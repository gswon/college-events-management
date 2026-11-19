"""세부 그룹 규칙. 예시는 2026-10 실제 사이트 데이터에서 가져왔다."""
import pytest

from ingest.groups import GROUPS, assign_groups
from ingest.models import Event


def groups(source, title, category, tags=(), host=None, url=None):
    event = Event(external_id="x", title=title, category=category, tags=list(tags),
                  host_name=host, source_url=url)
    return assign_groups(source, event)


@pytest.mark.parametrize("title", [
    "HSBC Information Session: Sales and Trading",
    "PJT Partners Corporate Presentation | New York University",
    "NYU Coffee Chats with Natixis CIB Americas",
    "SAP Recruiter Coffee Chats",
    "Inside Amazon University Recruiting: A Lunch & Learn",
])
def test_company_visit(title):
    assert "company-visit" in groups("WASSERMAN", title, "CAREER")


def test_program_info_is_not_company_visit():
    g = groups("WASSERMAN", "Northwestern MSL: A one-year law degree Information Session", "CAREER")
    assert "company-visit" not in g and "grad-program-info" in g
    assert groups("NYU_EVENTS", "Education Policy MA Program Online Info Session", "OTHER") == ["grad-program-info"]


def test_career_skills():
    assert "career-skills" in groups("NYU_EVENTS", "AUSA/ASPRS Resume & Cover Letter Workshop", "SOCIAL")
    assert "career-skills" in groups("WASSERMAN", "SPS Career Lab: LinkedIn Branding", "CAREER")


def test_alumni_panel_is_panel_not_networking():
    g = groups("WASSERMAN", "Navigating Life after NYU: A Recent Alumni Panel", "CAREER")
    assert g == ["panel-talk"]


def test_academic_calendar():
    assert groups("ACADEMIC", "Last day of January term classes", "ACADEMIC",
                  tags=["january-term-2027", "classes-end"]) == ["term-dates"]
    assert groups("ACADEMIC", "Fall Break - No classes scheduled", "ACADEMIC",
                  tags=["fall-2026", "no-classes"]) == ["no-classes"]


def test_athletics():
    assert groups("ATHLETICS", "NYU Women's Volleyball vs Vassar College", "SPORTS",
                  tags=["womens-volleyball", "home"]) == ["sport-womens-volleyball", "home-game"]
    assert groups("ATHLETICS", "NYU Women's Soccer at Babson College", "SPORTS",
                  tags=["womens-soccer", "away", "result-w"]) == ["sport-womens-soccer"]


def test_yoga_by_spiritual_life_office_is_not_faith():
    assert "faith" not in groups("NYU_EVENTS", "Restorative Yoga with Brain Liem", "WELLNESS",
                                 tags=["mindfulnyu", "athletics"], host="Global Spiritual Life at NYU")
    assert "faith" in groups("NYU_EVENTS", "International Bible Study", "SOCIAL")


def test_club_and_food():
    g = groups("NYU_EVENTS", "🌊 NYWEA General Body Meeting + FREE FOOD!", "SOCIAL",
               url="https://engage.nyu.edu/event/1")
    assert g == ["club-event", "club-meeting", "free-food"]


def test_group_codes_are_known():
    for code in GROUPS:
        assert code == code.lower() and " " not in code


def test_technyu():
    assert groups("TECH_NYU", "Tech@NYU x Claude: Hackday 007", "CAREER") == ["hackathon", "club-event"]
    assert "company-visit" in groups("TECH_NYU", "Interface (YC) Hiring Event", "CAREER")
    assert "panel-talk" in groups("TECH_NYU", "Tech@NYU x Petal Speaker Event", "CAREER")
