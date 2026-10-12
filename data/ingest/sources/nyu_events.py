"""events.nyu.edu (LiveWhale Calendar) 수집기.

1단계 fetch():  LiveWhale JSON API를 날짜 구간별로 호출해서 원본 이벤트 목록을 만든다.
3단계 normalize(): 원본 하나를 공통 Event 형식으로 바꾼다.

데이터에서 확인된 특이사항
  * 여러 날에 걸친 이벤트는 '날짜마다' 같은 id로 반복해서 나온다 → id 기준으로 하나만 남긴다.
  * 매주 반복(repeats='weekly') 이벤트는 회차마다 따로 저장한다 → id + 시작시각으로 구분.
  * Engage 동아리 이벤트는 다른 부서 그룹 이름으로 한 번 더 올라오기도 한다
    → engage.nyu.edu/event/<번호> 를 기준으로 하나만 남긴다 (태그가 있는 쪽 우선).
  * Wasserman 그룹(gid 109) 이벤트는 Wasserman 수집기가 정본이므로 여기서 뺀다.
  * 같은 이유로 'NYU Athletics' 그룹 경기는 athletics 수집기(iCal)가 정본이라 뺀다.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from .. import config, http
from ..models import Event, FetchResult, Organization, RawItem
from ..textutil import NY, clean_text, fit, fit_url, normalize_tags, ny_date, ny_today, parse_utc, slugify

log = logging.getLogger(__name__)

SLUG = "nyu_events"
SOURCE = "NYU_EVENTS"
NAME = "NYU Events (events.nyu.edu)"
BASE_URL = "https://events.nyu.edu"

# thumbnail, online_url, cost 는 events 의 image_url / online_url / price_text 용
RESPONSE_FIELDS = "location,tags,group_title,event_types,summary,last_modified,cost,thumbnail,online_url"
MAX_PER_REQUEST = 500

ENGAGE_GID = 22
EXCLUDED_GIDS = {109}
EXCLUDED_GROUP_TITLES = {"NYU Athletics"}

_ENGAGE_RE = re.compile(r"engage\.nyu\.edu/event/(\d+)")
_CANCELED_PREFIX_RE = re.compile(r"^\s*CANCEL+ED\s*[:\-]\s*", re.I)
_CAREER_WORDS = ("career", "job", "internship", "networking", "recruit", "resume", "interview")
# 카테고리 판별용 단어 (태그 / 이벤트 종류 / 그룹 이름에서 단어 단위로 찾는다)
_ARTS_RE = re.compile(r"\b(arts?|music|film|cinema|theat(er|re)|dance|concert|exhibit(ion)?|gallery|"
                      r"performance|poetry|opera|jazz)\b", re.I)
_WELLNESS_RE = re.compile(r"\b(wellness|wellbeing|well-being|health|mindful\w*|meditation|yoga|"
                          r"fitness|mental|counseling)\b", re.I)
_ACADEMIC_RE = re.compile(r"\b(lecture|seminar|colloquium|symposium|research|conference|academic|"
                          r"panel discussion|deadlines?|registration)\b", re.I)
_SPORTS_RE = re.compile(r"\b(athletics?|sports?|recreation)\b", re.I)
# 이벤트 종류 중 '누가 올 수 있는지'를 말하는 것만 audience_text 로
_AUDIENCE_RE = re.compile(r"public|student|faculty|staff|alumni|community|grad|undergrad|nyu id|member", re.I)
_IMG_SRC_RE = re.compile(r'src="([^"]+)"')


def _list_url(start, end) -> str:
    return (
        f"{BASE_URL}/live/json/events/start_date/{start.isoformat()}/end_date/{end.isoformat()}"
        f"/max/{MAX_PER_REQUEST}/response_fields/{RESPONSE_FIELDS}"
    )


def _fetch_window(start, end) -> list[dict]:
    """한 날짜 구간을 받아온다. 다음 페이지 링크가 있으면 따라간다."""
    url = _list_url(start, end)
    rows: list[dict] = []
    while url:
        body = http.get(url).json()
        rows.extend(body.get("data") or [])
        url = (body.get("links") or {}).get("next")
    if len(rows) >= MAX_PER_REQUEST:
        log.warning("%s~%s 구간 결과가 %s건으로 상한에 닿음. NYU_EVENTS_CHUNK_DAYS 를 줄이세요.",
                    start, end, len(rows))
    return rows


def _external_id(row: dict) -> str:
    m = _ENGAGE_RE.search(row.get("url") or "")
    base = f"engage-{m.group(1)}" if m else str(row["id"])
    if row.get("repeats"):
        # 반복 이벤트는 회차별로 저장: <id>@<시작 UTC 타임스탬프>
        base = f"{base}@{row.get('date_ts')}"
    return base


def _richness(row: dict) -> int:
    """같은 이벤트가 두 그룹에 올라왔을 때 어느 쪽을 남길지 정하는 점수."""
    score = 0
    if row.get("gid") != ENGAGE_GID:
        score += 2
    if row.get("tags"):
        score += 1
    if row.get("event_types"):
        score += 1
    return score


def fetch() -> FetchResult:
    today = ny_today()
    last_day = today + timedelta(days=config.NYU_EVENTS_DAYS_AHEAD)
    chunk = timedelta(days=max(1, config.NYU_EVENTS_CHUNK_DAYS))

    chosen: dict[str, dict] = {}
    day = today
    while day <= last_day:
        window_end = min(day + chunk, last_day)
        for row in _fetch_window(day, window_end):
            if row.get("gid") in EXCLUDED_GIDS or row.get("group_title") in EXCLUDED_GROUP_TITLES:
                continue
            key = _external_id(row)
            prev = chosen.get(key)
            # 처음 본 것을 남기되(날짜순이라 가장 이른 회차), 같은 이벤트의 더 풍부한 버전이면 교체
            if prev is None or _richness(row) > _richness(prev):
                chosen[key] = row
        day += chunk

    items = [RawItem(external_id=k, payload=v) for k, v in chosen.items()]
    window_end_utc = datetime.combine(last_day, datetime.min.time(), tzinfo=NY).astimezone(timezone.utc)
    return FetchResult(items=items, complete=True, window_end_utc=window_end_utc)


def _category(row: dict, tags: list[str]) -> str:
    """event_categories.code 로 매핑. 먼저 맞는 규칙이 이긴다."""
    if _ENGAGE_RE.search(row.get("url") or ""):
        return "SOCIAL"
    group = str(row.get("group_title") or "")
    haystack = " ".join(tags + [group]).lower()
    if any(w in haystack for w in _CAREER_WORDS):
        return "CAREER"
    if _ARTS_RE.search(haystack):
        return "ARTS"
    if _WELLNESS_RE.search(haystack):
        return "WELLNESS"
    if _SPORTS_RE.search(haystack):
        return "SPORTS"
    if _ACADEMIC_RE.search(haystack):
        return "ACADEMIC"
    return "OTHER"


def _price(row: dict) -> tuple[bool | None, str | None]:
    """(is_free, price_text). cost 칸은 HTML 일 수 있다. 모르면 (None, None)."""
    text = clean_text(row.get("cost"))
    types = [str(t).strip().lower() for t in (row.get("event_types") or [])]
    is_free = None
    if text:
        lower = text.lower()
        if "$" in lower and "free" not in lower:
            is_free = False
        elif lower.startswith("free") or lower in ("no cost", "$0"):
            is_free = True
    if is_free is None and "free" in types:
        is_free = True
    return is_free, fit(text.replace("\n", " ") if text else None, 100)


def _audience(row: dict) -> str | None:
    found = []
    for t in row.get("event_types") or []:
        t = clean_text(t)
        if t and _AUDIENCE_RE.search(t) and t not in found:
            found.append(t)
    return fit(", ".join(found), 255)


def _image_url(row: dict) -> str | None:
    """LiveWhale thumbnail 은 URL 이거나 <img src="..."> 일 수 있다."""
    value = row.get("thumbnail")
    if not value:
        return None
    m = _IMG_SRC_RE.search(str(value))
    return fit_url(m.group(1) if m else str(value))


def _organization(row: dict) -> Organization | None:
    """부서·단체 그룹(gid)을 organizations 에 연결. Engage 는 동아리 이름을 알 수 없어서 NULL."""
    group = clean_text(row.get("group_title"), 255)
    gid = row.get("gid")
    if not group or gid is None or gid == ENGAGE_GID:
        return None
    return Organization(external_id=f"gid-{gid}", name=group, slug=slugify(group) or f"gid-{gid}")


def normalize(row: dict) -> Event:
    canceled = bool(row.get("is_canceled"))
    title = clean_text(row.get("title"), 255) or "(제목 없음)"
    title = _CANCELED_PREFIX_RE.sub("", title) or title

    # 반복 이벤트는 이 회차의 시간, 아니면 이벤트 전체 기간(repeats_start~end)을 쓴다.
    if row.get("repeats"):
        start = parse_utc(row.get("date_utc"))
        end = parse_utc(row.get("date2_utc"))
    else:
        start = parse_utc(row.get("repeats_start") or row.get("date_utc"))
        end = parse_utc(row.get("repeats_end") or row.get("date2_utc"))
    if start is None:
        raise ValueError("시작 시간이 없음")
    if end is not None and end < start:
        end = None

    tags = normalize_tags((row.get("tags") or []) + (row.get("event_types") or []))
    is_free, price_text = _price(row)

    group = clean_text(row.get("group_title"), 200)
    url = fit_url(row.get("url"))
    online_url = fit_url(row.get("online_url"))

    event = Event(
        external_id="",
        title=title,
        category=_category(row, tags),
        status="CANCELLED" if canceled else "ACTIVE",
        description=clean_text(row.get("summary") or row.get("description"), 10000),
        source_url=url,
        host_name=None if group in (None, "NYU Engage") else group,
        organization=_organization(row),
        location_name=clean_text(row.get("location"), 255),
        is_online=bool(row.get("is_online")) or bool(online_url),
        online_url=online_url,
        registration_url=url if url and "joinhandshake.com" in url else None,
        image_url=_image_url(row),
        is_free=is_free,
        price_text=price_text,
        audience_text=_audience(row),
        tags=tags,
    )

    if row.get("is_all_day"):
        event.is_all_day = True
        event.start_date = ny_date(start)
        event.end_date = ny_date(end) if end else event.start_date
        if event.end_date < event.start_date:
            event.end_date = event.start_date
    else:
        event.start_at = start
        event.end_at = end
    return event
