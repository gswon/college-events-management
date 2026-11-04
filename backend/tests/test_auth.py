"""인증 API 테스트 (NYU Google 계정 로그인).

Supabase 호출은 FakeSupabase로 바꿔 실제 계정을 만들지 않는다.
토큰 검증은 테스트용 EC 키쌍으로 서명한 JWT로 확인한다.
db 픽스처를 쓰는 테스트만 DB에 접속한다 (끝나면 롤백).
"""
import time
import uuid
from datetime import datetime

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import func, select

import auth
import models
import supabase_auth
from supabase_auth import SupabaseAuthError
from tests.conftest import make_user
from tests.test_events import assert_error

API = "/api/v1"
SUPABASE_URL = "https://test-project.supabase.co"
ISSUER = f"{SUPABASE_URL}/auth/v1"
AVATAR = "https://lh3.googleusercontent.com/a/test-avatar"


# --- 준비 --------------------------------------------------------------------

@pytest.fixture(scope="module")
def signing_key():
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture(autouse=True)
def supabase_config(monkeypatch, signing_key):
    monkeypatch.setattr(supabase_auth, "SUPABASE_URL", SUPABASE_URL)
    monkeypatch.setattr(supabase_auth, "SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test")
    monkeypatch.setattr(auth, "_signing_key", lambda token: signing_key.public_key())


class FakeSupabase:
    """supabase_auth 함수 호출을 기록하고, results[이름]을 돌려주거나 예외면 던진다."""

    NAMES = ("sign_in_with_id_token", "refresh_session", "sign_out")

    def __init__(self, monkeypatch):
        self.calls: list[tuple] = []
        self.results: dict[str, object] = {}
        for name in self.NAMES:
            monkeypatch.setattr(supabase_auth, name, self._recorder(name))

    def _recorder(self, name):
        def call(*args):
            self.calls.append((name, *args))
            result = self.results.get(name, {})
            if isinstance(result, Exception):
                raise result
            return result
        return call

    def called(self, name) -> list[tuple]:
        return [call[1:] for call in self.calls if call[0] == name]


@pytest.fixture
def fake(monkeypatch):
    return FakeSupabase(monkeypatch)


def new_email() -> str:
    return f"pytest-{uuid.uuid4().hex[:12]}@nyu.edu"


def supa_session(email: str, uid: str = None, access_token: str = "at-new", **metadata) -> dict:
    """Supabase가 Google ID 토큰 로그인 후 돌려주는 세션 모양."""
    meta = {"full_name": "Kim Tester", "avatar_url": AVATAR, "email": email, "email_verified": True}
    meta.update(metadata)
    return {
        "access_token": access_token,
        "refresh_token": "rt-new",
        "token_type": "bearer",
        "expires_in": 3600,
        "user": {
            "id": uid or str(uuid.uuid4()),
            "email": email,
            "email_confirmed_at": "2026-11-04T12:00:00.123456Z",
            "app_metadata": {"provider": "google", "providers": ["google"]},
            "user_metadata": {k: v for k, v in meta.items() if v is not None},
        },
    }


def make_token(key, sub: str, email: str = "someone@nyu.edu", **overrides) -> str:
    now = int(time.time())
    claims = {
        "sub": sub, "email": email, "aud": "authenticated", "iss": ISSUER,
        "role": "authenticated", "iat": now, "exp": now + 3600,
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="ES256")


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def supa_error(status: int, code: str) -> SupabaseAuthError:
    return SupabaseAuthError(status, code, "supabase message")


def google_login(client, id_token: str = "google-id-token", **extra):
    return client.post(f"{API}/auth/google", json={"id_token": id_token, **extra})


# --- Google 로그인 -------------------------------------------------------------

def test_first_login_creates_user_from_google_profile(client, db, fake):
    email, uid = new_email(), str(uuid.uuid4())
    fake.results["sign_in_with_id_token"] = supa_session(email, uid)
    res = google_login(client)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["access_token"] == "at-new" and body["refresh_token"] == "rt-new"
    assert body["token_type"] == "bearer" and body["expires_in"] == 3600
    assert body["user"]["email"] == email
    assert body["user"]["display_name"] == "Kim Tester"
    assert body["user"]["profile_image_url"] == AVATAR
    assert fake.called("sign_in_with_id_token") == [("google", "google-id-token", None)]

    user = db.scalar(select(models.User).where(models.User.auth_uid == uid))
    assert user.id == body["user"]["id"]
    assert user.password_hash is None
    assert user.email_verified_at.replace(microsecond=0) == datetime(2026, 11, 4, 12, 0)


