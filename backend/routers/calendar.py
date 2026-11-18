from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import AwareDatetime
from sqlalchemy import select
from sqlalchemy.orm import Session, contains_eager, joinedload

import models
from auth import user_dependency
from database import db_dependency
from errors import APIError
from schemas import BusyItem, CalendarItem, EntryItem, EventItem, UserCalendar
from timeutil import utc_range

router = APIRouter(tags=["calendar"])

StartQuery = Annotated[AwareDatetime, Query(description="Range start (ISO 8601 with a UTC offset)")]
EndQuery = Annotated[AwareDatetime, Query(description="Range end (ISO 8601 with a UTC offset)")]

KINDS = ("class", "personal", "event")
OWNER_LEVELS = dict.fromkeys(KINDS, "DETAILS")
LEVEL_RANK = {level: rank for rank, level in enumerate(models.SHARE_LEVELS)}  # higher = more visible
MAX_OVERLAY_USERS = 10

# owner id -> {"class" | "personal" | "event": share level}. A missing kind means HIDDEN.
LevelsByOwner = dict[int, dict[str, str]]


def _levels_by_owner(db: Session, owner_ids: list[int], viewer: models.User) -> LevelsByOwner:
    """Share levels each owner gives the viewer, in owner_ids order. One query for all friends.

    Raises 403 before anything is read if any owner is not the viewer's friend.
    """
    others = [owner_id for owner_id in owner_ids if owner_id != viewer.id]
    friend_levels = {}
    if others:
        Friendship = models.Friendship
        # Row (user_id=owner, friend_id=viewer) holds what the owner shares with the viewer.
        rows = db.scalars(
            select(Friendship).where(Friendship.user_id.in_(others), Friendship.friend_id == viewer.id)
        )
        friend_levels = {row.user_id: row.levels() for row in rows}
        if len(friend_levels) != len(others):
            raise APIError(403, "NOT_FRIENDS", "You can only view a friend's calendar.")
    return {
        owner_id: OWNER_LEVELS if owner_id == viewer.id else friend_levels[owner_id]
        for owner_id in owner_ids
    }


def _entry_items(
    db: Session, levels: LevelsByOwner, start: datetime, end: datetime, viewer_id: int
) -> dict[int, list]:
    """Classes and personal entries in the range, as calendar items per owner."""
    visible_kinds = {
        owner_id: {kind.upper() for kind in ("class", "personal") if owner_levels.get(kind, "HIDDEN") != "HIDDEN"}
        for owner_id, owner_levels in levels.items()
    }
    owner_ids = [owner_id for owner_id, kinds in visible_kinds.items() if kinds]
    if not owner_ids:
        return {}

    Entry = models.CalendarEntry
    entries = db.scalars(
        select(Entry).where(Entry.user_id.in_(owner_ids), Entry.start_at < end, Entry.end_at > start)
    )
    items: dict[int, list] = {}
    for entry in entries:
        if entry.kind not in visible_kinds[entry.user_id]:
            continue
        level = levels[entry.user_id][entry.kind.lower()]
        # A friend's per-entry override can only lower the level, and never applies to the owner.
        if entry.user_id != viewer_id and entry.visibility_override is not None:
            level = min(level, entry.visibility_override, key=LEVEL_RANK.get)
        if level == "DETAILS":
            item = EntryItem(
                type=entry.kind, id=entry.id, title=entry.title, start_at=entry.start_at, end_at=entry.end_at,
                is_all_day=entry.is_all_day, location=entry.location,
            )
        elif level == "BUSY":
            item = BusyItem(start_at=entry.start_at, end_at=entry.end_at)
        else:
            continue
        items.setdefault(entry.user_id, []).append(item)
    return items


