"""요청한 유저 식별.

JWT 로그인(/auth/*)이 붙기 전까지는 개발용으로 X-User-Id 헤더의 유저를 현재 유저로 본다.
아무나 다른 유저 행세를 할 수 있으므로 이 상태로 배포하면 안 된다.
로그인이 붙으면 get_current_user만 Authorization: Bearer 토큰 검증으로 바꾸면 된다.
"""
from typing import Annotated, Optional

from fastapi import Depends, Header
from sqlalchemy.orm import Session

import models
from database import get_db
from errors import APIError


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    x_user_id: Annotated[Optional[int], Header()] = None,
) -> models.User:
    user = db.get(models.User, x_user_id) if x_user_id is not None else None
    if user is None:
        raise APIError(401, "AUTH_REQUIRED", "로그인이 필요합니다.")
    return user


user_dependency = Annotated[models.User, Depends(get_current_user)]
