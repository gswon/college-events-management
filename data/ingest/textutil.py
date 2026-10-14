"""텍스트/시간 정리 도우미."""
from __future__ import annotations

import html
import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
UTC = timezone.utc

_TAG_RE = re.compile(r"<[^>]+>")
_BR_RE = re.compile(r"<\s*(br|/p|/li)\s*/?>", re.I)
_SPACES_RE = re.compile(r"[ \t\r\f\v]+")
_NEWLINES_RE = re.compile(r"\n\s*\n+")


def clean_text(value: str | None, max_len: int | None = None) -> str | None:
    """HTML 태그 제거 + &amp; 같은 엔티티 해제 + 공백 정리. 빈 값이면 None."""
    if value is None:
        return None
    text = _BR_RE.sub("\n", str(value))
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    text = _SPACES_RE.sub(" ", text).replace(" ,", ",")
    text = _NEWLINES_RE.sub("\n", text)
    text = "\n".join(line.strip() for line in text.split("\n")).strip()
    if not text:
        return None
    if max_len and len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text


def parse_utc(value: str | None) -> datetime | None:
    """'2026-10-06 21:30:00' (UTC, 시간대 표기 없음) → aware UTC datetime."""
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)


def ny_date(dt_utc: datetime) -> date:
    """UTC 시각을 뉴욕 기준 날짜로."""
    return dt_utc.astimezone(NY).date()


def ny_today() -> date:
    return datetime.now(NY).date()


def to_utc(dt: datetime) -> datetime:
    """aware 면 UTC로 변환, naive 면 뉴욕 현지 시각으로 보고 UTC로 변환."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=NY)
    return dt.astimezone(UTC)


def slugify(value: str) -> str:
    value = html.unescape(value).lower().replace("'", "")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def normalize_tags(values) -> list[str]:
    """태그 목록 정리: 소문자, 앞뒤 공백 제거, 중복 제거, 100자 제한."""
    seen: list[str] = []
    for v in values or []:
        if not v:
            continue
        tag = html.unescape(str(v)).strip().lower()[:100]
        if tag and tag not in seen:
            seen.append(tag)
    return seen


def ny_midnight_utc(day: date) -> datetime:
    """뉴욕 날짜의 자정(00:00 America/New_York)을 aware UTC 로. 종일 이벤트 저장용."""
    return datetime.combine(day, datetime.min.time(), tzinfo=NY).astimezone(UTC)


def fit_url(url: str | None, max_len: int = 500) -> str | None:
    """URL 은 잘라 쓰면 깨지므로, 길면 아예 버린다."""
    url = (url or "").strip()
    return url if url and len(url) <= max_len else None


def fit(value: str | None, max_len: int) -> str | None:
    """이미 정리된 문자열을 컬럼 길이에 맞춘다 (넘치면 … 로 자름)."""
    if not value:
        return None
    return value if len(value) <= max_len else value[: max_len - 1].rstrip() + "…"


_STREET_RE = re.compile(r"^\d+[A-Za-z]?\s+\S")
_ONLINE_RE = re.compile(r"\b(online|virtual|zoom|remote|webinar)\b", re.I)


def split_location(text: str | None) -> tuple[str | None, str | None]:
    """'NYU Kimmel Center, Eisner & Lubin Auditorium, 60 Washington Square South, New York, ...'
    → ('NYU Kimmel Center, Eisner & Lubin Auditorium', '60 Washington Square South, New York, ...').

    번지수로 시작하는 조각부터를 도로명 주소로 본다. 번지수가 없으면 전부 장소 이름.
    """
    text = clean_text(text)
    if not text:
        return None, None
    parts = [p.strip() for p in text.split(",") if p.strip()]
    for i, part in enumerate(parts):
        if _STREET_RE.match(part):
            name = ", ".join(parts[:i]) or None
            return fit(name, 255), fit(", ".join(parts[i:]), 255)
    return fit(", ".join(parts), 255), None


def looks_online(text: str | None) -> bool:
    return bool(text and _ONLINE_RE.search(text))
