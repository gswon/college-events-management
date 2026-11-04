"""로그인 (/auth/*). NYU Google 계정(@nyu.edu)으로만 로그인한다.

앱이 Google 로그인으로 받은 ID 토큰을 보내면 Supabase가 검증해 세션을 만든다(supabase_auth.py).
여기서는 @nyu.edu 제한, Supabase 유저 ↔ MySQL users 행 연결, Supabase 에러 → API 에러 코드 변환을 한다.
"""
import logging
from datetime import datetime
from typing import Annotated, Any, NoReturn, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

import models
import supabase_auth
from auth import token_dependency
from database import get_db
from errors import APIError
from schemas import AuthSession, GoogleLoginIn, MeOut, RefreshIn
from supabase_auth import SupabaseAuthError
from timeutil import to_utc_naive, utc_now

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

db_dependency = Annotated[Session, Depends(get_db)]

ALLOWED_EMAIL_DOMAIN = "@nyu.edu"

ErrorSpec = tuple[int, str, str]

INVALID_GOOGLE_TOKEN: ErrorSpec = (401, "INVALID_GOOGLE_TOKEN", "Google 로그인 정보가 유효하지 않습니다. 다시 시도해 주세요.")
INVALID_REFRESH_TOKEN: ErrorSpec = (401, "INVALID_REFRESH_TOKEN", "다시 로그인해 주세요.")
NYU_ACCOUNT_REQUIRED: ErrorSpec = (403, "NYU_ACCOUNT_REQUIRED", "NYU Google 계정(@nyu.edu)으로만 로그인할 수 있습니다.")
RATE_LIMITED: ErrorSpec = (429, "RATE_LIMITED", "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.")
AUTH_UNAVAILABLE: ErrorSpec = (503, "AUTH_UNAVAILABLE", "인증 서버에 연결할 수 없습니다.")
AUTH_FAILED: ErrorSpec = (502, "AUTH_FAILED", "인증 처리 중 오류가 발생했습니다.")


def _raise(exc: SupabaseAuthError, client_error: Optional[ErrorSpec] = None) -> NoReturn:
    """Supabase 에러를 API 에러로 바꿔 던진다. client_error: 나머지 4xx를 한꺼번에 이 에러로."""
    if exc.code == "unavailable":
        raise APIError(*AUTH_UNAVAILABLE) from exc
    if exc.status_code == 429 or exc.code.startswith("over_"):
        raise APIError(*RATE_LIMITED) from exc
    # provider_disabled(대시보드에서 Google이 꺼져 있음)는 설정 문제라 사용자 에러로 돌리지 않는다.
    if client_error is not None and 400 <= exc.status_code < 500 and exc.code != "provider_disabled":
        raise APIError(*client_error) from exc
    logger.error("Supabase auth error: %s", exc)
    raise APIError(*AUTH_FAILED) from exc


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


def _google_profile(supa_user: dict[str, Any], email: str) -> dict[str, Any]:
    """Supabase가 user_metadata에 넣어 주는 Google 프로필(full_name/name, avatar_url/picture)."""
    meta = supa_user.get("user_metadata") or {}
    name = str(meta.get("full_name") or meta.get("name") or "").strip()[:50] or email.split("@")[0][:50]
    picture = meta.get("avatar_url") or meta.get("picture")
    if not isinstance(picture, str) or len(picture) > 500:
        picture = None
    return {"display_name": name, "profile_image_url": picture}


def _link_user(db: Session, supa_user: dict[str, Any]) -> models.User:
    """Supabase 유저에 맞는 users 행을 찾고, 없으면 만든다 (첫 로그인 때).

    이름·사진은 처음 만들 때만 Google 프로필에서 가져오고, 이후에는 덮어쓰지 않는다.
    """
    uid = supa_user["id"]
    user = db.scalar(select(models.User).where(models.User.auth_uid == uid))
    if user is None:
        email = supa_user["email"].lower()
        # Supabase 도입 전에 만든 행(또는 Supabase에서 지웠다 다시 들어온 유저)은 이메일로 연결한다.
        user = db.scalar(select(models.User).where(models.User.email == email))
        if user is None:
            user = models.User(email=email, **_google_profile(supa_user, email))
            db.add(user)
        user.auth_uid = uid
    confirmed_at = supa_user.get("email_confirmed_at")
    if confirmed_at and user.email_verified_at is None:
        user.email_verified_at = _parse_time(confirmed_at)
    db.commit()
    return user


def _session_out(db: Session, session: dict[str, Any]) -> AuthSession:
    supa_user = session["user"]
    email = (supa_user.get("email") or "").lower()
    if not email.endswith(ALLOWED_EMAIL_DOMAIN):
        # NYU 계정이 아니면 방금 만든 세션을 끊어서 토큰이 앱으로 나가지 않게 한다.
        # refresh에서도 같은 검사를 하므로, Supabase를 직접 호출해 얻은 세션도 여기서 막힌다.
        _end_session_quietly(session["access_token"], "global")
        raise APIError(*NYU_ACCOUNT_REQUIRED)
    user = _link_user(db, supa_user)
    return AuthSession(
        access_token=session["access_token"],
        refresh_token=session["refresh_token"],
        expires_in=session["expires_in"],
        user=MeOut.model_validate(user),
    )


@router.post("/auth/google", response_model=AuthSession)
def google_login(body: GoogleLoginIn, db: db_dependency):
    """앱이 Google 로그인으로 받은 ID 토큰으로 로그인한다. 첫 로그인이면 users 행을 만든다."""
    try:
        session = supabase_auth.sign_in_with_id_token("google", body.id_token, body.nonce)
    except SupabaseAuthError as exc:
        _raise(exc, client_error=INVALID_GOOGLE_TOKEN)
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
