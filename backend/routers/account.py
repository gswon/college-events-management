"""Sign up, log in, and passwords (/auth/*, /users/me/password).

Supabase does the authentication itself (supabase_auth.py). This module adds the @nyu.edu rule,
links each Supabase user to a MySQL users row, and turns Supabase errors into API error codes.
"""
import logging
from datetime import datetime
from typing import Any, NoReturn, Optional

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import Session

import models
import supabase_auth
from auth import token_dependency, user_dependency
from database import db_dependency
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

ALLOWED_EMAIL_DOMAIN = "@nyu.edu"

ErrorSpec = tuple[int, str, str]

INVALID_EMAIL_DOMAIN: ErrorSpec = (400, "INVALID_EMAIL_DOMAIN", "Only @nyu.edu email addresses can be used.")
NYU_ACCOUNT_REQUIRED: ErrorSpec = (403, "NYU_ACCOUNT_REQUIRED", "Only @nyu.edu accounts can be used.")
EMAIL_TAKEN: ErrorSpec = (409, "EMAIL_TAKEN", "An account with this email already exists.")
INVALID_CREDENTIALS: ErrorSpec = (401, "INVALID_CREDENTIALS", "Incorrect email or password.")
EMAIL_NOT_VERIFIED: ErrorSpec = (403, "EMAIL_NOT_VERIFIED", "Please verify your email first.")
INVALID_CODE: ErrorSpec = (400, "INVALID_CODE", "The code is wrong or has expired.")
INVALID_REFRESH_TOKEN: ErrorSpec = (401, "INVALID_REFRESH_TOKEN", "Please log in again.")
INVALID_CURRENT_PASSWORD: ErrorSpec = (400, "INVALID_CURRENT_PASSWORD", "Your current password is incorrect.")
RATE_LIMITED: ErrorSpec = (429, "RATE_LIMITED", "Too many requests. Please try again in a moment.")

# Supabase errors that mean the same thing on every endpoint
_COMMON: dict[str, ErrorSpec] = {
    "weak_password": (422, "WEAK_PASSWORD", "The password does not meet the security requirements."),
    "same_password": (400, "SAME_PASSWORD", "The new password must be different from the current one."),
    "email_address_invalid": (400, "INVALID_EMAIL", "Invalid email address."),
    "over_email_send_rate_limit": RATE_LIMITED,
    "over_request_rate_limit": RATE_LIMITED,
}


def _raise(
    exc: SupabaseAuthError,
    overrides: Optional[dict[str, ErrorSpec]] = None,
    client_error: Optional[ErrorSpec] = None,
) -> NoReturn:
    """Raise the API error for a Supabase error.

    overrides: Supabase codes that this endpoint shows differently.
    client_error: the error for any other 4xx (e.g. every failed code check becomes INVALID_CODE).
    """
    spec = (overrides or {}).get(exc.code) or _COMMON.get(exc.code)
    if spec is None and exc.status_code == 429:
        spec = RATE_LIMITED
    if spec is None and client_error is not None and 400 <= exc.status_code < 500:
        spec = client_error
    if spec is not None:
        raise APIError(*spec) from exc
    if exc.code == "unavailable":
        raise APIError(503, "AUTH_UNAVAILABLE", "Cannot reach the authentication server.") from exc
    logger.error("Supabase auth error: %s", exc)
    raise APIError(502, "AUTH_FAILED", "Authentication failed. Please try again.") from exc


def _raise_unless_client_error(exc: SupabaseAuthError) -> None:
    """Treat a 4xx as success (unless rate limited) so the response never reveals whether an account exists."""
    if exc.status_code == 429 or _COMMON.get(exc.code) == RATE_LIMITED or not 400 <= exc.status_code < 500:
        _raise(exc)
    logger.warning("Supabase refused, answering success anyway: %s", exc)


def _end_session_quietly(access_token: str, scope: str) -> None:
    try:
        supabase_auth.sign_out(access_token, scope)
    except SupabaseAuthError as exc:
        logger.warning("Could not end the Supabase session (scope=%s): %s", scope, exc)


