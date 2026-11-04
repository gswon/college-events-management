"""요청한 유저 식별.

Authorization: Bearer <access_token> 을 Supabase 공개키(JWKS)로 검증하고,
토큰의 sub(Supabase 유저 UUID)로 users.auth_uid 행을 찾는다.
users 행은 로그인 때 만들어지므로(routers/account.py) 여기서는 찾기만 한다.
"""
from dataclasses import dataclass
from typing import Annotated, Any, Optional

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

import models
import supabase_auth
from database import get_db
from errors import APIError

ALGORITHMS = ["ES256", "RS256"]  # Supabase 비대칭 JWT 서명 키
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
    # 공개키 목록은 PyJWKClient가 캐시하고, 모르는 kid가 오면 다시 받아온다.
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
        raise APIError(401, "AUTH_REQUIRED", "로그인이 필요합니다.")
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
        raise APIError(401, "TOKEN_EXPIRED", "로그인이 만료되었습니다. 토큰을 갱신해 주세요.")
    except jwt.PyJWKClientConnectionError:
        raise APIError(503, "AUTH_UNAVAILABLE", "인증 서버에 연결할 수 없습니다.")
    except jwt.PyJWTError:
        raise APIError(401, "INVALID_TOKEN", "유효하지 않은 토큰입니다.")
    return AccessToken(raw=token, claims=claims)


token_dependency = Annotated[AccessToken, Depends(get_access_token)]


def get_current_user(db: Annotated[Session, Depends(get_db)], token: token_dependency) -> models.User:
    user = db.scalar(select(models.User).where(models.User.auth_uid == token.auth_uid))
    if user is None:
        raise APIError(401, "AUTH_REQUIRED", "로그인이 필요합니다.")
    return user


user_dependency = Annotated[models.User, Depends(get_current_user)]
