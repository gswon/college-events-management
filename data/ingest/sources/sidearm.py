"""Sidearm Sports 체육부 사이트 공통 코드. NYU(gonyuathletics.com)와 Princeton(goprincetontigers.com)이 같은 형식이다.

1단계 fetch(): 전 종목 시즌 일정이 담긴 iCal 파일 하나(calendar.ashx/calendar.ics?sport_id=0)를 받아 VEVENT 마다 원본을 만든다.
3단계 normalize(): SUMMARY 문자열을 쪼개서 종목/홈·원정/결과/취소 여부를 뽑는다.

SUMMARY 예시 (학교 이름만 다름)
  "[W] New York University Women's Soccer at Babson College "   ← 끝난 경기 (W/L/T/N)
  "CANCELLED New York University Women's Soccer at William Paterson University"
  "[W] Princeton University Men's Swimming and Diving vs Villanova"
LOCATION 은 '도시, 주[, 경기장]' 모양 ('Princeton, N.J., DeNunzio Pool').
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from icalendar import Calendar

from .. import http
from ..models import Event, FetchResult, Organization, RawItem
from ..textutil import clean_text, fit, fit_url, slugify, to_utc

_UID_RE = re.compile(r"vcal_(\d+)")
_RESULT_RE = re.compile(r"^\s*\[(W|L|T|N)\]\s*")
_CANCELED_RE = re.compile(r"^\s*(CANCEL+ED|POSTPONED)\s+", re.I)


@dataclass(frozen=True)
class Site:
    base_url: str
    school: str              # SUMMARY 에 쓰이는 학교 이름 ('New York University')
    short: str               # 제목에서 학교 이름을 줄인 것 ('NYU')
    home_prefix: str         # 홈 경기 LOCATION 의 시작 ('New York, NY')
    organization: Organization
    matchup_re: re.Pattern = field(init=False, compare=False)

    def __post_init__(self):
        pattern = rf"^{re.escape(self.school)}\s+(?P<sport>.+?)\s+(?P<ha>vs\.?|at)\s+(?P<opp>.+)$"
        object.__setattr__(self, "matchup_re", re.compile(pattern))

    @property
    def ics_url(self) -> str:
        return f"{self.base_url}/calendar.ashx/calendar.ics?sport_id=0"


def _dt_payload(value) -> tuple[str, bool]:
    if isinstance(value, datetime):
        return to_utc(value).isoformat(), False
    return value.isoformat(), True


def fetch(site: Site) -> FetchResult:
    resp = http.get(site.ics_url)
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


def split_location(text: str | None) -> tuple[str | None, str | None]:
    """'New York, NY, John A. Paulson Center' → ('John A. Paulson Center', 'New York, NY')
    'Babson Park, MA' → ('Babson Park, MA', None),  'TBD' → (None, None)
    """
    text = clean_text(text)
    if not text or text.upper() == "TBD":
        return None, None
    parts = [p.strip() for p in text.split(",")]
    if len(parts) >= 3:
        return fit(", ".join(parts[2:]), 255), fit(", ".join(parts[:2]), 255)
    return fit(text, 255), None


def normalize(site: Site, payload: dict) -> Event:
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
    matchup = site.matchup_re.match(summary)
    raw_location = clean_text(payload.get("location"))
    if matchup:
        tags.append(slugify(matchup.group("sport")))
        if matchup.group("ha").startswith("vs"):
            # 'vs' 라도 중립 경기장일 수 있어서, 학교가 있는 도시에서 열리는 경우만 홈으로 본다
            tags.append("home" if raw_location and raw_location.startswith(site.home_prefix) else "neutral")
        else:
            tags.append("away")
    if "scrimmage" in summary.lower():
        tags.append("scrimmage")

    title = summary.replace(site.school, site.short, 1)

    # DESCRIPTION 첫 줄은 SUMMARY 반복이라 버리고, 결과/중계 링크만 남긴다
    desc_lines = [ln.strip() for ln in (payload.get("description") or "").splitlines()[1:] if ln.strip()]
    description = "\n".join(desc_lines) or None

    location_name, address = split_location(payload.get("location"))
    event = Event(
        external_id="",
        title=clean_text(title, 255) or "(제목 없음)",
        category="SPORTS",
        status="CANCELLED" if canceled else "ACTIVE",
        description=description,
        source_url=fit_url(payload.get("url")),
        host_name=site.organization.name,
        organization=site.organization,
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
