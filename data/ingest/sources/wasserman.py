"""Wasserman Center 수집기 (Handshake 이벤트의 공개 미러).

1단계 fetch():
  1) /events/feed/ RSS를 페이지별로 읽어 이벤트 링크 목록을 만든다.
     (RSS의 pubDate는 '게시일'이라 이벤트 날짜로 쓸 수 없다)
  2) 오늘 이후 이벤트만 골라, 각 이벤트 페이지의 .ics 를 받아 정확한 시간/장소를 얻는다.
  원본 payload = {"rss": RSS 항목, "ics": iCal 이벤트}

3단계 normalize(): payload 를 공통 Event 로 바꾼다.

external_id 는 RSS 작성자 칸의 'Handshake #Event:1997298' 에서 뽑은 Handshake 이벤트 ID.
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime

from icalendar import Calendar

from .. import config, http
from ..models import Event, FetchResult, Organization, RawItem
from ..textutil import clean_text, fit_url, looks_online, ny_today, split_location, to_utc

log = logging.getLogger(__name__)

SLUG = "wasserman"
SOURCE = "WASSERMAN"
NAME = "Wasserman Center for Career Dev."
BASE_URL = "https://wasserman.nyu.edu"
FEED_URL = f"{BASE_URL}/events/feed/"
ORGANIZER = "Wasserman Center for Career Development"
ORGANIZATION = Organization(external_id="wasserman", name=ORGANIZER, slug="wasserman",
                            website_url=BASE_URL)

# 게시일이 이보다 오래된 글만 나오는 페이지에 닿으면 페이지 넘기기를 멈춘다.
STOP_WHEN_POSTED_BEFORE_DAYS = 120

NS = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "wp": "com-wordpress:feed-additions:1",
}
_HANDSHAKE_RE = re.compile(r"Handshake\s*#Event:\s*(\d+)")
_URL_DATE_RE = re.compile(r"/events/(\d{4})/(\d{2})/(\d{2})/")
_CANCELED_RE = re.compile(r"^\s*(CANCEL+ED|POSTPONED)\s*[:\-]?\s*", re.I)

_TAG_RULES = {
    "info-session": ("info session", "information session"),
    "career-fair": ("career fair", "job fair", "expo"),
    "workshop": ("workshop", "bootcamp", "training"),
    "networking": ("networking", "coffee chat", "meet & greet", "meet and greet", "reception"),
    "panel": ("panel", "fireside"),
    "hackathon": ("hackathon", "datathon"),
}


def _parse_rss_items(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    items = []
    for node in root.iter("item"):
        def text(tag, ns=None):
            el = node.find(tag, ns) if ns else node.find(tag)
            return el.text.strip() if el is not None and el.text else None

        items.append({
            "title": text("title"),
            "link": text("link"),
            "creator": text("dc:creator", NS),
            "pub_date": text("pubDate"),
            "description": text("description"),
            "content": text("content:encoded", NS),
            "post_id": text("wp:post-id", NS),
        })
    return items


def _event_date_from_url(link: str | None) -> date | None:
    m = _URL_DATE_RE.search(link or "")
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def _ics_value(dt_value) -> tuple[str, bool]:
    """iCal DTSTART/DTEND 값을 (ISO 문자열, 날짜만인지) 로."""
    if isinstance(dt_value, datetime):
        return to_utc(dt_value).isoformat(), False
    return dt_value.isoformat(), True


def _parse_ics(ics_bytes: bytes) -> dict | None:
    cal = Calendar.from_ical(ics_bytes)
    for comp in cal.walk("VEVENT"):
        start_iso, all_day = _ics_value(comp.decoded("DTSTART"))
        end = comp.get("DTEND")
        end_iso = _ics_value(comp.decoded("DTEND"))[0] if end is not None else None
        return {
            "summary": str(comp.get("SUMMARY", "")) or None,
            "location": str(comp.get("LOCATION", "")) or None,
            "description": str(comp.get("DESCRIPTION", "")) or None,
            "dtstart": start_iso,
            "dtend": end_iso,
            "all_day": all_day,
        }
    return None


def _ics_url(link: str) -> str:
    return link.rstrip("/") + ".ics/"


def fetch() -> FetchResult:
    today = ny_today()
    stop_before = datetime.now().astimezone() - timedelta(days=STOP_WHEN_POSTED_BEFORE_DAYS)
    seen: dict[str, RawItem] = {}

    for page in range(1, config.WASSERMAN_MAX_PAGES + 1):
        url = FEED_URL if page == 1 else f"{FEED_URL}?paged={page}"
        resp = http.get(url, allow_404=True)
        if resp is None:
            break
        rss_items = _parse_rss_items(resp.content)
        if not rss_items:
            break

        all_old = True
        for item in rss_items:
            if item["pub_date"]:
                try:
                    if parsedate_to_datetime(item["pub_date"]) >= stop_before:
                        all_old = False
                except (TypeError, ValueError):
                    all_old = False

            event_day = _event_date_from_url(item["link"])
            if event_day is None or event_day < today or not item["link"]:
                continue

            m = _HANDSHAKE_RE.search(item["creator"] or "")
            if m:
                external_id = m.group(1)
            elif item["post_id"]:
                external_id = f"post-{item['post_id']}"
            else:
                external_id = item["link"]
            if external_id in seen:
                continue

            ics = None
            try:
                ics_resp = http.get(_ics_url(item["link"]), allow_404=True)
                if ics_resp is not None:
                    ics = _parse_ics(ics_resp.content)
            except Exception as exc:  # 한 이벤트의 .ics 실패가 전체를 멈추지 않게
                log.warning("ics 받기 실패, RSS 날짜로 대체: %s (%s)", item["link"], exc)

            seen[external_id] = RawItem(
                external_id=external_id,
                payload={"rss": item, "ics": ics, "event_date": event_day.isoformat()},
            )

        if all_old:
            break

    # RSS는 전체 목록이 아니므로(페이지 제한) 사라진 이벤트 자동 취소는 하지 않는다.
    return FetchResult(items=list(seen.values()), complete=False)


def _tags(title: str) -> list[str]:
    lower = title.lower()
    return [tag for tag, words in _TAG_RULES.items() if any(w in lower for w in words)]


def normalize(payload: dict) -> Event:
    rss = payload["rss"]
    ics = payload.get("ics") or {}

    title = clean_text(ics.get("summary") or rss.get("title"), 255) or "(제목 없음)"
    canceled = bool(_CANCELED_RE.match(title))
    title = _CANCELED_RE.sub("", title) or title

    m = _HANDSHAKE_RE.search(rss.get("creator") or "")
    registration_url = f"https://nyu.joinhandshake.com/events/{m.group(1)}" if m else None

    location_name, address = split_location(ics.get("location"))
    is_online = looks_online(ics.get("location")) or looks_online(title)
    if is_online and looks_online(location_name) and not address:
        location_name = None   # 'Virtual' 같은 값은 장소가 아니라 is_online 으로

    event = Event(
        external_id="",
        title=title,
        category="CAREER",
        status="CANCELLED" if canceled else "ACTIVE",
        description=clean_text(rss.get("content") or rss.get("description"), 10000),
        source_url=fit_url(rss.get("link")),
        host_name=ORGANIZER,
        organization=ORGANIZATION,
        location_name=location_name,
        address=address,
        is_online=is_online,
        registration_url=registration_url,
        tags=_tags(title),
    )

    if ics.get("dtstart") and not ics.get("all_day"):
        event.start_at = datetime.fromisoformat(ics["dtstart"])
        event.end_at = datetime.fromisoformat(ics["dtend"]) if ics.get("dtend") else None
    elif ics.get("dtstart"):
        event.is_all_day = True
        event.start_date = date.fromisoformat(ics["dtstart"][:10])
        if ics.get("dtend"):
            # iCal 의 날짜형 DTEND 는 '다음 날'(미포함)이므로 하루 뺀다
            event.end_date = max(event.start_date, date.fromisoformat(ics["dtend"][:10]) - timedelta(days=1))
        else:
            event.end_date = event.start_date
    else:
        # .ics 를 못 받은 경우: URL의 날짜로 종일 이벤트 처리
        event.is_all_day = True
        event.start_date = event.end_date = date.fromisoformat(payload["event_date"])
    return event
