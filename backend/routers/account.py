"""회원가입·로그인·비밀번호 (/auth/*, /users/me/password).

인증 자체는 Supabase가 하고(supabase_auth.py), 여기서는 @nyu.edu 제한,
Supabase 유저 ↔ MySQL users 행 연결, Supabase 에러 → API 에러 코드 변환을 한다.
"""
import logging
from datetime import datetime
from typing import Annotated, Any, NoReturn, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

import models
import supabase_auth
from auth import token_dependency, user_dependency
from database import get_db
from errors import APIError
from schemas import (
    AuthSession,
    EmailIn,
    LoginIn,
    MeOut,
    PasswordChangeIn,
    PasswordResetIn,
    RefreshIn,
    SignupIn,
    SignupOut,
    VerifyEmailIn,
)
from supabase_auth import SupabaseAuthError
from timeutil import to_utc_naive, utc_now

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

db_dependency = Annotated[Session, Depends(get_db)]

ALLOWED_EMAIL_DOMAIN = "@nyu.edu"

ErrorSpec = tuple[int, str, str]

INVALID_EMAIL_DOMAIN: ErrorSpec = (400, "INVALID_EMAIL_DOMAIN", "@nyu.edu 이메일만 사용할 수 있습니다.")
NYU_ACCOUNT_REQUIRED: ErrorSpec = (403, "NYU_ACCOUNT_REQUIRED", "@nyu.edu 계정만 사용할 수 있습니다.")
EMAIL_TAKEN: ErrorSpec = (409, "EMAIL_TAKEN", "이미 가입된 이메일입니다.")
INVALID_CREDENTIALS: ErrorSpec = (401, "INVALID_CREDENTIALS", "이메일 또는 비밀번호가 올바르지 않습니다.")
EMAIL_NOT_VERIFIED: ErrorSpec = (403, "EMAIL_NOT_VERIFIED", "이메일 인증을 먼저 완료해 주세요.")
INVALID_CODE: ErrorSpec = (400, "INVALID_CODE", "코드가 틀렸거나 만료되었습니다.")
INVALID_REFRESH_TOKEN: ErrorSpec = (401, "INVALID_REFRESH_TOKEN", "다시 로그인해 주세요.")
INVALID_CURRENT_PASSWORD: ErrorSpec = (400, "INVALID_CURRENT_PASSWORD", "현재 비밀번호가 올바르지 않습니다.")
RATE_LIMITED: ErrorSpec = (429, "RATE_LIMITED", "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.")

# 어느 엔드포인트에서 나와도 뜻이 같은 Supabase 에러
_COMMON: dict[str, ErrorSpec] = {
    "weak_password": (422, "WEAK_PASSWORD", "비밀번호가 보안 기준에 맞지 않습니다."),
    "same_password": (400, "SAME_PASSWORD", "새 비밀번호가 기존 비밀번호와 같습니다."),
    "email_address_invalid": (400, "INVALID_EMAIL", "이메일 주소가 올바르지 않습니다."),
    "over_email_send_rate_limit": RATE_LIMITED,
    "over_request_rate_limit": RATE_LIMITED,
}


def _raise(
    exc: SupabaseAuthError,
    overrides: Optional[dict[str, ErrorSpec]] = None,
    client_error: Optional[ErrorSpec] = None,
) -> NoReturn:
    """Supabase 에러를 API 에러로 바꿔 던진다.

    overrides: 이 엔드포인트에서만 다르게 보여줄 Supabase 코드.
    client_error: 위에 없는 나머지 4xx를 한꺼번에 이 에러로 (예: 코드 확인 실패는 전부 INVALID_CODE).
    """
    spec = (overrides or {}).get(exc.code) or _COMMON.get(exc.code)
    if spec is None and exc.status_code == 429:
        spec = RATE_LIMITED
    if spec is None and client_error is not None and 400 <= exc.status_code < 500:
        spec = client_error
    if spec is not None:
        raise APIError(*spec) from exc
    if exc.code == "unavailable":
        raise APIError(503, "AUTH_UNAVAILABLE", "인증 서버에 연결할 수 없습니다.") from exc
    logger.error("Supabase auth error: %s", exc)
    raise APIError(502, "AUTH_FAILED", "인증 처리 중 오류가 발생했습니다.") from exc


