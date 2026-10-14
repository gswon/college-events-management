"""1단계(받기) + 3단계(변환)를 소스별로 확인한다. DB 없이 돌아간다."""
from datetime import date, datetime, timedelta, timezone

import pytest

from ingest.sources import academic, athletics, nyu_events, wasserman
from ingest.sources.academic import parse_date_range

UTC = timezone.utc


def _by_id(result):
    return {item.external_id: item for item in result.items}


def _normalize(module, item):
    event = module.normalize(item.payload)
    event.external_id = item.external_id
    event.validate()
    return event


def test_nyu_events_dedupe_and_exclusions(web):
    items = _by_id(nyu_events.fetch())

    assert "401630" not in items                # Wasserman 그룹(gid 109)은 제외
    assert "engage-12827082" in items           # 두 그룹에 올라온 Engage 이벤트는 하나로
    assert items["engage-12827082"].payload["gid"] == 257   # 태그 있는 쪽을 남김
    assert "404084@1791316800" in items         # 매주 반복 이벤트는 회차 단위 ID
    # 같은 날짜 구간을 두 번 받아도(청크 2개) 중복 없이 하나씩만
    assert sum(1 for k in items if k.startswith("403833")) == 1


def test_nyu_events_normalize_cases(web):
    items = _by_id(nyu_events.fetch())

    ifa = _normalize(nyu_events, items["engage-12252581"])
    assert ifa.status == "CANCELLED"
    assert ifa.title == "3rd IFA General Meeting"
    assert ifa.category == "SOCIAL" and ifa.organization is None and ifa.host_name is None

    quantum = _normalize(nyu_events, items["403833"])
    assert quantum.is_all_day and quantum.start_at is None
    assert (quantum.start_date, quantum.end_date) == (date(2026, 10, 5), date(2026, 10, 6))
    # 종일 이벤트 → 뉴욕 자정 기준 UTC (EDT = UTC-4), end_at 은 마지막 날 다음 날 자정
    assert quantum.resolve_times() == (datetime(2026, 10, 5, 4, 0, tzinfo=UTC),
                                       datetime(2026, 10, 7, 4, 0, tzinfo=UTC))
    assert quantum.category == "ACADEMIC"
    assert quantum.organization.external_id == "gid-348"
    assert quantum.host_name == "The Office of Global Science and Technology"
    assert quantum.is_free is False and quantum.price_text == "Industry Registration Fee: $500"
    assert quantum.audience_text == "Open to the Public"

    karaoke = _normalize(nyu_events, items["engage-12713554"])
    assert karaoke.title == "BSB Guess-the-Song & Karaoke Night"
    assert karaoke.start_at == datetime(2026, 10, 6, 22, 0, tzinfo=UTC)
    assert karaoke.end_at == datetime(2026, 10, 6, 23, 0, tzinfo=UTC)
    assert karaoke.location_name == "Kimmel, LGBTQ+ Center, 6th Fl"

    ogs = _normalize(nyu_events, items["405921"])
    assert ogs.category == "CAREER" and ogs.is_free is True
    assert ogs.registration_url == "https://app.joinhandshake.com/edu/events/1964706"

    online = _normalize(nyu_events, items["407309"])
    assert online.is_online and online.location_name is None and online.end_at is None
    # 종료 시각이 없으면 +1시간 (명세)
    start_at, end_at = online.resolve_times()
    assert end_at - start_at == timedelta(hours=1)
    assert online.description == "A conversation about Renaissance Rome & its music."
    assert online.category == "ARTS"
    assert online.audience_text == "Open to the Public"

    weekly = _normalize(nyu_events, items["404084@1791316800"])
    assert weekly.start_at == datetime(2026, 10, 6, 20, 0, tzinfo=UTC)  # 회차 시간 (시리즈 시작 아님)
    assert weekly.audience_text == "Open to the Public, Students"

    pets = _normalize(nyu_events, items["401373"])
    assert (pets.start_date, pets.end_date) == (date(2026, 9, 1), date(2026, 11, 1))
    assert pets.category == "OTHER"

    nest = _normalize(nyu_events, items["engage-12827082"])  # Engage 링크지만 부서 그룹에 올라온 것
    assert nest.category == "SOCIAL" and nest.is_free is True
    assert nest.organization.name == "Student Wellbeing Initiatives"


def test_wasserman_fetch_and_normalize(web):
    result = wasserman.fetch()
    items = _by_id(result)

    assert result.complete is False
    assert set(items) == {"1997298", "2031864"}      # 지난 이벤트(9/1)는 건너뜀
    assert not any("old-event-already-over" in u for u in web.requested)

    ubs = _normalize(wasserman, items["1997298"])
    assert ubs.start_at == datetime(2026, 10, 7, 16, 0, tzinfo=UTC)
    assert ubs.end_at == datetime(2026, 10, 7, 18, 0, tzinfo=UTC)
    assert ubs.location_name == "NYU Kimmel Center, Eisner & Lubin Auditorium"
    assert ubs.address == "60 Washington Square South, New York, New York 10012, United States"
    assert ubs.registration_url == "https://nyu.joinhandshake.com/events/1997298"
    assert ubs.category == "CAREER" and "info-session" in ubs.tags
    assert ubs.organization.slug == "wasserman" and ubs.is_online is False

    # .ics 가 없는 이벤트는 URL 날짜로 종일 처리
    roth = _normalize(wasserman, items["2031864"])
    assert roth.is_all_day and roth.start_date == date(2026, 10, 20)
    assert roth.title == "Rothschild & Co | Corporate Presentation & Networking Event at NYU"
    assert "networking" in roth.tags