def _event_items(db: Session, levels: LevelsByOwner, start: datetime, end: datetime) -> dict[int, list]:
    """Saved school events in the range, as calendar items per owner."""
    owner_ids = [
        owner_id for owner_id, owner_levels in levels.items() if owner_levels.get("event", "HIDDEN") != "HIDDEN"
    ]
    if not owner_ids:
        return {}

    Save, Event = models.EventSave, models.Event
    saves = db.scalars(
        select(Save)
        .join(Save.event)
        .options(contains_eager(Save.event).joinedload(Event.category))
        .where(Save.user_id.in_(owner_ids), Event.status != "HIDDEN", Event.start_at < end, Event.end_at > start)
    )
    items: dict[int, list] = {}
    for save in saves:
        event = save.event
        if levels[save.user_id]["event"] == "DETAILS":
            item = EventItem(
                id=event.id, title=event.title, start_at=event.start_at, end_at=event.end_at,
                is_all_day=event.is_all_day, location=event.location_name, category=event.category.code,
                save_status=save.status, is_cancelled=event.status == "CANCELLED",
            )
        elif event.status == "ACTIVE":  # A cancelled event does not make the owner busy.
            item = BusyItem(start_at=event.start_at, end_at=event.end_at)
        else:
            continue
        items.setdefault(save.user_id, []).append(item)
    return items


def _calendars(
    db: Session, levels: LevelsByOwner, start: datetime, end: datetime, viewer_id: int
) -> dict[int, list]:
    """Each owner's calendar items, sorted by time. Two queries no matter how many owners."""
    calendars = {owner_id: [] for owner_id in levels}
    for items_by_owner in (_entry_items(db, levels, start, end, viewer_id), _event_items(db, levels, start, end)):
        for owner_id, items in items_by_owner.items():
            calendars[owner_id].extend(items)
    for items in calendars.values():
        items.sort(key=lambda item: (item.start_at, item.end_at))
    return calendars


@router.get("/calendar", response_model=list[CalendarItem])
def my_calendar(
    db: db_dependency,
    user: user_dependency,
    start: StartQuery,
    end: EndQuery,
    include: Annotated[str, Query(description="Comma-separated: class, personal, event")] = ",".join(KINDS),
):
    start_utc, end_utc = utc_range(start, end)
    kinds = {k.strip() for k in include.split(",") if k.strip()}
    if not kinds or not kinds <= set(KINDS):
        raise APIError(400, "INVALID_INCLUDE", "include must list only class, personal, event.")
    levels = {user.id: dict.fromkeys(kinds, "DETAILS")}
    return _calendars(db, levels, start_utc, end_utc, user.id)[user.id]


@router.get("/users/{user_id}/calendar", response_model=list[CalendarItem])
def user_calendar(user_id: int, db: db_dependency, user: user_dependency, start: StartQuery, end: EndQuery):
    start_utc, end_utc = utc_range(start, end)
    levels = _levels_by_owner(db, [user_id], user)
    return _calendars(db, levels, start_utc, end_utc, user.id)[user_id]


@router.get("/calendar/overlay", response_model=list[UserCalendar])
def calendar_overlay(
    db: db_dependency,
    user: user_dependency,
    user_ids: Annotated[str, Query(description="Comma-separated friend ids, e.g. 12,31")],
    start: StartQuery,
    end: EndQuery,
):
    start_utc, end_utc = utc_range(start, end)
    try:
        friend_ids = [int(x) for x in user_ids.split(",") if x.strip()]
    except ValueError:
        raise APIError(400, "INVALID_USER_IDS", "user_ids must be comma-separated numbers.")
    ids = list(dict.fromkeys([user.id, *friend_ids]))  # Me first, duplicates removed
    if len(ids) - 1 > MAX_OVERLAY_USERS:
        raise APIError(400, "INVALID_USER_IDS", f"You can overlay at most {MAX_OVERLAY_USERS} friends.")

    levels = _levels_by_owner(db, ids, user)
    calendars = _calendars(db, levels, start_utc, end_utc, user.id)
    return [{"user_id": owner_id, "items": calendars[owner_id]} for owner_id in ids]
