"""요청 시각(오프셋 포함) → DB용 naive UTC 변환, 기간 조회 검사."""
from datetime import datetime, timedelta, timezone

from errors import APIError

MAX_RANGE = timedelta(days=92)


def to_utc_naive(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_range(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    start_utc, end_utc = to_utc_naive(start), to_utc_naive(end)
    if end_utc <= start_utc:
        raise APIError(400, "INVALID_RANGE", "end는 start보다 뒤여야 합니다.")
    if end_utc - start_utc > MAX_RANGE:
        raise APIError(400, "INVALID_RANGE", "조회 기간은 최대 92일입니다.")
    return start_utc, end_utc
