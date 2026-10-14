"""NYU 학사일정 수집기 (NYU Bulletin 의 Academic Calendar 표).

1단계 fetch(): 페이지의 각 학기 제목(h3) 아래 표에서 (날짜, 내용) 줄을 읽는다.
3단계 normalize(): "December 16-22, 2026" 같은 날짜 문자열을 시작/끝 날짜로 바꾼다.

학사일정은 1년에 30~40줄뿐이지만 틀리면 치명적이라 '반자동'을 권장한다:
  python -m ingest.run --source academic --dry-run   # 먼저 결과를 눈으로 확인
  python -m ingest.run --source academic             # 확인 후 저장
고유 ID가 없으므로 (학기 + 날짜 + 내용)의 해시를 external_id 로 쓴다.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import date

from bs4 import BeautifulSoup

from .. import http
from ..models import Event, FetchResult, RawItem
from ..textutil import clean_text, slugify

log = logging.getLogger(__name__)

SLUG = "academic"
SOURCE = "ACADEMIC"
NAME = "NYU Academic Calendar"
BASE_URL = "https://bulletins.nyu.edu/nyu/academic-calendar/"

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}
_WEEKDAY_RE = re.compile(r"\b(mon|tues|wednes|thurs|fri|satur|sun)day,?\s*", re.I)

_SINGLE_RE = re.compile(r"^(?P<m>[a-z]+)\.?\s+(?P<d>\d{1,2}),\s*(?P<y>\d{4})$", re.I)
_SAME_MONTH_RANGE_RE = re.compile(r"^(?P<m>[a-z]+)\.?\s+(?P<d1>\d{1,2})\s*-\s*(?P<d2>\d{1,2}),\s*(?P<y>\d{4})$", re.I)
_CROSS_MONTH_RANGE_RE = re.compile(
    r"^(?P<m1>[a-z]+)\.?\s+(?P<d1>\d{1,2})(?:,\s*(?P<y1>\d{4}))?\s*-\s*"
    r"(?P<m2>[a-z]+)\.?\s+(?P<d2>\d{1,2}),\s*(?P<y2>\d{4})$", re.I)


def fetch() -> FetchResult:
    resp = http.get(BASE_URL)
    soup = BeautifulSoup(resp.content, "html.parser")

    items: list[RawItem] = []
    for heading in soup.find_all("h3"):
        term = clean_text(heading.get_text(" "))
        table = heading.find_next("table")
        # 이 h3 바로 아래 표인지 확인 (다음 h3 의 표를 잘못 잡지 않도록)
        if not term or table is None or table.find_previous("h3") is not heading:
            continue
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 2:
                continue
            date_text = clean_text(cells[0].get_text(" "))
            event_text = clean_text(cells[1].get_text(" "))
            if not date_text or not event_text:
                continue
            key = f"{term}|{date_text}|{event_text}"
            external_id = hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
            items.append(RawItem(external_id=external_id, payload={
                "term": term, "date_text": date_text, "event_text": event_text,
            }))

    if not items:
        raise RuntimeError("학사일정 표를 하나도 찾지 못함 - 페이지 구조가 바뀌었는지 확인 필요")

    # 페이지 전체를 읽었으므로, 페이지에서 사라진(=바뀐) 줄은 취소 처리한다.
    return FetchResult(items=items, complete=True, window_end_utc=None)


def _month(name: str) -> int:
    """'September', 'Sept', 'Sep' 모두 9."""
    key = name.lower()
    for full, num in _MONTHS.items():
        if len(key) >= 3 and full.startswith(key):
            return num
    if key == "sept":
        return 9
    raise ValueError(f"월 이름을 모름: {name}")


def parse_date_range(text: str) -> tuple[date, date]:
    """'September 2, 2026' / 'December 16-22, 2026' / 'December 23, 2026 - January 2, 2027' 등."""
    t = _WEEKDAY_RE.sub("", text)
    t = re.sub(r"\s*[–—-]\s*", " - ", t)   # 여러 종류의 대시를 ' - ' 로 통일
    t = re.sub(r"\s+", " ", t).strip()

    if m := _SINGLE_RE.match(t):
        d = date(int(m["y"]), _month(m["m"]), int(m["d"]))
        return d, d
    if m := _SAME_MONTH_RANGE_RE.match(t):
        month, year = _month(m["m"]), int(m["y"])
        return date(year, month, int(m["d1"])), date(year, month, int(m["d2"]))
    if m := _CROSS_MONTH_RANGE_RE.match(t):
        m1, m2, y2 = _month(m["m1"]), _month(m["m2"]), int(m["y2"])
        y1 = int(m["y1"]) if m["y1"] else (y2 if m1 <= m2 else y2 - 1)
        return date(y1, m1, int(m["d1"])), date(y2, m2, int(m["d2"]))
    raise ValueError(f"날짜 형식을 해석하지 못함: {text!r}")


def _tags(term: str, text: str) -> list[str]:
    lower = text.lower()
    tags = [slugify(term)]
    if "no classes" in lower or "recess" in lower or "break" in lower:
        tags.append("no-classes")
    if "final exam" in lower:
        tags.append("final-exams")
    if "classes begin" in lower:
        tags.append("classes-begin")
    if "classes end" in lower or "last day of" in lower:
        tags.append("classes-end")
    if "legislative day" in lower:
        tags.append("legislative-day")
    return tags


def normalize(payload: dict) -> Event:
    start, end = parse_date_range(payload["date_text"])
    if end < start:
        raise ValueError(f"끝 날짜가 시작보다 빠름: {payload['date_text']!r}")
    return Event(
        external_id="",
        title=clean_text(payload["event_text"], 255) or "(제목 없음)",
        category="ACADEMIC",
        is_all_day=True,
        start_date=start,
        end_date=end,
        source_url=BASE_URL,
        tags=_tags(payload["term"], payload["event_text"]),
    )