def test_athletics_fetch_and_normalize(web):
    result = athletics.fetch()
    items = _by_id(result)
    assert result.complete is True
    assert set(items) == {"14700", "14707", "14651", "14675", "14734"}

    babson = _normalize(athletics, items["14700"])
    assert babson.title == "NYU Women's Soccer at Babson College"
    assert "away" in babson.tags and "result-w" in babson.tags and "womens-soccer" in babson.tags
    assert babson.description.startswith("W 1-0")
    assert babson.source_url == "https://gonyuathletics.com/calendar.aspx?game_id=14700&sport_id=14"
    assert babson.category == "SPORTS" and babson.location_name == "Babson Park, MA"

    canceled = _normalize(athletics, items["14707"])
    assert canceled.status == "CANCELLED" and canceled.title.startswith("NYU Women's Soccer at")

    home = _normalize(athletics, items["14651"])
    assert "home" in home.tags
    assert (home.location_name, home.address) == ("John A. Paulson Center", "New York, NY")

    neutral = _normalize(athletics, items["14675"])      # 'vs' 지만 뉴저지 경기장
    assert "neutral" in neutral.tags

    ncaa = _normalize(athletics, items["14734"])
    assert ncaa.is_all_day and ncaa.start_date == ncaa.end_date == date(2026, 11, 13)
    assert ncaa.location_name is None                     # 'TBD'
    # 11월 13일은 EST (UTC-5)
    assert ncaa.resolve_times() == (datetime(2026, 11, 13, 5, 0, tzinfo=UTC),
                                    datetime(2026, 11, 14, 5, 0, tzinfo=UTC))


def test_academic_fetch_and_normalize(web):
    result = academic.fetch()
    assert result.complete is True
    rows = {(i.payload["term"], i.payload["date_text"]): i for i in result.items}
    assert len(result.items) == 8

    exams = _normalize(academic, rows[("Fall 2026", "December 16–22, 2026")])
    assert (exams.start_date, exams.end_date) == (date(2026, 12, 16), date(2026, 12, 22))
    assert "final-exams" in exams.tags and "fall-2026" in exams.tags
    assert exams.category == "ACADEMIC" and exams.is_all_day

    with pytest.raises(ValueError):
        academic.normalize(rows[("Spring 2027", "Sometime in spring")].payload)


@pytest.mark.parametrize("text, expected", [
    ("September 2, 2026", (date(2026, 9, 2), date(2026, 9, 2))),
    ("November 26-27, 2026", (date(2026, 11, 26), date(2026, 11, 27))),
    ("December 16–22, 2026", (date(2026, 12, 16), date(2026, 12, 22))),
    ("Tuesday, September 8, 2026", (date(2026, 9, 8), date(2026, 9, 8))),
    ("December 23, 2026 - January 2, 2027", (date(2026, 12, 23), date(2027, 1, 2))),
    ("Tuesday, December 29, 2026 - January 2, 2027", (date(2026, 12, 29), date(2027, 1, 2))),
    ("December 30 - January 2, 2027", (date(2026, 12, 30), date(2027, 1, 2))),
    ("Sept 8, 2026", (date(2026, 9, 8), date(2026, 9, 8))),
])


def test_parse_date_range(text, expected):
    assert parse_date_range(text) == expected


def test_nyu_events_category_rules():
    def cat(**row):
        return nyu_events._category(row, [t.lower() for t in row.get("tags", [])])
    assert cat(tags=["mindfulnyu", "athletics", "free"], group_title="Global Spiritual Life at NYU") == "WELLNESS"
    assert cat(tags=["law", "dates and deadlines"], group_title="School of Law") == "ACADEMIC"
    assert cat(tags=["career", "lgbtq"], group_title="LGBTQ+ Center") == "CAREER"
    assert cat(tags=["music", "theater"], group_title="Casa Italiana") == "ARTS"
    assert cat(tags=["entrepreneur"], group_title="NYU Entrepreneurial Institute") == "OTHER"
    assert cat(url="https://engage.nyu.edu/event/1", tags=["career"]) == "SOCIAL"


def test_nyu_events_skips_athletics_group(web):
    import json
    body = json.loads(web.pages["events.nyu.edu/live/json/events"])
    body["data"][0] = {**body["data"][0], "id": 999, "gid": 117, "group_title": "NYU Athletics",
                       "url": "https://events.nyu.edu/event/999-fencing"}
    web.pages["events.nyu.edu/live/json/events"] = json.dumps(body).encode()
    assert "999" not in _by_id(nyu_events.fetch())


def test_wasserman_virtual_location():
    payload = {"rss": {"title": "Virtual Info Session", "link": "https://wasserman.nyu.edu/events/2026/10/15/x/",
                       "creator": "Handshake #Event:1"},
               "ics": {"summary": "Virtual Info Session", "location": "Virtual",
                       "dtstart": "2026-10-15T16:30:00+00:00", "dtend": None, "all_day": False},
               "event_date": "2026-10-15"}
    event = wasserman.normalize(payload)
    assert event.is_online and event.location_name is None and event.address is None
