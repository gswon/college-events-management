"""Convert request times (with offsets) to the naive UTC the DB stores, and check query ranges."""
from datetime import datetime, timedelta, timezone

from errors import APIError

MAX_RANGE = timedelta(days=92)


def to_utc_naive(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_range(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    # A query range must have end > start: an empty range cannot overlap anything.
    # (A calendar entry may end when it starts; see routers/entries.py.)
    start_utc, end_utc = to_utc_naive(start), to_utc_naive(end)
    if end_utc <= start_utc:
        raise APIError(400, "INVALID_RANGE", "end must be after start.")
    if end_utc - start_utc > MAX_RANGE:
        raise APIError(400, "INVALID_RANGE", "The range can be at most 92 days.")
    return start_utc, end_utc
