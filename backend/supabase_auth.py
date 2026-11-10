"""Supabase Auth(GoTrue) REST 호출.

비밀번호·세션·인증 메일은 Supabase가 관리한다. 여기서는 요청을 넘기기만 하고
비밀번호는 로그·DB 어디에도 남기지 않는다. 필요한 키는 backend/.env의
SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY 두 개다 (secret 키는 쓰지 않는다).

실패하면 SupabaseAuthError(code=Supabase error_code)를 던지고,
API 에러 코드로 바꾸는 건 routers/account.py가 엔드포인트마다 한다.
"""
import os
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY") or ""
TIMEOUT_SECONDS = 10.0
# 에러 응답 형식을 고정하는 헤더. 이 버전에서는 {"code": "<에러 코드>", "message": ...}로 온다.
API_VERSION = "2024-01-01"


class SupabaseAuthError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(f"{status_code} {code}: {message}")
        self.status_code = status_code
        self.code = code
        self.message = message


def auth_url() -> str:
    if not SUPABASE_URL:
        raise RuntimeError("SUPABASE_URL이 설정되지 않았습니다 (backend/.env).")
    return f"{SUPABASE_URL}/auth/v1"


def api_headers() -> dict[str, str]:
    if not SUPABASE_PUBLISHABLE_KEY:
        raise RuntimeError("SUPABASE_PUBLISHABLE_KEY가 설정되지 않았습니다 (backend/.env).")
    return {"apikey": SUPABASE_PUBLISHABLE_KEY, "X-Supabase-Api-Version": API_VERSION}


def error_from_response(response: httpx.Response) -> SupabaseAuthError:
    try:
        body = response.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        body = {}
    # API_VERSION 헤더를 보내면 code(문자열)/message, 안 보내면 code(숫자)+error_code/msg,
    # 아주 옛 /token 형식은 error/error_description. 셋 다 받아 준다.
    version_code = body.get("code") if isinstance(body.get("code"), str) else None
    code = body.get("error_code") or version_code or body.get("error") or "unknown"
    message = body.get("msg") or body.get("error_description") or body.get("message") or response.text
    return SupabaseAuthError(response.status_code, str(code), str(message))


def _request(
    method: str,
    path: str,
    *,
    json: Optional[dict[str, Any]] = None,
    params: Optional[dict[str, str]] = None,
    access_token: Optional[str] = None,
) -> dict[str, Any]:
    headers = api_headers()
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    try:
        response = httpx.request(
            method, auth_url() + path, json=json, params=params, headers=headers, timeout=TIMEOUT_SECONDS
        )
    except httpx.HTTPError as exc:
        raise SupabaseAuthError(503, "unavailable", str(exc)) from exc
    if response.status_code >= 400:
        raise error_from_response(response)
    return response.json() if response.content else {}


def sign_up(email: str, password: str, display_name: str) -> dict[str, Any]:
    """Confirm email이 켜져 있으면 세션 없이 유저만 오고, 인증 코드 메일이 나간다."""
    return _request(
        "POST", "/signup", json={"email": email, "password": password, "data": {"display_name": display_name}}
    )


def verify_otp(email: str, code: str, otp_type: str) -> dict[str, Any]:
    """메일로 받은 코드 확인. otp_type: 'signup'(가입 인증) | 'recovery'(비밀번호 재설정). 세션을 돌려준다."""
    return _request("POST", "/verify", json={"type": otp_type, "email": email, "token": code})


def resend_signup_code(email: str) -> None:
    _request("POST", "/resend", json={"type": "signup", "email": email})


def sign_in(email: str, password: str) -> dict[str, Any]:
    return _request("POST", "/token", params={"grant_type": "password"}, json={"email": email, "password": password})


def refresh_session(refresh_token: str) -> dict[str, Any]:
    return _request("POST", "/token", params={"grant_type": "refresh_token"}, json={"refresh_token": refresh_token})


def sign_out(access_token: str, scope: str) -> None:
    """scope: 'local'(이 세션) | 'others'(이 세션 빼고 전부) | 'global'(전부)."""
    _request("POST", "/logout", params={"scope": scope}, access_token=access_token)


def update_password(access_token: str, new_password: str) -> None:
    _request("PUT", "/user", json={"password": new_password}, access_token=access_token)


def send_password_reset(email: str) -> None:
    """가입 안 된 이메일이어도 Supabase는 성공으로 응답한다."""
    _request("POST", "/recover", json={"email": email})
