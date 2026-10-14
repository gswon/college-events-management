"""NYU Athletics (Sidearm Sports) 수집기.

1단계 fetch(): 전 종목 시즌 일정이 담긴 iCal 파일 하나를 받아 VEVENT 마다 원본을 만든다.
3단계 normalize(): SUMMARY 문자열을 쪼개서 종목/홈·원정/결과/취소 여부를 뽑는다.

SUMMARY 예시
  "[W] New York University Women's Soccer at Babson College "   ← 끝난 경기 (W/L/T/N)
  "CANCELLED New York University Women's Soccer at William Paterson University"
  "New York University Men's Soccer vs University of Chicago (TEAR IT UP!)"
"""
from __future__ import annotations

import html
import logging
import re
from datetime import date, datetime, timedelta

from icalendar import Calendar

from .. import http
from ..models import Event, FetchResult, Organization, RawItem
from ..textutil import clean_text, fit, fit_url, slugify, to_utc

log = logging.getLogger(__name__)

SLUG = "athletics"
SOURCE = "ATHLETICS"
NAME = "NYU Athletics"
BASE_URL = "https://gonyuathletics.com"
ICS_URL = f"{BASE_URL}/calendar.ashx/calendar.ics?sport_id=0"
ORGANIZER = "NYU Athletics"
ORGANIZATION = Organization(external_id="athletics", name=ORGANIZER, slug="nyu-athletics",
                            website_url=BASE_URL)

_UID_RE = re.compile(r"vcal_(\d+)")
_RESULT_RE = re.compile(r"^\s*\[(W|L|T|N)\]\s*")
_CANCELED_RE = re.compile(r"^\s*(CANCEL+ED|POSTPONED)\s+", re.I)
_MATCHUP_RE = re.compile(r"^New York University\s+(?P<sport>.+?)\s+(?P<ha>vs\.?|at)\s+(?P<opp>.+)$")


def _dt_payload(value) -> tuple[str, bool]:
    if isinstance(value, datetime):
        return to_utc(value).isoformat(), False
    return value.isoformat(), True


def fetch() -> FetchResult:
    resp = http.get(ICS_URL)
    cal = Calendar.from_ical(resp.content)

    items: list[RawItem] = []
    for comp in cal.walk("VEVENT"):
        uid = str(comp.get("UID", ""))
        m = _UID_RE.search(uid)
        external_id = m.group(1) if m else uid
        if not external_id:
            continue

        start_iso, all_day = _dt_payload(comp.decoded("DTSTART"))
        end_iso = _dt_payload(comp.decoded("DTEND"))[0] if comp.get("DTEND") is not None else None
        items.append(RawItem(external_id=external_id, payload={
            "uid": uid,
            "summary": str(comp.get("SUMMARY", "")),
            "description": str(comp.get("DESCRIPTION", "")),
            "location": str(comp.get("LOCATION", "")),
            "url": html.unescape(str(comp.get("URL", ""))) or None,
            "dtstart": start_iso,
            "dtend": end_iso,
            "all_day": all_day,
        }))

    # iCal 하나에 시즌 전체가 들어 있으므로 '전체 목록'으로 취급한다.
    return FetchResult(items=items, complete=True, window_end_utc=None)


def _split_location(text: str | None) -> tuple[str | None, str | None]:
    """Sidearm LOCATION 은 '도시, 주[, 경기장]' 모양.
    'New York, NY, John A. Paulson Center' → ('John A. Paulson Center', 'New York, NY')
    'Babson Park, MA' → ('Babson Park, MA', None),  'TBD' → (None, None)
    """
    text = clean_text(text)
    if not text or text.upper() == "TBD":
        return None, None
    parts = [p.strip() for p in text.split(",")]
    if len(parts) >= 3:
        return fit(", ".join(parts[2:]), 255), fit(", ".join(parts[:2]), 255)
    return fit(text, 255), None


def normalize(payload: dict) -> Event:
    summary = (payload.get("summary") or "").strip()

    result = None
    m = _RESULT_RE.match(summary)
    if m:
        result = m.group(1)
        summary = summary[m.end():]

    canceled = bool(_CANCELED_RE.match(summary))
    summary = _CANCELED_RE.sub("", summary).strip()
    summary = re.sub(r"\s{2,}", " ", summary)

    tags: list[str] = []
    matchup = _MATCHUP_RE.match(summary)
    raw_location = clean_text(payload.get("location"))
    if matchup:
        tags.append(slugify(matchup.group("sport")))
        if matchup.group("ha").startswith("vs"):
            # 'vs' 라도 중립 경기장일 수 있어서, 뉴욕에서 열리는 경우만 홈으로 본다
            tags.append("home" if raw_location and raw_location.startswith("New York, NY") else "neutral")
        else:
            tags.append("away")
    if "scrimmage" in summary.lower():
        tags.append("scrimmage")

    title = summary.replace("New York University", "NYU", 1)

    # DESCRIPTION 첫 줄은 SUMMARY 반복이라 버리고, 결과/중계 링크만 남긴다
    desc_lines = [ln.strip() for ln in (payload.get("description") or "").splitlines()[1:] if ln.strip()]
    description = "\n".join(desc_lines) or None

    location_name, address = _split_location(payload.get("location"))
    event = Event(
        external_id="",
        title=clean_text(title, 255) or "(제목 없음)",
        category="SPORTS",
        status="CANCELLED" if canceled else "ACTIVE",
        description=description,
        source_url=fit_url(payload.get("url")),
        host_name=ORGANIZER,
        organization=ORGANIZATION,
        location_name=location_name,
        address=address,
        tags=tags + ([f"result-{result.lower()}"] if result in ("W", "L", "T") else []),
    )

    if payload.get("all_day"):
        event.is_all_day = True
        event.start_date = date.fromisoformat(payload["dtstart"][:10])
        if payload.get("dtend"):
            # 날짜형 DTEND 는 미포함(다음 날) → 하루 빼서 마지막 날로
            event.end_date = max(event.start_date, date.fromisoformat(payload["dtend"][:10]) - timedelta(days=1))
        else:
            event.end_date = event.start_date
    else:
        event.start_at = datetime.fromisoformat(payload["dtstart"])
        event.end_at = datetime.fromisoformat(payload["dtend"]) if payload.get("dtend") else None
    return event
