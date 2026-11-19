"""제목 키워드로 카테고리를 정하는 공통 규칙 (NYU events.nyu.edu, Princeton 캘린더가 같이 쓴다).

  from_title("Princeton University Orchestra: Britten") → "ARTS"
  from_title("Spring Registration Begins")              → "ACADEMIC"
  from_title("Something Unclear")                        → None  (소스가 태그·주최 사이트로 정한다)

제목이 태그보다 정확하다: events.nyu.edu 의 태그는 부서가 아무렇게나 붙여서
(예: Box Office 의 Jets 경기에 'arts', 브로드웨이 공연에 'athletics') 제목을 먼저 본다.
위에서부터 먼저 맞는 규칙을 쓴다.
"""
from __future__ import annotations

import re


def _kw(*words: str) -> re.Pattern:
    return re.compile(r"\b(" + "|".join(words) + r")\b", re.I)


RULES: list[tuple[str, re.Pattern]] = [
    # 학사일정·마감 (휴일, 수강신청, 시험 기간)
    ("ACADEMIC", _kw(r"university holiday", r"holiday \(no classes\)", r"no classes", r"recess", r"fall break",
                     r"spring break", r"reading period", r"final exams?", r"exam period", r"classes (begin|end)",
                     r"last day of (classes|\w+ \d{4} classes)", r"deadlines?", r"registration (begins|opens|ends)",
                     r"(spring|fall|summer|january) registration", r"withdrawal", r"census date", r"commencement",
                     r"apply for \w+ \d{4} graduation", r"fafsa", r"class schedule published")),
    ("CAREER", _kw(r"careers?", r"internships?", r"jobs?", r"recruit\w*", r"r[eé]sum[eé]s?", r"cover letters?",
                   r"interview(s|ing)?", r"networking", r"employers?", r"hiring", r"coffee chats?", r"linkedin",
                   r"career fair", r"info(rmation)? session with", r"private equity", r"investment bank\w*",
                   r"consulting", r"industry (panel|professionals|night|mixer)", r"alumni panel", r"mentorship",
                   r"professional development", r"j\.?p\.? morgan", r"goldman sachs", r"mckinsey")),
    ("WELLNESS", _kw(r"wellness", r"well-being", r"wellbeing", r"mindful\w*", r"meditation", r"yoga", r"pilates",
                     r"zumba", r"vinyasa", r"mental health", r"counseling", r"fitness", r"self-care", r"stress less",
                     r"flu (shot|clinic|pop-up)", r"vaccin\w*", r"therapy dogs?", r"sound bath")),
    ("ARTS", _kw(r"concerts?", r"orchestra", r"symphony", r"philharmonic", r"choir", r"chorus", r"ensemble",
                 r"recital", r"opera", r"ballet", r"jazz", r"exhibitions?", r"exhibit", r"gallery", r"museum",
                 r"curator", r"theat(er|re)", r"broadway", r"musical", r"play reading", r"screenings?", r"films?",
                 r"cinema", r"documentary", r"dance", r"tango", r"salsa", r"swing", r"poetry", r"performances?",
                 r"open studios?", r"art show", r"winter show", r"music", r"piano", r"chorale", r"photographs?",
                 r"photography", r"showcase")),
    # 종교 모임 (NYU groups.py 의 'faith' 도 SOCIAL 아래). 'Ministry Table Talk' 처럼 강연 단어보다 먼저 본다.
    # fellowship 은 장학 펠로십과 헷갈려서 종교 단체 이름이 붙은 것만
    ("SOCIAL", _kw(r"bible", r"worship", r"(christian|orthodox|catholic|campus|student|thanksgiving) fellowship",
                   r"fellowship (meeting|night|dinner|boba|event)", r"devotional", r"prayer", r"ministry", r"mass",
                   r"shabbat", r"jummah", r"small group", r"qira['’]?at", r"qur['’]?an", r"quran")),
    ("ACADEMIC", _kw(r"lectures?", r"seminars?", r"colloquium", r"symposium", r"conference", r"research",
                     r"talks?", r"book (reading|talk|launch)", r"in conversation", r"panel( discussion)?",
                     r"open house", r"info(rmation)? sessions?", r"study (abroad|away)", r"works?-in-progress",
                     r"office hours", r"tutoring", r"writing (center|clinic)", r"dissertation", r"thesis",
                     r"workshop on", r"webinar", r"brownbag", r"brown bag", r"proseminar", r"roundtable", r"forum",
                     r"conversations?", r"discussions?", r"speaker series", r"book presentation", r"orientation",
                     r"drop-in sessions?", r"lightning lesson", r"workshops?", r"study (slam|jam|session|hall)",
                     r"supplemental learning")),
    # 종목 이름, 또는 프로팀 'Nets vs. 76ers' / 'Rangers V. Devils' (법률 사건명 'A v. B', 'Star Wars vs ...' 는 아님)
    ("SPORTS", re.compile(r"\b(basketball|football|hockey|soccer|baseball|volleyball|tennis|wrestling|lacrosse|"
                          r"softball|squash|swim meet|track meet|game day)\b|"
                          r"\b(nets|knicks|rangers|islanders|devils|jets|giants|yankees|mets|liberty|nycfc|red bulls|"
                          r"princeton|nyu)\s+(vs\.?|v\.)\s", re.I)),
    ("SOCIAL", _kw(r"socials?", r"mixer", r"party", r"dinner", r"lunch", r"brunch", r"breakfast", r"happy hour",
                   r"pizza", r"trivia", r"game night", r"games?", r"karaoke", r"festival", r"celebration",
                   r"potluck", r"meet[- ]?up", r"meet (&|and) greet", r"gathering", r"clubs?", r"general meeting",
                   r"(weekly|interest|board|e-board) meeting", r"meetings?", r"friendsgiving", r"crafts?",
                   r"movie night", r"study break", r"night", r"reception", r"feast", r"get-together", r"tea",
                   r"tasting", r"(food|coat|clothing|book) drive", r"day of service", r"volunteer\w*",
                   r"alumni", r"ceremony")),
]


def from_title(title: str | None) -> str | None:
    for category, pattern in RULES:
        if title and pattern.search(title):
            return category
    return None