def _parse_time(value: str) -> datetime:
    try:
        return to_utc_naive(datetime.fromisoformat(value))
    except ValueError:
        return utc_now()


def _link_user(db: Session, supa_user: dict[str, Any]) -> models.User:
    """Find the users row for a Supabase user, creating it on the first login."""
    uid = supa_user["id"]
    user = db.scalar(select(models.User).where(models.User.auth_uid == uid))
    if user is None:
        email = supa_user["email"].lower()
        # Link by email: a row made before Supabase, or a user deleted in Supabase who signed up again.
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
        # Sign up already requires @nyu.edu; this also stops accounts made another way, e.g. in the dashboard.
        _end_session_quietly(session["access_token"], "global")
        raise APIError(*NYU_ACCOUNT_REQUIRED)
    user = _link_user(db, supa_user)
    return AuthSession(
        access_token=session["access_token"],
        refresh_token=session["refresh_token"],
        expires_in=session["expires_in"],
        user=MeOut.model_validate(user),
    )


# --- Sign up / email verification --------------------------------------------

@router.post("/auth/signup", response_model=SignupOut, status_code=201)
def signup(body: SignupIn):
    """Sign up and email a verification code. The users row is created at the first login after that."""
    if not body.email.endswith(ALLOWED_EMAIL_DOMAIN):
        raise APIError(*INVALID_EMAIL_DOMAIN)
    try:
        result = supabase_auth.sign_up(body.email, body.password, body.display_name)
    except SupabaseAuthError as exc:
        _raise(exc, {"user_already_exists": EMAIL_TAKEN, "email_exists": EMAIL_TAKEN})
    # For an already verified email, Supabase returns a fake user with empty identities instead of an error.
    supa_user = result.get("user") or result
    if supa_user.get("identities") == []:
        raise APIError(*EMAIL_TAKEN)
    return SignupOut(email=body.email)


@router.post("/auth/verify-email", response_model=AuthSession)
def verify_email(body: VerifyEmailIn, db: db_dependency):
    """Verify the email with the emailed code. On success the user is logged in."""
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


# --- Log in / sessions -------------------------------------------------------

@router.post("/auth/login", response_model=AuthSession)
def login(body: LoginIn, db: db_dependency):
    try:
        session = supabase_auth.sign_in(body.email, body.password)
    except SupabaseAuthError as exc:
        _raise(exc, {"invalid_credentials": INVALID_CREDENTIALS, "email_not_confirmed": EMAIL_NOT_VERIFIED})
    return _session_out(db, session)


@router.post("/auth/refresh", response_model=AuthSession)
def refresh(body: RefreshIn, db: db_dependency):
    """Refresh tokens rotate on use, so the client must replace both tokens with the response."""
    try:
        session = supabase_auth.refresh_session(body.refresh_token)
    except SupabaseAuthError as exc:
        _raise(exc, client_error=INVALID_REFRESH_TOKEN)
    return _session_out(db, session)


@router.post("/auth/logout", status_code=204)
def logout(token: token_dependency):
    """End this device's session only. Succeeds even if the session already ended."""
    try:
        supabase_auth.sign_out(token.raw, "local")
    except SupabaseAuthError as exc:
        if not 400 <= exc.status_code < 500:
            _raise(exc)


# --- Passwords ---------------------------------------------------------------

@router.put("/users/me/password", response_model=AuthSession)
def change_password(body: PasswordChangeIn, db: db_dependency, token: token_dependency, user: user_dependency):
    """Check the current password by logging in with it, then change it.

    Every other device is logged out; this device must switch to the tokens in the response.
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
    """Email a reset code. Always answers success, whether or not the account exists."""
    try:
        supabase_auth.send_password_reset(body.email)
    except SupabaseAuthError as exc:
        _raise_unless_client_error(exc)


@router.post("/auth/password/reset", status_code=204)
def reset_password(body: PasswordResetIn):
    """Check the code, change the password, log out every device. The user then logs in with the new password."""
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
