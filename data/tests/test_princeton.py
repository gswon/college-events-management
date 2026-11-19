"""Princeton 소스 2개 (princeton_events, princeton_athletics). fixtures 는 2026-11-14 실제 피드에서 몇 건만 남긴 것."""
from datetime import date, datetime, timezone

from ingest.run import to_events
from ingest.sources import princeton_athletics, princeton_events
from ingest.sources.princeton_events import _category, _split_location

UTC = timezone.utc


def _events(module):
    result = module.fetch()
    return result, {item.external_id: to_events(module, item)[0] for item in result.items}


def test_princeton_events_fetch(web):
    result, events = _events(princeton_events)
    assert "338051-0" not in events            # 체육 경기(goprincetontigers.com)는 princeton_athletics 가 정본
    assert len(events) == 9
    assert all(e.college == "PRINCETON" for e in events.values())
    # 피드 = 날짜순 200건 → 마지막 행사 시각까지만 '전체 목록'으로 보고 취소 처리
    assert result.complete is True
    assert result.window_end_utc == datetime(2026, 12, 1, 22, 0, tzinfo=UTC)


def test_princeton_events_normalize(web):
    _, events = _events(princeton_events)

    site = events["339836-0"]
    assert site.title == "Site: Exhibition by Carlos Agredano" and site.category == "ARTS"
    assert site.start_at == datetime(2026, 11, 14, 14, 0, tzinfo=UTC)
    assert site.end_at == datetime(2026, 11, 15, 1, 30, tzinfo=UTC)
    assert site.location_name == "Hurley Gallery, Lewis Arts Complex" and site.address is None
    assert site.source_url == "https://arts.princeton.edu/events/2026/site-exhibition-carlos-agredano"
    assert site.organization.slug == "princeton-lewis-center-arts"
    assert site.host_name == "Lewis Center for the Arts"
    # 설명은 RSS 전문 (iCal 은 잘려 있음), 붙어 버린 문단은 줄바꿈으로
    assert "Superfund" in site.description and "\nSite follows" in site.description

    gallery = events["340736-0"]
    assert (gallery.location_name, gallery.address) == ("Hagan Gallery", "185 Nassau Street")

    worship = events["338066-0"]                # LOCATION 'Invite Only' 는 장소가 아님
    assert worship.category == "SOCIAL" and worship.location_name is None
    assert worship.audience_text == "Invite only"

    holiday = events["331606-0"]                # 뉴욕 자정 ~ 11/27 23:45 → 종일 이틀
    assert holiday.category == "ACADEMIC" and holiday.is_all_day
    assert (holiday.start_date, holiday.end_date) == (date(2026, 11, 26), date(2026, 11, 27))

    assert events["338061-0"].category == "SOCIAL"     # Magic: The Gathering Club Meeting
    assert events["338091-0"].category == "CAREER"     # Pace Center Summer Internships Drop-in
    assert events["341496-0"].category == "ACADEMIC"   # IHUM Open House (학과 사이트)
    assert events["341376-0"].organization.slug == "princeton-art-museum"


def test_princeton_events_without_rss(web):
    web.pages["princeton.edu/feed/events"] = None        # RSS 실패 → 잘린 iCal 설명으로
    _, events = _events(princeton_events)
    assert events["339836-0"].description.startswith("Recent 2025-26 Hodder Fellow")


def test_princeton_category_rules():
    assert _category("Princeton Psychology Society Career Panel", "princeton.edu") == "CAREER"
    assert _category("Composition Colloquium with Tian Zhou", "music.princeton.edu") == "ARTS"
    assert _category("Tour of Firestone Library", "libcal.princeton.edu") == "ACADEMIC"
    assert _category("PCF Frosh Bible study", "princeton.edu") == "SOCIAL"
    assert _category("Norman Finkelstein Lecture", "princeton.edu") == "ACADEMIC"
    assert _category("Advent Concert: Stars", "princeton.edu") == "ARTS"
    assert _category("Mindfulness Meditation", "princeton.edu") == "WELLNESS"
    assert _category("Lives Well Lived", "uchv.princeton.edu") == "ACADEMIC"
    assert _category("Princeton Women in National Security", "princeton.edu") == "OTHER"


def test_princeton_room_numbers_are_not_addresses():
    assert _split_location("Art Museum, 100 Grand Hall") == ("Art Museum, 100 Grand Hall", None)
    assert _split_location("Center for Modern Aging, 101 Poor Farm Road, Princeton, NJ 08540") == (
        "Center for Modern Aging", "101 Poor Farm Road, Princeton, NJ 08540")


def test_princeton_athletics(web):
    result, events = _events(princeton_athletics)
    assert result.complete is True and len(events) == 4
    swim = events["21970"]
    assert swim.title == "Princeton Men's Swimming and Diving vs Villanova"
    assert swim.category == "SPORTS" and swim.college == "PRINCETON"
    assert (swim.location_name, swim.address) == ("DeNunzio Pool", "Princeton, N.J.")
    assert "home" in swim.tags and "result-w" in swim.tags and "home-game" in swim.groups
    assert swim.organization.slug == "princeton-athletics"

    tennis = events["21913"]                    # 'vs' 지만 Philadelphia → 홈 아님
    assert "neutral" in tennis.tags and tennis.is_all_day
    assert (tennis.start_date, tennis.end_date) == (date(2026, 10, 15), date(2026, 10, 19))


def test_princeton_arts_sites_win_over_social_and_academic_words():
    assert _category("Handel Messiah: Part 1 & Britten A Ceremony of Carols", "music.princeton.edu") == "ARTS"
    assert _category("Silent Book Club", "libcal.princeton.edu") == "SOCIAL"   # 도서관은 제목이 먼저
