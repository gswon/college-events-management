from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime
from sqlalchemy import select
from sqlalchemy.orm import Session, contains_eager, joinedload

import models
from auth import user_dependency
from database import get_db
from errors import APIError
from schemas import BusyItem, CalendarItem, EntryItem, EventItem, UserCalendar
from timeutil import utc_range

router = APIRouter(tags=["calendar"])

db_dependency = Annotated[Session, Depends(get_db)]
StartQuery = Annotated[AwareDatetime, Query(description="기간 시작 (ISO 8601, 오프셋 필수)")]
EndQuery = Annotated[AwareDatetime, Query(description="기간 끝 (ISO 8601, 오프셋 필수)")]

KINDS = ("class", "personal", "event")
OWNER_LEVELS = dict.fromkeys(KINDS, "DETAILS")
LEVEL_RANK = {"HIDDEN": 0, "BUSY": 1, "DETAILS": 2}
MAX_OVERLAY_USERS = 10


def _collect_items(
    db: Session, owner_id: int, start: datetime, end: datetime, levels: dict[str, str], is_owner: bool
) -> list:
    """owner의 기간 내 수업·개인 일정·저장한 이벤트를 캘린더 항목으로 만든다.

    levels: 종류(class/personal/event)별 공유 수준, 빠진 종류는 HIDDEN.
    친구가 볼 때는 일정별 visibility_override로 수준을 더 낮출 수만 있다.
    """
    items = []

    E = models.CalendarEntry
    entry_kinds = [k.upper() for k in ("class", "personal") if levels.get(k, "HIDDEN") != "HIDDEN"]
    if entry_kinds:
        entries = db.scalars(
            select(E).where(E.user_id == owner_id, E.kind.in_(entry_kinds), E.start_at < end, E.end_at > start)
        )
        for e in entries:
            level = levels[e.kind.lower()]
            if not is_owner and e.visibility_override is not None:
                level = min(level, e.visibility_override, key=LEVEL_RANK.get)
            if level == "DETAILS":
                items.append(EntryItem(
                    type=e.kind, id=e.id, title=e.title, start_at=e.start_at, end_at=e.end_at,
                    is_all_day=e.is_all_day, location=e.location,
                ))
            elif level == "BUSY":
                items.append(BusyItem(start_at=e.start_at, end_at=e.end_at))

    event_level = levels.get("event", "HIDDEN")
    if event_level != "HIDDEN":
        S, Ev = models.EventSave, models.Event
        saves = db.scalars(
            select(S)
            .join(S.event)
            .options(contains_eager(S.event).joinedload(Ev.category))
            .where(S.user_id == owner_id, Ev.status != "HIDDEN", Ev.start_at < end, Ev.end_at > start)
        )
        for s in saves:
            ev = s.event
            if event_level == "DETAILS":
                items.append(EventItem(
                    id=ev.id, title=ev.title, start_at=ev.start_at, end_at=ev.end_at, is_all_day=ev.is_all_day,
                    location=ev.location_name, category=ev.category.code, save_status=s.status,
                    is_cancelled=ev.status == "CANCELLED",
                ))
            elif ev.status == "ACTIVE":  # 취소된 이벤트는 바쁜 시간으로 치지 않는다.
                items.append(BusyItem(start_at=ev.start_at, end_at=ev.end_at))

    items.sort(key=lambda item: (item.start_at, item.end_at))
    return items


def _levels_for(db: Session, owner_id: int, viewer: models.User) -> dict[str, str]:
    if owner_id == viewer.id:
        return OWNER_LEVELS
    row = db.get(models.Friendship, (owner_id, viewer.id))  # owner가 viewer에게 공유하는 수준
    if row is None:
        raise APIError(403, "NOT_FRIENDS", "친구의 캘린더만 볼 수 있습니다.")
    return row.levels()


@router.get("/calendar", response_model=list[CalendarItem])
def my_calendar(
    db: db_dependency,
    user: user_dependency,
    start: StartQuery,
    end: EndQuery,
    include: Annotated[str, Query(description="class,personal,event 중 쉼표로 구분")] = ",".join(KINDS),
):
    start_utc, end_utc = utc_range(start, end)
    kinds = {k.strip() for k in include.split(",") if k.strip()}
    if not kinds or not kinds <= set(KINDS):
        raise APIError(400, "INVALID_INCLUDE", "include는 class, personal, event 중에서 골라야 합니다.")
    return _collect_items(db, user.id, start_utc, end_utc, dict.fromkeys(kinds, "DETAILS"), is_owner=True)


@router.get("/users/{user_id}/calendar", response_model=list[CalendarItem])
def user_calendar(user_id: int, db: db_dependency, user: user_dependency, start: StartQuery, end: EndQuery):
    start_utc, end_utc = utc_range(start, end)
    levels = _levels_for(db, user_id, user)
    return _collect_items(db, user_id, start_utc, end_utc, levels, is_owner=user_id == user.id)


@router.get("/calendar/overlay", response_model=list[UserCalendar])
def calendar_overlay(
    db: db_dependency,
    user: user_dependency,
    user_ids: Annotated[str, Query(description="친구 id를 쉼표로 구분, 예: 12,31")],
    start: StartQuery,
    end: EndQuery,
):
    start_utc, end_utc = utc_range(start, end)
    try:
        friend_ids = [int(x) for x in user_ids.split(",") if x.strip()]
    except ValueError:
        raise APIError(400, "INVALID_USER_IDS", "user_ids는 쉼표로 구분한 숫자여야 합니다.")
    ids = list(dict.fromkeys([user.id, *friend_ids]))  # 나를 맨 앞에, 중복 제거
    if len(ids) - 1 > MAX_OVERLAY_USERS:
        raise APIError(400, "INVALID_USER_IDS", f"친구는 최대 {MAX_OVERLAY_USERS}명까지 겹쳐 볼 수 있습니다.")

    # 친구가 아닌 id가 하나라도 있으면 아무것도 조회하기 전에 403.
    levels = {uid: _levels_for(db, uid, user) for uid in ids}
    return [
        {"user_id": uid, "items": _collect_items(db, uid, start_utc, end_utc, lv, is_owner=uid == user.id)}
        for uid, lv in levels.items()
    ]