def test_login_passes_nonce(client, db, fake):
    fake.results["sign_in_with_id_token"] = supa_session(new_email())
    assert google_login(client, nonce="raw-nonce").status_code == 200
    assert fake.called("sign_in_with_id_token") == [("google", "google-id-token", "raw-nonce")]


def test_name_falls_back_to_email(client, db, fake):
    email = new_email()
    fake.results["sign_in_with_id_token"] = supa_session(email, full_name=None, avatar_url=None, name=None)
    body = google_login(client).json()
    assert body["user"]["display_name"] == email.split("@")[0]
    assert body["user"]["profile_image_url"] is None


def test_uppercase_nyu_email_is_allowed(client, db, fake):
    email = new_email()
    fake.results["sign_in_with_id_token"] = supa_session(email.upper())
    res = google_login(client)
    assert res.status_code == 200, res.text
    assert res.json()["user"]["email"] == email


def test_non_nyu_google_account_is_rejected(client, db, fake):
    fake.results["sign_in_with_id_token"] = supa_session("someone@gmail.com", access_token="at-gmail")
    assert_error(google_login(client), 403, "NYU_ACCOUNT_REQUIRED")
    # 받은 세션은 끊고, MySQL에는 아무것도 만들지 않는다.
    assert fake.called("sign_out") == [("at-gmail", "global")]
    assert db.scalar(select(models.User).where(models.User.email == "someone@gmail.com")) is None


def test_login_links_existing_row_by_email(client, db, fake):
    existing = make_user(db, name="Old Name", email=new_email())
    uid = str(uuid.uuid4())
    fake.results["sign_in_with_id_token"] = supa_session(existing.email, uid)
    res = google_login(client)
    assert res.status_code == 200, res.text
    # 이미 있던 이름·사진은 Google 프로필로 덮어쓰지 않는다.
    assert res.json()["user"] == {"id": existing.id, "email": existing.email, "display_name": "Old Name", "profile_image_url": None}
    db.refresh(existing)
    assert existing.auth_uid == uid


def test_login_twice_keeps_one_row(client, db, fake):
    email, uid = new_email(), str(uuid.uuid4())
    fake.results["sign_in_with_id_token"] = supa_session(email, uid)
    first = google_login(client).json()
    fake.results["sign_in_with_id_token"] = supa_session(email, uid, full_name="Changed Name")
    second = google_login(client).json()
    assert first["user"]["id"] == second["user"]["id"]
    assert second["user"]["display_name"] == "Kim Tester"
    assert db.scalar(select(func.count()).select_from(models.User).where(models.User.email == email)) == 1


def test_invalid_google_token(client, fake):
    fake.results["sign_in_with_id_token"] = supa_error(400, "validation_failed")
    assert_error(google_login(client), 401, "INVALID_GOOGLE_TOKEN")


def test_empty_google_token(client, fake):
    assert_error(google_login(client, id_token=""), 422, "VALIDATION_ERROR")
    assert fake.calls == []


def test_google_provider_disabled_is_server_error(client, fake):
    fake.results["sign_in_with_id_token"] = supa_error(422, "provider_disabled")
    assert_error(google_login(client), 502, "AUTH_FAILED")


def test_rate_limited(client, fake):
    fake.results["sign_in_with_id_token"] = supa_error(429, "over_request_rate_limit")
    assert_error(google_login(client), 429, "RATE_LIMITED")


def test_supabase_unreachable(client, fake):
    fake.results["sign_in_with_id_token"] = supa_error(503, "unavailable")
    assert_error(google_login(client), 503, "AUTH_UNAVAILABLE")


def test_unexpected_supabase_error(client, fake):
    fake.results["sign_in_with_id_token"] = supa_error(500, "unexpected_failure")
    assert_error(google_login(client), 502, "AUTH_FAILED")


def test_email_password_endpoints_are_gone(client):
    for path in ("/auth/signup", "/auth/login", "/auth/password/forgot"):
        assert client.post(f"{API}{path}", json={}).status_code == 404


# --- 세션 ----------------------------------------------------------------------