def _raise_unless_client_error(exc: SupabaseAuthError) -> None:
    """가입 여부가 드러나지 않게, 요청 한도 초과가 아닌 4xx는 성공으로 넘긴다."""
    if exc.status_code == 429 or _COMMON.get(exc.code) == RATE_LIMITED or not 400 <= exc.status_code < 500:
        _raise(exc)
    logger.warning("Supabase가 거절했지만 성공으로 응답: %s", exc)


def _end_session_quietly(access_token: str, scope: str) -> None:
    try:
        supabase_auth.sign_out(access_token, scope)
    except SupabaseAuthError as exc:
        logger.warning("Supabase 세션 종료 실패(scope=%s): %s", scope, exc)


def _parse_time(value: str) -> datetime:
    try:
        return to_utc_naive(datetime.fromisoformat(value))
    except ValueError:
        return utc_now()


def _link_user(db: Session, supa_user: dict[str, Any]) -> models.User:
    """Supabase 유저에 맞는 users 행을 찾고, 없으면 만든다 (첫 로그인 때)."""
    uid = supa_user["id"]
    user = db.scalar(select(models.User).where(models.User.auth_uid == uid))
    if user is None:
        email = supa_user["email"].lower()
        # Supabase 도입 전에 만든 행(또는 Supabase에서 지웠다 다시 가입한 유저)은 이메일로 연결한다.
        user = db.scalar(select(models.User).where(models.User.email == email))
        if user is None:
            meta = supa_user.get("user_metadata") or {}
            name = str(meta.get("display_name") or "").strip()[:50] or email.split("@")[0][:50]
            user = models.User(email=email, display_name=name)
            db.add(user)
        user.auth_uid = uid
    confirmed_at = supa_user.get("email_confirmed_at")
    if confirmed_at and user.email_verified_at is None:
        user.email_verified_at = _parse_time(confirmed_at)
    db.commit()
    return user


def _session_out(db: Session, session: dict[str, Any]) -> AuthSession:
    supa_user = session["user"]
    if not (supa_user.get("email") or "").lower().endswith(ALLOWED_EMAIL_DOMAIN):
        # 가입은 @nyu.edu만 받지만, 대시보드에서 직접 만든 계정 같은 예외도 여기서 막는다.
        _end_session_quietly(session["access_token"], "global")
        raise APIError(*NYU_ACCOUNT_REQUIRED)
    user = _link_user(db, supa_user)
    return AuthSession(
        access_token=session["access_token"],
        refresh_token=session["refresh_token"],
        expires_in=session["expires_in"],
        user=MeOut.model_validate(user),
    )


# --- 가입 / 이메일 인증 ------------------------------------------------------

@router.post("/auth/signup", response_model=SignupOut, status_code=201)
def signup(body: SignupIn):
    """가입 후 인증 코드 메일이 나간다. users 행은 인증 뒤 첫 로그인 때 만들어진다."""
    if not body.email.endswith(ALLOWED_EMAIL_DOMAIN):
        raise APIError(*INVALID_EMAIL_DOMAIN)
    try:
        result = supabase_auth.sign_up(body.email, body.password, body.display_name)
    except SupabaseAuthError as exc:
        _raise(exc, {"user_already_exists": EMAIL_TAKEN, "email_exists": EMAIL_TAKEN})
    # 이미 인증까지 끝난 이메일이면 Supabase는 에러 대신 identities가 빈 가짜 유저를 돌려준다.
    supa_user = result.get("user") or result
    if supa_user.get("identities") == []:
        raise APIError(*EMAIL_TAKEN)
    return SignupOut(email=body.email)


