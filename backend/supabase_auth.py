"""Calls to the Supabase Auth (GoTrue) REST API.

Supabase keeps passwords, sessions and verification emails. This module only forwards requests
and never logs or stores a password. It needs two keys from backend/.env: SUPABASE_URL and
SUPABASE_PUBLISHABLE_KEY (no secret key).

On failure it raises SupabaseAuthError (code = Supabase's error code); routers/account.py turns
that into an API error for each endpoint.
"""
import os
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY") or ""
TIMEOUT_SECONDS = 10.0
# Pins the error response format. With this version errors look like {"code": "<error code>", "message": ...}.
API_VERSION = "2024-01-01"


_http_client: Optional[httpx.Client] = None


def _http() -> httpx.Client:
    # One shared client keeps HTTPS connections open, so each call skips a new TLS handshake.
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(timeout=TIMEOUT_SECONDS)
    return _http_client


class SupabaseAuthError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(f"{status_code} {code}: {message}")
        self.status_code = status_code
        self.code = code
        self.message = message


def auth_url() -> str:
    if not SUPABASE_URL:
        raise RuntimeError("SUPABASE_URL is not set (backend/.env).")
    return f"{SUPABASE_URL}/auth/v1"


def api_headers() -> dict[str, str]:
    if not SUPABASE_PUBLISHABLE_KEY:
        raise RuntimeError("SUPABASE_PUBLISHABLE_KEY is not set (backend/.env).")
    return {"apikey": SUPABASE_PUBLISHABLE_KEY, "X-Supabase-Api-Version": API_VERSION}


def error_from_response(response: httpx.Response) -> SupabaseAuthError:
    try:
        body = response.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        body = {}
    # With the API_VERSION header: code (string) + message. Without it: code (number) + error_code + msg.
    # The oldest /token format: error + error_description. Accept all three.
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
        response = _http().request(method, auth_url() + path, json=json, params=params, headers=headers)
    except httpx.HTTPError as exc:
        raise SupabaseAuthError(503, "unavailable", str(exc)) from exc
    if response.status_code >= 400:
        raise error_from_response(response)
    return response.json() if response.content else {}


def sign_up(email: str, password: str, display_name: str) -> dict[str, Any]:
    """With Confirm email on, this returns the user without a session and emails a verification code."""
    return _request(
        "POST", "/signup", json={"email": email, "password": password, "data": {"display_name": display_name}}
    )


def verify_otp(email: str, code: str, otp_type: str) -> dict[str, Any]:
    """Check an emailed code. otp_type: 'signup' (verify email) | 'recovery' (reset password). Returns a session."""
    return _request("POST", "/verify", json={"type": otp_type, "email": email, "token": code})


def resend_signup_code(email: str) -> None:
    _request("POST", "/resend", json={"type": "signup", "email": email})


def sign_in(email: str, password: str) -> dict[str, Any]:
    return _request("POST", "/token", params={"grant_type": "password"}, json={"email": email, "password": password})


def refresh_session(refresh_token: str) -> dict[str, Any]:
    return _request("POST", "/token", params={"grant_type": "refresh_token"}, json={"refresh_token": refresh_token})


def sign_out(access_token: str, scope: str) -> None:
    """scope: 'local' (this session) | 'others' (all but this one) | 'global' (all of them)."""
    _request("POST", "/logout", params={"scope": scope}, access_token=access_token)


def update_password(access_token: str, new_password: str) -> None:
    _request("PUT", "/user", json={"password": new_password}, access_token=access_token)


def send_password_reset(email: str) -> None:
    """Supabase answers success even for an email with no account."""
    _request("POST", "/recover", json={"email": email})