def test_refresh_returns_new_tokens(client, db, fake):
    fake.results["refresh_session"] = supa_session(new_email(), access_token="at-refreshed")
    res = client.post(f"{API}/auth/refresh", json={"refresh_token": "rt-old"})
    assert res.status_code == 200, res.text
    assert res.json()["access_token"] == "at-refreshed"
    assert fake.called("refresh_session") == [("rt-old",)]


def test_refresh_with_used_token(client, fake):
    fake.results["refresh_session"] = supa_error(400, "refresh_token_already_used")
    assert_error(client.post(f"{API}/auth/refresh", json={"refresh_token": "rt-old"}), 401, "INVALID_REFRESH_TOKEN")


def test_refresh_rejects_non_nyu_session(client, fake):
    # Supabase를 직접 호출해 얻은 세션이어도 우리 API로는 NYU 계정만 통과한다.
    fake.results["refresh_session"] = supa_session("someone@gmail.com", access_token="at-gmail")
    assert_error(client.post(f"{API}/auth/refresh", json={"refresh_token": "rt"}), 403, "NYU_ACCOUNT_REQUIRED")
    assert fake.called("sign_out") == [("at-gmail", "global")]


def test_logout_ends_this_session(auth_client, fake, signing_key):
    token = make_token(signing_key, str(uuid.uuid4()))
    res = auth_client.post(f"{API}/auth/logout", headers=bearer(token))
    assert res.status_code == 204, res.text
    assert fake.called("sign_out") == [(token, "local")]


def test_logout_of_ended_session_still_succeeds(auth_client, fake, signing_key):
    fake.results["sign_out"] = supa_error(404, "session_not_found")
    res = auth_client.post(f"{API}/auth/logout", headers=bearer(make_token(signing_key, str(uuid.uuid4()))))
    assert res.status_code == 204, res.text


def test_logout_needs_token(auth_client, fake):
    assert_error(auth_client.post(f"{API}/auth/logout"), 401, "AUTH_REQUIRED")
    assert fake.calls == []


# --- 토큰 검증 (auth.get_current_user) ---------------------------------------

def test_no_token(auth_client):
    assert_error(auth_client.get(f"{API}/friends"), 401, "AUTH_REQUIRED")


def test_expired_token(auth_client, signing_key):
    token = make_token(signing_key, str(uuid.uuid4()), exp=int(time.time()) - 10)
    assert_error(auth_client.get(f"{API}/friends", headers=bearer(token)), 401, "TOKEN_EXPIRED")


@pytest.mark.parametrize("overrides", [{"aud": "anon"}, {"iss": "https://other.supabase.co/auth/v1"}])
def test_token_for_wrong_audience_or_issuer(auth_client, signing_key, overrides):
    token = make_token(signing_key, str(uuid.uuid4()), **overrides)
    assert_error(auth_client.get(f"{API}/friends", headers=bearer(token)), 401, "INVALID_TOKEN")


def test_token_signed_by_other_key(auth_client):
    token = make_token(ec.generate_private_key(ec.SECP256R1()), str(uuid.uuid4()))
    assert_error(auth_client.get(f"{API}/friends", headers=bearer(token)), 401, "INVALID_TOKEN")


def test_valid_token_reaches_api(auth_client, db, signing_key):
    uid = str(uuid.uuid4())
    make_user(db, auth_uid=uid)
    res = auth_client.get(f"{API}/friends", headers=bearer(make_token(signing_key, uid)))
    assert res.status_code == 200, res.text


def test_valid_token_without_user_row(auth_client, db, signing_key):
    token = make_token(signing_key, str(uuid.uuid4()))
    assert_error(auth_client.get(f"{API}/friends", headers=bearer(token)), 401, "AUTH_REQUIRED")


# --- Supabase 응답 해석 --------------------------------------------------------

@pytest.mark.parametrize(
    "body, code, message",
    [
        ({"code": 400, "error_code": "validation_failed", "msg": "Bad ID token"}, "validation_failed", "Bad ID token"),
        ({"error": "invalid_grant", "error_description": "Invalid Refresh Token"}, "invalid_grant", "Invalid Refresh Token"),
    ],
)
def test_error_from_response(body, code, message):
    exc = supabase_auth.error_from_response(httpx.Response(400, json=body))
    assert (exc.status_code, exc.code, exc.message) == (400, code, message)


def test_error_from_non_json_response():
    exc = supabase_auth.error_from_response(httpx.Response(502, text="Bad Gateway"))
    assert (exc.status_code, exc.code, exc.message) == (502, "unknown", "Bad Gateway")
