"""세부 그룹 규칙. 카테고리(하나)와 달리 이벤트 하나가 여러 그룹에 들어갈 수 있다.

DB 에는 아직 저장하지 않는다 (tags / event_tags 테이블은 백엔드와 합의 후 추가).
지금은 --dry-run 출력의 groups 칸으로만 확인한다.
"""
from __future__ import annotations

import re

from .models import Event

# 그룹 코드 → (상위 카테고리, 화면 이름)
GROUPS = {
    "company-visit":     ("CAREER",   "회사 방문 (인포세션·커피챗)"),
    "career-skills":     ("CAREER",   "커리어 스킬 (이력서·LinkedIn·면접)"),
    "networking":        ("CAREER",   "네트워킹"),
    "panel-talk":        ("CAREER",   "패널·토크"),
    "career-fair":       ("CAREER",   "커리어 페어·서밋"),
    "hackathon":         ("CAREER",   "해커톤·핵데이"),
    "grad-program-info": ("ACADEMIC", "대학원·장학금 설명회"),
    "lecture":           ("ACADEMIC", "강연·세미나"),
    "no-classes":        ("ACADEMIC", "휴강·방학"),
    "exams":             ("ACADEMIC", "시험"),
    "term-dates":        ("ACADEMIC", "개강·종강"),
    "deadline":          ("ACADEMIC", "마감일"),
    "home-game":         ("SPORTS",   "홈 경기"),
    # 종목별 그룹은 sport-<종목> 으로 자동 생성 (예: sport-womens-soccer)
    "club-event":        ("SOCIAL",   "동아리 행사"),
    "club-meeting":      ("SOCIAL",   "동아리 정기 모임"),
    "free-food":         ("SOCIAL",   "음식 제공"),
    "cultural":          ("SOCIAL",   "문화·커뮤니티"),
    "faith":             ("SOCIAL",   "종교·영성"),
    "volunteering":      ("SOCIAL",   "봉사·모금"),
}


def _re(*words: str) -> re.Pattern:
    return re.compile(r"\b(" + "|".join(words) + r")\b", re.I)


_COMPANY = _re(r"info(rmation)? sessions?", r"corporate presentations?", r"coffee chats?",
               r"recruit(ing|er|ers)", r"hiring", r"lunch (&|and) learn", r"employer", r"meet the firm")
_PROGRAM = _re(r"programs?", r"degrees?", r"graduate", r"master'?s", r"m\.?s\.?", r"m\.?a\.?", r"mba",
               r"ph\.?d", r"doctoral", r"bfa", r"mfa", r"dnp", r"scholarships?", r"fellowships?", r"msl")
_INFO = _re(r"info(rmation)? sessions?", r"open house", r"webinar", r"information")
_SKILLS = _re(r"r[eé]sum[eé]s?", r"cover letters?", r"cv", r"linkedin", r"interview(s|ing)?", r"portfolios?",
              r"personal brand(ing)?", r"negotiat\w*", r"elevator pitch", r"headshots?", r"career lab")
_NETWORKING = _re(r"networking", r"mixer", r"meet (&|and) greet", r"reception", r"meet the industry")
_PANEL = _re(r"panel", r"fireside", r"real talk", r"speakers?( series| event)?", r"in conversation")
_HACK = _re(r"hack(athon|days?)", r"buildathon", r"build night")
_FAIR = _re(r"career fair", r"job fair", r"expo", r"summit")
_LECTURE = _re(r"lectures?", r"seminars?", r"colloquium", r"symposium", r"conference", r"book (talk|launch)",
               r"research", r"workshop")
_DEADLINE = _re(r"deadlines?", r"registration (begins|opens|ends)")
_MEETING = _re(r"general (body )?meeting", r"gbm", r"e-?board", r"board meeting", r"interest meeting",
               r"weekly meeting")
_FOOD = _re(r"free food", r"pizza", r"snacks?", r"lunch", r"dinner", r"breakfast", r"brunch", r"boba",
            r"bagels?", r"refreshments", r"potluck", r"food")
_CULTURAL = _re(r"cultur(e|al)", r"heritage", r"festival", r"diwali", r"lunar new year", r"hispanic",
                r"latin[oax]?", r"asian", r"black", r"indigenous", r"international students?", r"korean",
                r"chinese", r"japanese", r"indian", r"arab", r"african", r"caribbean", r"lgbtq\+?", r"queer")
_FAITH = _re(r"prayer", r"bible", r"worship", r"mass", r"shabbat", r"qur'?an", r"islamic", r"muslim",
             r"christian", r"catholic", r"hillel", r"jewish", r"jummah", r"church")
_VOLUNTEER = _re(r"volunteer(ing)?", r"community service", r"fundrais(er|ing)", r"donation", r"charity")


def assign_groups(source: str, event: Event) -> list[str]:
    title = event.title
    text = " ".join([title, " ".join(event.tags), event.host_name or ""])
    groups: list[str] = []

    def add(code: str) -> None:
        if code not in groups:
            groups.append(code)

    is_program_info = bool(_INFO.search(title) and _PROGRAM.search(title))
    if is_program_info:
        add("grad-program-info")

    if event.category == "CAREER":
        if _COMPANY.search(title) and not is_program_info:
            add("company-visit")
        if _SKILLS.search(text):
            add("career-skills")
        if _NETWORKING.search(title):
            add("networking")
        if _PANEL.search(title):
            add("panel-talk")
        if _FAIR.search(title):
            add("career-fair")
        if _HACK.search(title):
            add("hackathon")
    elif _SKILLS.search(text):
        add("career-skills")

    if source == "ACADEMIC":
        for tag, code in (("no-classes", "no-classes"), ("final-exams", "exams"),
                          ("classes-begin", "term-dates"), ("classes-end", "term-dates")):
            if tag in event.tags:
                add(code)
    if _DEADLINE.search(title):
        add("deadline")
    if event.category in ("ACADEMIC", "OTHER", "ARTS") and _LECTURE.search(text):
        add("lecture")

    if source in ("ATHLETICS", "PRINCETON_ATHLETICS"):
        sport = next((t for t in event.tags if t not in ("home", "away", "neutral", "scrimmage")
                      and not t.startswith("result-")), None)
        if sport:
            add(f"sport-{sport}")
        if "home" in event.tags:
            add("home-game")

    if source == "TECH_NYU" or (source == "NYU_EVENTS" and "engage.nyu.edu" in (event.source_url or "")):
        add("club-event")
    if _MEETING.search(title):
        add("club-meeting")
    if _FOOD.search(text):
        add("free-food")
    if _CULTURAL.search(text):
        add("cultural")
    if _FAITH.search(text):
        add("faith")
    if _VOLUNTEER.search(text):
        add("volunteering")

    return groups
