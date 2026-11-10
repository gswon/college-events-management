"""인증 API 테스트 (Supabase 이메일 + 비밀번호).

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
# 새 비밀번호 규칙(8자 이상, 소문자·대문자·숫자·특수문자)을 통과하는 값
PASSWORD = "Passw0rd!"
NEW_PASSWORD = "NewPassw0rd!"


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

    NAMES = (
        "sign_up", "verify_otp", "resend_signup_code", "sign_in",
        "refresh_session", "sign_out", "update_password", "send_password_reset",
    )

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


def supa_session(email: str, uid: str = None, display_name: str = "Tester", access_token: str = "at-new") -> dict:
    return {
        "access_token": access_token,
        "refresh_token": "rt-new",
        "token_type": "bearer",
        "expires_in": 3600,
        "user": {
            "id": uid or str(uuid.uuid4()),
            "email": email,
            "email_confirmed_at": "2026-11-04T12:00:00.123456Z",
            "user_metadata": {"display_name": display_name},
            "identities": [{"provider": "email"}],
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


# --- 가입 --------------------------------------------------------------------

def test_signup_sends_code(client, fake):
    res = client.post(f"{API}/auth/signup", json={"email": "  Student@NYU.edu ", "password": PASSWORD, "display_name": " Kim "})
    assert res.status_code == 201, res.text
    assert res.json() == {"email": "student@nyu.edu"}
    assert fake.called("sign_up") == [("student@nyu.edu", PASSWORD, "Kim")]


def test_signup_only_nyu_email(client, fake):
    res = client.post(f"{API}/auth/signup", json={"email": "a@gmail.com", "password": PASSWORD, "display_name": "A"})
    assert_error(res, 400, "INVALID_EMAIL_DOMAIN")
    assert fake.calls == []


def test_signup_short_password_never_reaches_supabase(client, fake):
    res = client.post(f"{API}/auth/signup", json={"email": new_email(), "password": "short", "display_name": "A"})
    assert_error(res, 422, "VALIDATION_ERROR")
    assert fake.calls == []


@pytest.mark.parametrize(
    "password, missing",
    [
        ("PASSW0RD!", "소문자"),
        ("passw0rd!", "대문자"),
        ("Password!", "숫자"),
        ("Passw0rd1", "특수문자"),
        ("Passw0rd 한글", "특수문자"),  # 공백·한글은 Supabase가 특수문자로 치지 않는다
    ],
)
def test_new_password_needs_every_character_kind(client, fake, password, missing):
    signup = client.post(f"{API}/auth/signup", json={"email": new_email(), "password": password, "display_name": "A"})
    assert_error(signup, 422, "VALIDATION_ERROR")
    assert missing in signup.json()["error"]["message"]
    reset = client.post(f"{API}/auth/password/reset", json={"email": new_email(), "code": "654321", "new_password": password})
    assert_error(reset, 422, "VALIDATION_ERROR")
    # 재설정 코드가 소모되지 않도록 Supabase까지 가지 않아야 한다.
    assert fake.calls == []


@pytest.mark.parametrize("symbol", list("!@#$%^&*()_+-=[]{};'\\:\"|<>?,./`~"))
def test_new_password_accepts_supabase_symbols(client, fake, symbol):
    res = client.post(f"{API}/auth/signup", json={"email": new_email(), "password": f"Passw0rd{symbol}", "display_name": "A"})
    assert res.status_code == 201, res.text


def test_signup_verified_email_is_taken(client, fake):
    # Confirm email이 켜져 있으면 이미 가입된 이메일에 identities가 빈 가짜 유저가 온다.
    fake.results["sign_up"] = {"id": str(uuid.uuid4()), "email": "x@nyu.edu", "identities": []}
    res = client.post(f"{API}/auth/signup", json={"email": new_email(), "password": PASSWORD, "display_name": "A"})
    assert_error(res, 409, "EMAIL_TAKEN")


def test_signup_existing_user_error_is_taken(client, fake):
    fake.results["sign_up"] = supa_error(422, "user_already_exists")
    res = client.post(f"{API}/auth/signup", json={"email": new_email(), "password": PASSWORD, "display_name": "A"})
    assert_error(res, 409, "EMAIL_TAKEN")


def test_signup_weak_password_from_supabase(client, fake):
    fake.results["sign_up"] = supa_error(422, "weak_password")
    res = client.post(f"{API}/auth/signup", json={"email": new_email(), "password": PASSWORD, "display_name": "A"})
    assert_error(res, 422, "WEAK_PASSWORD")


def test_resend_hides_whether_email_exists(client, fake):
    fake.results["resend_signup_code"] = supa_error(400, "user_not_found")
    res = client.post(f"{API}/auth/verify-email/resend", json={"email": new_email()})
    assert res.status_code == 204, res.text


def test_resend_rate_limited(client, fake):
    fake.results["resend_signup_code"] = supa_error(429, "over_email_send_rate_limit")
    assert_error(client.post(f"{API}/auth/verify-email/resend", json={"email": new_email()}), 429, "RATE_LIMITED")


def test_verify_email_bad_code(client, fake):
    fake.results["verify_otp"] = supa_error(403, "otp_expired")
    res = client.post(f"{API}/auth/verify-email", json={"email": new_email(), "code": "123456"})
    assert_error(res, 400, "INVALID_CODE")


def test_verify_email_logs_in(client, db, fake):
    email = new_email()
    fake.results["verify_otp"] = supa_session(email, display_name="Verified")
    res = client.post(f"{API}/auth/verify-email", json={"email": email, "code": " 123456 "})
    assert res.status_code == 200, res.text
    assert res.json()["user"]["display_name"] == "Verified"
    assert fake.called("verify_otp") == [(email, "123456", "signup")]


# --- 로그인 / 세션 -------------------------------------------------------------

def test_login_creates_user_on_first_login(client, db, fake):
    email, uid = new_email(), str(uuid.uuid4())
    fake.results["sign_in"] = supa_session(email, uid, display_name="New Name")
    res = client.post(f"{API}/auth/login", json={"email": email.upper(), "password": "pw"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["access_token"] == "at-new" and body["refresh_token"] == "rt-new"
    assert body["token_type"] == "bearer" and body["expires_in"] == 3600
    assert body["user"]["email"] == email and body["user"]["display_name"] == "New Name"
    assert fake.called("sign_in") == [(email, "pw")]

    user = db.scalar(select(models.User).where(models.User.auth_uid == uid))
    assert user.id == body["user"]["id"]
    assert user.password_hash is None
    assert user.email_verified_at.replace(microsecond=0) == datetime(2026, 11, 4, 12, 0)


def test_login_links_existing_row_by_email(client, db, fake):
    existing = make_user(db, name="Old Name", email=new_email())
    uid = str(uuid.uuid4())
    fake.results["sign_in"] = supa_session(existing.email, uid, display_name="Ignored")
    res = client.post(f"{API}/auth/login", json={"email": existing.email, "password": "pw"})
    assert res.status_code == 200, res.text
    assert res.json()["user"] == {"id": existing.id, "email": existing.email, "display_name": "Old Name", "profile_image_url": None}
    db.refresh(existing)
    assert existing.auth_uid == uid


def test_login_twice_keeps_one_row(client, db, fake):
    email, uid = new_email(), str(uuid.uuid4())
    fake.results["sign_in"] = supa_session(email, uid)
    first = client.post(f"{API}/auth/login", json={"email": email, "password": "pw"}).json()
    second = client.post(f"{API}/auth/login", json={"email": email, "password": "pw"}).json()
    assert first["user"]["id"] == second["user"]["id"]
    assert db.scalar(select(func.count()).select_from(models.User).where(models.User.email == email)) == 1


def test_login_non_nyu_account_is_rejected(client, db, fake):
    # 대시보드에서 직접 만든 계정처럼 @nyu.edu가 아닌 세션은 끊고, MySQL에는 만들지 않는다.
    fake.results["sign_in"] = supa_session("someone@gmail.com", access_token="at-gmail")
    assert_error(client.post(f"{API}/auth/login", json={"email": "someone@gmail.com", "password": "pw"}), 403, "NYU_ACCOUNT_REQUIRED")
    assert fake.called("sign_out") == [("at-gmail", "global")]
    assert db.scalar(select(models.User).where(models.User.email == "someone@gmail.com")) is None


def test_login_wrong_password(client, fake):
    fake.results["sign_in"] = supa_error(400, "invalid_credentials")
    assert_error(client.post(f"{API}/auth/login", json={"email": new_email(), "password": "pw"}), 401, "INVALID_CREDENTIALS")


def test_login_email_not_verified(client, fake):
    fake.results["sign_in"] = supa_error(400, "email_not_confirmed")
    assert_error(client.post(f"{API}/auth/login", json={"email": new_email(), "password": "pw"}), 403, "EMAIL_NOT_VERIFIED")


def test_supabase_unreachable(client, fake):
    fake.results["sign_in"] = supa_error(503, "unavailable")
    assert_error(client.post(f"{API}/auth/login", json={"email": new_email(), "password": "pw"}), 503, "AUTH_UNAVAILABLE")


def test_unexpected_supabase_error(client, fake):
    fake.results["sign_in"] = supa_error(500, "unexpected_failure")
    assert_error(client.post(f"{API}/auth/login", json={"email": new_email(), "password": "pw"}), 502, "AUTH_FAILED")


def test_google_login_endpoint_is_gone(client):
    assert client.post(f"{API}/auth/google", json={"id_token": "x"}).status_code == 404


def test_refresh_returns_new_tokens(client, db, fake):
    email = new_email()
    fake.results["refresh_session"] = supa_session(email, access_token="at-refreshed")
    res = client.post(f"{API}/auth/refresh", json={"refresh_token": "rt-old"})
    assert res.status_code == 200, res.text
    assert res.json()["access_token"] == "at-refreshed"
    assert fake.called("refresh_session") == [("rt-old",)]


def test_refresh_with_used_token(client, fake):
    fake.results["refresh_session"] = supa_error(400, "refresh_token_already_used")
    assert_error(client.post(f"{API}/auth/refresh", json={"refresh_token": "rt-old"}), 401, "INVALID_REFRESH_TOKEN")


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


# --- 비밀번호 변경 / 찾기 ------------------------------------------------------

@pytest.fixture
def logged_in(db, signing_key):
    uid = str(uuid.uuid4())
    user = make_user(db, auth_uid=uid)
    return user, bearer(make_token(signing_key, uid, email=user.email))


def test_change_password(auth_client, fake, logged_in):
    user, headers = logged_in
    fake.results["sign_in"] = supa_session(user.email, user.auth_uid, access_token="at-verify")
    res = auth_client.put(f"{API}/users/me/password", headers=headers,
                          json={"current_password": "oldpassword", "new_password": NEW_PASSWORD})
    assert res.status_code == 200, res.text
    assert res.json()["access_token"] == "at-verify"
    assert res.json()["user"]["id"] == user.id
    assert fake.called("sign_in") == [(user.email, "oldpassword")]
    assert fake.called("update_password") == [("at-verify", NEW_PASSWORD)]
    assert fake.called("sign_out") == [("at-verify", "others")]


def test_change_password_wrong_current(auth_client, fake, logged_in):
    _, headers = logged_in
    fake.results["sign_in"] = supa_error(400, "invalid_credentials")
    res = auth_client.put(f"{API}/users/me/password", headers=headers,
                          json={"current_password": "wrong", "new_password": NEW_PASSWORD})
    assert_error(res, 400, "INVALID_CURRENT_PASSWORD")
    assert fake.called("update_password") == []


def test_change_password_rejected_ends_check_session(auth_client, fake, logged_in):
    user, headers = logged_in
    fake.results["sign_in"] = supa_session(user.email, user.auth_uid, access_token="at-verify")
    fake.results["update_password"] = supa_error(422, "same_password")
    res = auth_client.put(f"{API}/users/me/password", headers=headers,
                          json={"current_password": PASSWORD, "new_password": PASSWORD})
    assert_error(res, 400, "SAME_PASSWORD")
    assert fake.called("sign_out") == [("at-verify", "local")]


def test_change_password_needs_token(auth_client, fake):
    res = auth_client.put(f"{API}/users/me/password", json={"current_password": "a", "new_password": NEW_PASSWORD})
    assert_error(res, 401, "AUTH_REQUIRED")
    assert fake.calls == []


def test_forgot_password_hides_whether_email_exists(client, fake):
    fake.results["send_password_reset"] = supa_error(400, "user_not_found")
    res = client.post(f"{API}/auth/password/forgot", json={"email": new_email()})
    assert res.status_code == 204, res.text


def test_reset_password(client, fake):
    email = new_email()
    fake.results["verify_otp"] = supa_session(email, access_token="at-recovery")
    res = client.post(f"{API}/auth/password/reset", json={"email": email, "code": "654321", "new_password": NEW_PASSWORD})
    assert res.status_code == 204, res.text
    assert fake.called("verify_otp") == [(email, "654321", "recovery")]
    assert fake.called("update_password") == [("at-recovery", NEW_PASSWORD)]
    assert fake.called("sign_out") == [("at-recovery", "global")]


def test_reset_password_bad_code(client, fake):
    fake.results["verify_otp"] = supa_error(403, "otp_expired")
    res = client.post(f"{API}/auth/password/reset", json={"email": new_email(), "code": "654321", "new_password": NEW_PASSWORD})
    assert_error(res, 400, "INVALID_CODE")
    assert fake.called("update_password") == []


def test_reset_password_rejected_ends_recovery_session(client, fake):
    email = new_email()
    fake.results["verify_otp"] = supa_session(email, access_token="at-recovery")
    fake.results["update_password"] = supa_error(422, "weak_password")
    res = client.post(f"{API}/auth/password/reset", json={"email": email, "code": "654321", "new_password": NEW_PASSWORD})
    assert_error(res, 422, "WEAK_PASSWORD")
    assert fake.called("sign_out") == [("at-recovery", "local")]


# --- Supabase 응답 해석 --------------------------------------------------------

@pytest.mark.parametrize(
    "body, code, message",
    [
        # X-Supabase-Api-Version: 2024-01-01 을 보낼 때 실제로 오는 형식
        ({"code": "invalid_credentials", "message": "Invalid login credentials"},
         "invalid_credentials", "Invalid login credentials"),
        ({"code": 400, "error_code": "invalid_credentials", "msg": "Invalid login credentials"},
         "invalid_credentials", "Invalid login credentials"),
        ({"error": "invalid_grant", "error_description": "Invalid Refresh Token"}, "invalid_grant", "Invalid Refresh Token"),
    ],
)
def test_error_from_response(body, code, message):
    exc = supabase_auth.error_from_response(httpx.Response(400, json=body))
    assert (exc.status_code, exc.code, exc.message) == (400, code, message)


def test_error_from_non_json_response():
    exc = supabase_auth.error_from_response(httpx.Response(502, text="Bad Gateway"))
    assert (exc.status_code, exc.code, exc.message) == (502, "unknown", "Bad Gateway")
