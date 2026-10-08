import re
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime
from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session, joinedload

import models
from database import get_db
from errors import APIError
from pagination import decode_cursor, encode_cursor
from schemas import EventDetail, EventListItem, Page

router = APIRouter(tags=["events"])

db_dependency = Annotated[Session, Depends(get_db)]

MAX_RANGE = timedelta(days=92)
# InnoDB FULLTEXT 기본 innodb_ft_min_token_size. 이보다 짧은 단어는 인덱스에 없다.
FT_MIN_TOKEN = 3
_FT_OPERATORS = re.compile(r'[+\-<>()~*"@]')


def _to_utc_naive(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _search_condition(q: str):
    words = _FT_OPERATORS.sub(" ", q).split()
    if not words:
        return None
    tokens = [w for w in words if len(w) >= FT_MIN_TOKEN]
    if tokens:
        boolean_query = " ".join(f"+{w}*" for w in tokens)
        return text("MATCH (events.title, events.description) AGAINST (:ft_q IN BOOLEAN MODE)").bindparams(
            ft_q=boolean_query
        )
    # 짧은 단어만 있으면 FULLTEXT로 못 찾으므로 제목에서 단어 접두어 일치로 대신한다.
    title = models.Event.title
    return and_(
        *(or_(title.startswith(w, autoescape=True), title.contains(f" {w}", autoescape=True)) for w in words)
    )


@router.get("/events", response_model=Page[EventListItem])
def list_events(
    db: db_dependency,
    start: Annotated[AwareDatetime, Query(description="기간 시작 (ISO 8601, 오프셋 필수)")],
    end: Annotated[AwareDatetime, Query(description="기간 끝 (ISO 8601, 오프셋 필수)")],
    category: Annotated[Optional[str], Query(description="카테고리 코드, 예: CAREER")] = None,
    organization_id: Optional[int] = None,
    q: Annotated[Optional[str], Query(max_length=100)] = None,
    free_only: bool = False,
    followed_only: bool = False,
    cursor: Optional[str] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    start_utc, end_utc = _to_utc_naive(start), _to_utc_naive(end)
    if end_utc <= start_utc:
        raise APIError(400, "INVALID_RANGE", "end는 start보다 뒤여야 합니다.")
    if end_utc - start_utc > MAX_RANGE:
        raise APIError(400, "INVALID_RANGE", "조회 기간은 최대 92일입니다.")
    if followed_only:
        # 인증이 붙으면 organization_follows로 필터링한다.
        raise APIError(401, "AUTH_REQUIRED", "followed_only는 로그인이 필요합니다.")

    Event = models.Event
    stmt = (
        select(Event)
        .options(joinedload(Event.category), joinedload(Event.organization))
        .where(Event.status != "HIDDEN", Event.start_at < end_utc, Event.end_at > start_utc)
    )

    if category is not None:
        category_id = db.scalar(select(models.EventCategory.id).where(models.EventCategory.code == category))
        if category_id is None:
            raise APIError(400, "INVALID_CATEGORY", f"알 수 없는 카테고리입니다: {category}")
        stmt = stmt.where(Event.category_id == category_id)
    if organization_id is not None:
        stmt = stmt.where(Event.organization_id == organization_id)
    if free_only:
        stmt = stmt.where(Event.is_free.is_(True))
    search = _search_condition(q) if q else None
    if search is not None:
        stmt = stmt.where(search)
    if cursor:
        cursor_start, cursor_id = decode_cursor(cursor)
        stmt = stmt.where(
            or_(Event.start_at > cursor_start, and_(Event.start_at == cursor_start, Event.id > cursor_id))
        )

    rows = db.scalars(stmt.order_by(Event.start_at, Event.id).limit(limit + 1)).all()
    items = rows[:limit]
    next_cursor = encode_cursor(items[-1].start_at, items[-1].id) if len(rows) > limit else None
    return {"items": items, "next_cursor": next_cursor}


@router.get("/events/{event_id}", response_model=EventDetail)
def get_event(event_id: int, db: db_dependency):
    event = db.scalar(
        select(models.Event)
        .options(joinedload(models.Event.category), joinedload(models.Event.organization))
        .where(models.Event.id == event_id, models.Event.status != "HIDDEN")
    )
    if event is None:
        raise APIError(404, "EVENT_NOT_FOUND", "이벤트를 찾을 수 없습니다.")
    return event
