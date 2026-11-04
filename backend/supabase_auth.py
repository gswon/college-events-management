"""Supabase Auth(GoTrue) REST 호출.

로그인은 Google 계정으로만 한다. 앱이 Google에서 받은 ID 토큰을 Supabase가 검증하고
세션(access/refresh 토큰)을 만든다. 필요한 키는 backend/.env의
SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY 두 개다 (secret 키는 쓰지 않는다).

실패하면 SupabaseAuthError(code=Supabase error_code)를 던지고,
API 에러 코드로 바꾸는 건 routers/account.py가 한다.
"""
import os
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY") or ""
TIMEOUT_SECONDS = 10.0
# 이 헤더가 있어야 /token 에러도 error_code 형식으로 온다.
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
    # 현재 형식은 error_code/msg, 옛 /token 형식은 error/error_description.
    code = body.get("error_code") or body.get("error") or "unknown"
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


def sign_in_with_id_token(provider: str, id_token: str, nonce: Optional[str]) -> dict[str, Any]:
    """Google 등에서 받은 ID 토큰으로 세션을 만든다. 처음 보는 계정이면 Supabase 유저도 만든다.

    ID 토큰을 받을 때 nonce를 썼다면 그 원문(해시 전)을 같이 보내야 한다.
    """
    body = {"provider": provider, "id_token": id_token}
    if nonce:
        body["nonce"] = nonce
    return _request("POST", "/token", params={"grant_type": "id_token"}, json=body)


def refresh_session(refresh_token: str) -> dict[str, Any]:
    return _request("POST", "/token", params={"grant_type": "refresh_token"}, json={"refresh_token": refresh_token})


def sign_out(access_token: str, scope: str) -> None:
    """scope: 'local'(이 세션) | 'others'(이 세션 빼고 전부) | 'global'(전부)."""
    _request("POST", "/logout", params={"scope": scope}, access_token=access_token)
