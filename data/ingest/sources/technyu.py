"""Tech@NYU (techatnyu.org) 수집기.

techatnyu.org 의 Events 메뉴는 Luma 캘린더(luma.com/techatnyu)로 연결된다.
1단계 fetch(): Luma 가 공개로 제공하는 캘린더 구독용 iCal 을 받는다 (과거 + 예정 이벤트 전체).
3단계 normalize(): DESCRIPTION 에서 Luma 링크, 장소(호실), 주최자 줄을 뽑는다.

DESCRIPTION 예시
  Get up-to-date information at: https://luma.com/30c62y79

  Address:
  NYU Global Center for Academic and Spiritual Life
  Room GC 269
  New York, NY
  United States

  Hosted by Charice Huang, Tech@NYU & Pope Cruz

장소를 참가 신청자에게만 공개하는 이벤트는 LOCATION 이 Luma 링크이고 Address 가
'Check event page for more details.' 로 온다 → 장소는 비워 둔다.
STATUS 는 항상 TENTATIVE 라 쓰지 않는다. 취소된 이벤트는 피드에서 빠지므로 cancel_missing 이 처리한다.
"""
from __future__ import annotations

import re
from datetime import datetime

from icalendar import Calendar

from .. import http
from ..models import Event, FetchResult, Organization, RawItem
from ..textutil import clean_text, fit, fit_url, looks_online, split_location, to_utc

SLUG = "technyu"
SOURCE = "TECH_NYU"
COLLEGE = "NYU"
NAME = "Tech@NYU"
BASE_URL = "https://techatnyu.org"
CALENDAR_ID = "cal-VtoEJdCDdRHAJom"
ICS_URL = f"https://api.lu.ma/ics/get?entity=calendar&id={CALENDAR_ID}"
ORGANIZER = "Tech@NYU"
ORGANIZATION = Organization(external_id="techatnyu", name=ORGANIZER, slug="tech-at-nyu",
                            website_url=BASE_URL)

_UID_RE = re.compile(r"^(evt-[A-Za-z0-9]+)")
_LINK_RE = re.compile(r"Get up-to-date information at:\s*(https://\S+)")
_HOSTED_RE = re.compile(r"^Hosted by .+$", re.M)
_HIDDEN_ADDRESS = "check event page"
_CITY_LINE_RE = re.compile(r",\s*(NY|New York)$|^United States$")

_SOCIAL_RE = re.compile(r"\b(social|kickoff|mixer|e-?board|meet the)\b", re.I)


def fetch() -> FetchResult:
    resp = http.get(ICS_URL)
    cal = Calendar.from_ical(resp.content)

    items: list[RawItem] = []
    for comp in cal.walk("VEVENT"):
        uid = str(comp.get("UID", ""))
        m = _UID_RE.match(uid)
        external_id = m.group(1) if m else uid
        if not external_id or comp.get("DTSTART") is None:
            continue
        end = comp.decoded("DTEND") if comp.get("DTEND") is not None else None
        items.append(RawItem(external_id=external_id, payload={
            "uid": uid,
            "summary": str(comp.get("SUMMARY", "")),
            "description": str(comp.get("DESCRIPTION", "")),
            "location": str(comp.get("LOCATION", "")),
            "dtstart": to_utc(comp.decoded("DTSTART")).isoformat(),
            "dtend": to_utc(end).isoformat() if isinstance(end, datetime) else None,
        }))

    # 캘린더 전체가 한 파일에 들어 있다
    return FetchResult(items=items, complete=True, window_end_utc=None)


def start_times() -> list[datetime]:
    """nyu_events 가 Engage 에 다시 올라온 Tech@NYU 행사를 거를 때 쓴다."""
    cal = Calendar.from_ical(http.get(ICS_URL).content)
    return [to_utc(c.decoded("DTSTART")) for c in cal.walk("VEVENT")
            if c.get("DTSTART") is not None and isinstance(c.decoded("DTSTART"), datetime)]


def _address_lines(description: str) -> list[str]:
    """'Address:' 다음 줄부터 빈 줄 전까지."""
    lines = description.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip() == "Address:") + 1
    except StopIteration:
        return []
    block: list[str] = []
    for ln in lines[start:]:
        if not ln.strip():
            break
        block.append(ln.strip())
    return block


def _location(location: str, description: str) -> tuple[str | None, str | None]:
    """(location_name, address).

    LOCATION 'NYU Global Center ..., 238 Thompson St, New York, NY 10012, USA' + Address 블록의 호실 줄
    → ('NYU Global Center ... - Room GC 269', '238 Thompson St, New York, NY 10012, USA')
    """
    location = clean_text(location) or ""
    block = _address_lines(description)
    if not block or _HIDDEN_ADDRESS in block[0].lower():
        block = []
    if location.startswith("https://") and not block:
        return None, None

    name, address = split_location(location) if not location.startswith("https://") else (None, None)
    if block:
        # 번지수가 없는 주소('Washington Square Park, New York, NY 10012, USA')는 통째로 address 로
        if address is None and location and not location.startswith("https://") and location != block[0]:
            address = fit(location, 255)
        name = block[0]
        rooms = [ln for ln in block[1:] if not _CITY_LINE_RE.search(ln)]
        if rooms:
            name = f"{name} - {', '.join(rooms)}"
    return fit(name, 255), address


def _category(title: str) -> str:
    """동아리 친목 행사는 SOCIAL, 나머지(스피커·패널·리크루팅·핵데이·워크숍)는 CAREER."""
    return "SOCIAL" if _SOCIAL_RE.search(title) else "CAREER"


def normalize(payload: dict) -> Event:
    title = clean_text(payload.get("summary"), 255) or "(제목 없음)"
    description = payload.get("description") or ""
    m = _LINK_RE.search(description)
    luma_url = m.group(1) if m else None
    location = payload.get("location") or ""
    if not luma_url and location.startswith("https://luma.com/"):
        luma_url = location

    hosted = _HOSTED_RE.search(description)
    location_name, address = _location(location, description)
    return Event(
        external_id="",
        title=title,
        category=_category(title),
        start_at=datetime.fromisoformat(payload["dtstart"]),
        end_at=datetime.fromisoformat(payload["dtend"]) if payload.get("dtend") else None,
        description=hosted.group(0) if hosted else None,
        source_url=fit_url(luma_url),
        registration_url=fit_url(luma_url),
        host_name=ORGANIZER,
        organization=ORGANIZATION,
        location_name=location_name,
        address=address,
        is_online=looks_online(location_name),
        tags=["tech"],
    )