@router.post("/auth/verify-email", response_model=AuthSession)
def verify_email(body: VerifyEmailIn, db: db_dependency):
    """메일로 받은 코드로 인증한다. 성공하면 바로 로그인 상태가 된다."""
    try:
        session = supabase_auth.verify_otp(body.email, body.code, "signup")
    except SupabaseAuthError as exc:
        _raise(exc, client_error=INVALID_CODE)
    return _session_out(db, session)


@router.post("/auth/verify-email/resend", status_code=204)
def resend_verification(body: EmailIn):
    try:
        supabase_auth.resend_signup_code(body.email)
    except SupabaseAuthError as exc:
        _raise_unless_client_error(exc)


# --- 로그인 / 세션 -----------------------------------------------------------

@router.post("/auth/login", response_model=AuthSession)
def login(body: LoginIn, db: db_dependency):
    try:
        session = supabase_auth.sign_in(body.email, body.password)
    except SupabaseAuthError as exc:
        _raise(exc, {"invalid_credentials": INVALID_CREDENTIALS, "email_not_confirmed": EMAIL_NOT_VERIFIED})
    return _session_out(db, session)


@router.post("/auth/refresh", response_model=AuthSession)
def refresh(body: RefreshIn, db: db_dependency):
    """refresh 토큰은 한 번 쓰면 바뀐다(회전). 응답의 두 토큰으로 모두 교체해야 한다."""
    try:
        session = supabase_auth.refresh_session(body.refresh_token)
    except SupabaseAuthError as exc:
        _raise(exc, client_error=INVALID_REFRESH_TOKEN)
    return _session_out(db, session)


@router.post("/auth/logout", status_code=204)
def logout(token: token_dependency):
    """이 기기 세션만 끝낸다. 이미 끝난 세션이어도 성공."""
    try:
        supabase_auth.sign_out(token.raw, "local")
    except SupabaseAuthError as exc:
        if not 400 <= exc.status_code < 500:
            _raise(exc)


# --- 비밀번호 ----------------------------------------------------------------

@router.put("/users/me/password", response_model=AuthSession)
def change_password(body: PasswordChangeIn, db: db_dependency, token: token_dependency, user: user_dependency):
    """현재 비밀번호로 로그인해 확인한 뒤 바꾼다.

    다른 기기는 모두 로그아웃되고, 이 기기는 응답의 새 토큰으로 교체해야 한다.
    """
    try:
        session = supabase_auth.sign_in(token.email or user.email, body.current_password)
    except SupabaseAuthError as exc:
        _raise(exc, {"invalid_credentials": INVALID_CURRENT_PASSWORD})
    new_token = session["access_token"]
    try:
        supabase_auth.update_password(new_token, body.new_password)
    except SupabaseAuthError as exc:
        _end_session_quietly(new_token, "local")
        _raise(exc)
    _end_session_quietly(new_token, "others")
    return _session_out(db, session)


@router.post("/auth/password/forgot", status_code=204)
def forgot_password(body: EmailIn):
    """재설정 코드 메일을 보낸다. 가입 여부와 상관없이 성공으로 응답한다."""
    try:
        supabase_auth.send_password_reset(body.email)
    except SupabaseAuthError as exc:
        _raise_unless_client_error(exc)


@router.post("/auth/password/reset", status_code=204)
def reset_password(body: PasswordResetIn):
    """코드 확인 → 비밀번호 변경 → 모든 기기 로그아웃. 끝나면 새 비밀번호로 다시 로그인한다."""
    try:
        session = supabase_auth.verify_otp(body.email, body.code, "recovery")
    except SupabaseAuthError as exc:
        _raise(exc, client_error=INVALID_CODE)
    recovery_token = session["access_token"]
    try:
        supabase_auth.update_password(recovery_token, body.new_password)
    except SupabaseAuthError as exc:
        _end_session_quietly(recovery_token, "local")
        _raise(exc)
    _end_session_quietly(recovery_token, "global")
