"""Princeton University 행사 캘린더 (princeton.edu/events) 수집기.

princeton.edu 의 행사 페이지·검색은 Cloudflare 봇 확인이 걸려 있어서 (우회하지 않는다) 공개 피드 두 개만 쓴다.
  https://www.princeton.edu/feed/events.ics  — 시작·끝 시각, 장소, 원래 행사 페이지 URL (설명은 잘려 있음)
  https://www.princeton.edu/feed/events      — 같은 행사의 RSS. 설명 전문과 princeton.edu 행사 페이지 링크
둘 다 앞으로 약 3주 동안의 행사 200건 (날짜순)이다. 페이지 넘기기는 robots.txt 가 막아 둠(?page=).

1단계 fetch(): iCal 의 VEVENT 마다 원본 하나. RSS 설명을 노드 번호 + 시작 시각으로 붙인다.
  external_id = iCal UID ('338051-0' = Drupal 노드 번호-회차). 매일 열리는 전시는 날마다 노드가 따로 있다.
  체육 경기(URL 이 goprincetontigers.com)는 princeton_athletics 가 정본이라 뺀다.
3단계 normalize(): 피드에 카테고리가 없어서, 제목 키워드(categorize.py)와 주최 사이트 주소(URL 호스트)로 분류한다 (_category).
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, time, timedelta
from urllib.parse import urlparse

from icalendar import Calendar

from .. import http
from ..categorize import from_title
from ..models import Event, FetchResult, Organization, RawItem
from ..textutil import NY, clean_text, fit, fit_url, looks_online, to_utc

log = logging.getLogger(__name__)

SLUG = "princeton_events"
SOURCE = "PRINCETON_EVENTS"
COLLEGE = "PRINCETON"
NAME = "Princeton University Events"
BASE_URL = "https://www.princeton.edu"
ICS_URL = f"{BASE_URL}/feed/events.ics"
RSS_URL = f"{BASE_URL}/feed/events"

ATHLETICS_HOST = "goprincetontigers.com"

# 주최 사이트 → (organizations.external_id, 이름, 제목으로 못 정할 때의 카테고리)
HOSTS: dict[str, tuple[str, str, str | None]] = {
    "arts.princeton.edu":         ("lewis-center-arts", "Lewis Center for the Arts", "ARTS"),
    "music.princeton.edu":        ("music", "Department of Music", "ARTS"),
    "artmuseum.princeton.edu":    ("art-museum", "Princeton University Art Museum", "ARTS"),
    "mccarter.org":               ("mccarter", "McCarter Theatre Center", "ARTS"),
    "libcal.princeton.edu":       ("library", "Princeton University Library", "ACADEMIC"),
    "library.princeton.edu":      ("library", "Princeton University Library", "ACADEMIC"),
    "mcgraw.princeton.edu":       ("mcgraw", "McGraw Center for Teaching and Learning", "ACADEMIC"),
    "careerdevelopment.princeton.edu": ("career-development", "Center for Career Development", "CAREER"),
    "uhs.princeton.edu":          ("uhs", "University Health Services", "WELLNESS"),
    "umatter.princeton.edu":      ("umatter", "UMatter", "WELLNESS"),
    "campusrec.princeton.edu":    ("campus-rec", "Campus Recreation", "WELLNESS"),
}


_INVITE_ONLY = re.compile(r"^invite only$", re.I)
# '185 Nassau Street' 같은 도로명만 주소로 본다. '100 Grand Hall', '002 Auditorium' 은 강의실 번호.
_STREET_RE = re.compile(r"^\d+[A-Za-z]?\s+.*\b(street|st|avenue|ave|road|rd|lane|ln|place|pl|boulevard|blvd|way|drive|dr)\.?$",
                        re.I)
# RSS 설명은 HTML 태그를 지우면서 문단이 붙어 버린다 ('...complex.Site follows') → 문장 끝 뒤에 줄바꿈
_GLUED_RE = re.compile(r"([a-z0-9)][.!?])(?=[A-Z][a-z])")


def _host(url: str | None) -> str:
    return (urlparse(url or "").netloc or "").lower().removeprefix("www.") if url else ""


def _node(uid: str) -> str:
    return uid.split("-", 1)[0]


def _rss_descriptions(xml: bytes) -> dict[str, dict]:
    """RSS guid '338051-1794661200' (노드-시작 시각 유닉스초) → {'description', 'link'}."""
    out: dict[str, dict] = {}
    for item in ET.fromstring(xml).iter("item"):
        guid = (item.findtext("guid") or "").strip()
        if guid:
            out[guid] = {"description": item.findtext("description"), "link": item.findtext("link")}
    return out


def fetch() -> FetchResult:
    cal = Calendar.from_ical(http.get(ICS_URL).content)
    try:
        rss = _rss_descriptions(http.get(RSS_URL).content)
    except Exception as exc:  # 설명이 없어도 행사 자체는 저장한다
        log.warning("RSS 받기 실패, 잘린 iCal 설명을 씀: %s", exc)
        rss = {}

    items: list[RawItem] = []
    dropped_athletics = 0
    for comp in cal.walk("VEVENT"):
        uid = str(comp.get("UID", "")).strip()
        if not uid or comp.get("DTSTART") is None:
            continue
        url = str(comp.get("URL", "")).strip() or None
        if _host(url) == ATHLETICS_HOST:
            dropped_athletics += 1
            continue
        start = to_utc(comp.decoded("DTSTART"))
        end = to_utc(comp.decoded("DTEND")) if comp.get("DTEND") is not None else None
        extra = rss.get(f"{_node(uid)}-{int(start.timestamp())}") or {}
        items.append(RawItem(external_id=uid, payload={
            "uid": uid,
            "summary": str(comp.get("SUMMARY", "")),
            "location": str(comp.get("LOCATION", "")),
            "url": url,
            "dtstart": start.isoformat(),
            "dtend": end.isoformat() if end else None,
            "ics_description": str(comp.get("DESCRIPTION", "")),
            "description": extra.get("description"),
            "event_page": extra.get("link"),
        }))
    if dropped_athletics:
        log.info("체육 경기 %d건은 princeton_athletics 가 정본이라 제외", dropped_athletics)

    # 피드 = 앞으로의 행사를 날짜순으로 200건. 마지막 행사 시각 이전 구간은 '전체 목록'이라
    # 거기서 사라진 행사는 취소된 것으로 본다. 그 뒤는 피드에 아직 안 들어온 것일 수 있어 건드리지 않는다.
    starts = [datetime.fromisoformat(i.payload["dtstart"]) for i in items]
    return FetchResult(items=items, complete=bool(items), window_end_utc=max(starts) if starts else None)


def _category(title: str, host: str) -> str:
    """제목 키워드(categorize.py, NYU 와 공통) → 주최 사이트 → 학과 사이트면 ACADEMIC → OTHER.
    단, 예술 사이트(arts./music./artmuseum.)는 제목이 SOCIAL·ACADEMIC 이어도 ARTS."""
    by_title = from_title(title)
    fixed = HOSTS.get(host, (None, None, None))[2]
    # 예술 학과·미술관 사이트의 행사는 제목에 colloquium·ceremony 가 있어도 예술 행사
    if fixed == "ARTS" and by_title in ("SOCIAL", "ACADEMIC", None):
        return "ARTS"
    if by_title:
        return by_title
    if fixed:
        return fixed
    # 학과·연구소 사이트(xxx.princeton.edu)에서 온 행사는 대부분 강연·세미나
    if host.endswith(".princeton.edu"):
        return "ACADEMIC"
    return "OTHER"


def _split_location(text: str | None) -> tuple[str | None, str | None]:
    """'Hagan Gallery, 185 Nassau Street' → ('Hagan Gallery', '185 Nassau Street')
    'Art Museum, 100 Grand Hall' → ('Art Museum, 100 Grand Hall', None)"""
    if not text:
        return None, None
    parts = [p.strip() for p in text.split(",") if p.strip()]
    for i, part in enumerate(parts):
        if _STREET_RE.match(part):
            return fit(", ".join(parts[:i]) or None, 255), fit(", ".join(parts[i:]), 255)
    return fit(", ".join(parts), 255), None


def _organization(host: str) -> Organization | None:
    known = HOSTS.get(host)
    if known:
        ext, name, _ = known
        return Organization(external_id=ext, name=name, slug=f"princeton-{ext}", website_url=f"https://{host}")
    return None


def _all_day_span(start: datetime, end: datetime | None):
    """휴일 같은 종일 행사는 '뉴욕 자정 ~ 마지막 날 23:45(또는 다음 날 자정)' 으로 온다 → (첫날, 마지막 날)."""
    s, e = start.astimezone(NY), end.astimezone(NY) if end else None
    if s.time() != time(0, 0) or e is None:
        return None
    if e.time() == time(0, 0) and e.date() > s.date():
        return s.date(), e.date() - timedelta(days=1)
    if e.time() >= time(23, 45):
        return s.date(), e.date()
    return None


def normalize(payload: dict) -> Event:
    title = clean_text(payload.get("summary"), 255) or "(제목 없음)"
    url = payload.get("url")
    host = _host(url)

    description = clean_text(_GLUED_RE.sub(r"\1\n", payload.get("description") or "")) \
        or clean_text(payload.get("ics_description"))
    if description and description.rstrip(" .…") == title.rstrip(" .…"):
        description = None  # 제목만 반복한 설명

    raw_location = clean_text(payload.get("location"))
    audience = None
    if raw_location and _INVITE_ONLY.match(raw_location):
        raw_location, audience = None, "Invite only"
    is_online = looks_online(raw_location)
    location_name, address = _split_location(raw_location)

    org = _organization(host)
    event = Event(
        external_id="",
        title=title,
        category=_category(title, host),
        description=fit(description, 10000),
        # 원래 행사 페이지 (학과 사이트). 없으면 princeton.edu 행사 페이지
        source_url=fit_url(url) or fit_url(payload.get("event_page")),
        host_name=org.name if org else None,
        organization=org,
        location_name=location_name,
        address=address,
        is_online=is_online,
        audience_text=audience,
        tags=[t for t in (host,) if t],
        start_at=datetime.fromisoformat(payload["dtstart"]),
        end_at=datetime.fromisoformat(payload["dtend"]) if payload.get("dtend") else None,
    )
    if event.end_at and event.end_at < event.start_at:
        event.end_at = None
    span = _all_day_span(event.start_at, event.end_at)
    if span:
        event.is_all_day, (event.start_date, event.end_date) = True, span
        event.start_at = event.end_at = None
    return event
