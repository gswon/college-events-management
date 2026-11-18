"""Who is making the request.

Verifies `Authorization: Bearer <access_token>` with Supabase's public keys (JWKS), then finds
the users row whose auth_uid is the token's sub (the Supabase user UUID). Rows are created at
login (routers/account.py), so this module only looks them up.
"""
from dataclasses import dataclass
from typing import Annotated, Any, Optional

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

import models
import supabase_auth
from database import db_dependency
from errors import APIError

ALGORITHMS = ["ES256", "RS256"]  # Supabase's asymmetric JWT signing keys
AUDIENCE = "authenticated"

_bearer = HTTPBearer(auto_error=False)
_jwks_client: Optional[jwt.PyJWKClient] = None


@dataclass
class AccessToken:
    raw: str
    claims: dict[str, Any]

    @property
    def auth_uid(self) -> str:
        return self.claims["sub"]

    @property
    def email(self) -> Optional[str]:
        return self.claims.get("email")


def _signing_key(token: str) -> Any:
    # PyJWKClient caches the key set and fetches it again when a token has an unknown kid.
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(
            f"{supabase_auth.auth_url()}/.well-known/jwks.json",
            headers=supabase_auth.api_headers(),
            lifespan=600,
            timeout=10,
        )
    return _jwks_client.get_signing_key_from_jwt(token).key


def get_access_token(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)],
) -> AccessToken:
    if credentials is None:
        raise APIError(401, "AUTH_REQUIRED", "Please log in.")
    token = credentials.credentials
    try:
        claims = jwt.decode(
            token,
            _signing_key(token),
            algorithms=ALGORITHMS,
            audience=AUDIENCE,
            issuer=supabase_auth.auth_url(),
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
    except jwt.ExpiredSignatureError:
        raise APIError(401, "TOKEN_EXPIRED", "Your session has expired. Refresh the token.")
    except jwt.PyJWKClientConnectionError:
        raise APIError(503, "AUTH_UNAVAILABLE", "Cannot reach the authentication server.")
    except jwt.PyJWTError:
        raise APIError(401, "INVALID_TOKEN", "Invalid token.")
    return AccessToken(raw=token, claims=claims)


token_dependency = Annotated[AccessToken, Depends(get_access_token)]


def get_current_user(db: db_dependency, token: token_dependency) -> models.User:
    user = db.scalar(select(models.User).where(models.User.auth_uid == token.auth_uid))
    if user is None:
        raise APIError(401, "AUTH_REQUIRED", "Please log in.")
    return user


user_dependency = Annotated[models.User, Depends(get_current_user)]


def get_optional_user(
    db: db_dependency,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)],
) -> Optional[models.User]:
    """The current user if a token was sent, or None for an anonymous request.

    For public routes that show more to logged-in users. A token that was sent but is bad is still a 401,
    so the app knows to refresh it instead of silently seeing the anonymous view.
    """
    if credentials is None:
        return None
    return get_current_user(db, get_access_token(credentials))


optional_user_dependency = Annotated[Optional[models.User], Depends(get_optional_user)]
