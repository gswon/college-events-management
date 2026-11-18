import re
from typing import Annotated, Optional

from fastapi import APIRouter, Query
from pydantic import AwareDatetime
from sqlalchemy import and_, delete, func, or_, select, text
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import joinedload

import models
from auth import optional_user_dependency, user_dependency
from database import db_dependency
from errors import APIError
from pagination import decode_cursor, encode_cursor
from schemas import EventDetail, EventListItem, EventSaveIn, EventSaveOut, Page, UserBrief
from timeutil import utc_range

router = APIRouter(tags=["events"])

# InnoDB's default innodb_ft_min_token_size. Shorter words are not in the FULLTEXT index.
FT_MIN_TOKEN = 3
_FT_OPERATORS = re.compile(r'[+\-<>()~*"@]')


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
    # FULLTEXT cannot find words that short, so fall back to word-prefix matches in the title.
    title = models.Event.title
    return and_(
        *(or_(title.startswith(w, autoescape=True), title.contains(f" {w}", autoescape=True)) for w in words)
    )


@router.get("/events", response_model=Page[EventListItem])
def list_events(
    db: db_dependency,
    start: Annotated[AwareDatetime, Query(description="Range start (ISO 8601 with a UTC offset)")],
    end: Annotated[AwareDatetime, Query(description="Range end (ISO 8601 with a UTC offset)")],
    category: Annotated[Optional[str], Query(description="Category code, e.g. CAREER")] = None,
    organization_id: Optional[int] = None,
    q: Annotated[Optional[str], Query(max_length=100)] = None,
    free_only: bool = False,
    followed_only: bool = False,
    cursor: Optional[str] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    start_utc, end_utc = utc_range(start, end)
    if followed_only:
        # Needs the organization follow API (see plan.md). Until then, say so instead of a misleading 401.
        raise APIError(501, "NOT_IMPLEMENTED", "followed_only is not supported yet.")

    Event = models.Event
    stmt = (
        select(Event)
        .options(joinedload(Event.category), joinedload(Event.organization))
        .where(Event.status != "HIDDEN", Event.start_at < end_utc, Event.end_at > start_utc)
    )

    if category is not None:
        category_id = db.scalar(select(models.EventCategory.id).where(models.EventCategory.code == category))
        if category_id is None:
            raise APIError(400, "INVALID_CATEGORY", f"Unknown category: {category}")
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


FRIENDS_GOING_PREVIEW = 3


@router.get("/events/{event_id}", response_model=EventDetail)
def get_event(event_id: int, db: db_dependency, user: optional_user_dependency):
    """Public. A logged-in viewer also gets their own save status and the friends who are going."""
    event = db.scalar(
        select(models.Event)
        .options(joinedload(models.Event.category), joinedload(models.Event.organization))
        .where(models.Event.id == event_id, models.Event.status != "HIDDEN")
    )
    if event is None:
        raise APIError(404, "EVENT_NOT_FOUND", "Event not found.")
    detail = EventDetail.model_validate(event)
    if user is None:
        return detail

    Save, Friendship, User = models.EventSave, models.Friendship, models.User
    detail.my_save_status = db.scalar(select(Save.status).where(Save.user_id == user.id, Save.event_id == event_id))
    # Row (user_id=friend, friend_id=me) holds what that friend shares with me.
    friends_going = (
        select(User)
        .join(Save, Save.user_id == User.id)
        .join(Friendship, and_(Friendship.user_id == User.id, Friendship.friend_id == user.id))
        .where(Save.event_id == event_id, Save.status == "GOING", Friendship.share_event == "DETAILS")
    )
    detail.friends_going_count = db.scalar(select(func.count()).select_from(friends_going.subquery()))
    detail.friends_going = [
        UserBrief.model_validate(friend)
        for friend in db.scalars(friends_going.order_by(User.display_name, User.id).limit(FRIENDS_GOING_PREVIEW))
    ]
    return detail


# --- Save (my calendar) -------------------------------------------------------

@router.put("/events/{event_id}/save", response_model=EventSaveOut)
def save_event(event_id: int, body: EventSaveIn, db: db_dependency, user: user_dependency):
    """Save the event or change its status. Sending the same request twice gives the same result."""
    event = db.get(models.Event, event_id)
    if event is None or event.status == "HIDDEN":
        raise APIError(404, "EVENT_NOT_FOUND", "Event not found.")
    # A cancelled event cannot be newly saved, but an existing save can still change or be removed.
    if event.status == "CANCELLED" and db.get(models.EventSave, (user.id, event_id)) is None:
        raise APIError(409, "EVENT_CANCELLED", "This event was cancelled, so it cannot be saved.")

    # One upsert, so two taps at the same moment cannot collide on the (user_id, event_id) key.
    insert = mysql_insert(models.EventSave).values(user_id=user.id, event_id=event_id, status=body.status)
    db.execute(insert.on_duplicate_key_update(status=insert.inserted.status))
    db.commit()
    return {"event_id": event_id, "status": body.status}


@router.delete("/events/{event_id}/save", status_code=204)
def unsave_event(event_id: int, db: db_dependency, user: user_dependency):
    """Remove the save. Succeeds even if it was not saved, so a double tap is not an error."""
    Save = models.EventSave
    db.execute(delete(Save).where(Save.user_id == user.id, Save.event_id == event_id))
    db.commit()
