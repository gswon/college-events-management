"""Princeton Athletics (goprincetontigers.com, Sidearm Sports) 수집기. NYU athletics 와 같은 형식이라 sidearm.py 를 쓴다.

SUMMARY 예시
  "[W] Princeton University Men's Swimming and Diving vs Villanova"
  "Princeton University Men's Tennis vs ITA Regionals"   (LOCATION 'Philadelphia, Pa.' → 홈 아님)
LOCATION 'Princeton, N.J., DeNunzio Pool' → 경기장 'DeNunzio Pool', 주소 'Princeton, N.J.' (이 도시면 홈 경기)
robots.txt 의 Crawl-delay 30 — 실행마다 iCal 한 번만 받으므로 문제없다.
"""
from __future__ import annotations

from ..models import Event, FetchResult, Organization
from . import sidearm

SLUG = "princeton_athletics"
SOURCE = "PRINCETON_ATHLETICS"
COLLEGE = "PRINCETON"
NAME = "Princeton Athletics"
BASE_URL = "https://goprincetontigers.com"
ORGANIZATION = Organization(external_id="athletics", name="Princeton Athletics", slug="princeton-athletics",
                            website_url=BASE_URL)
SITE = sidearm.Site(base_url=BASE_URL, school="Princeton University", short="Princeton",
                    home_prefix="Princeton, N.J.", organization=ORGANIZATION)


def fetch() -> FetchResult:
    return sidearm.fetch(SITE)


def normalize(payload: dict) -> Event:
    return sidearm.normalize(SITE, payload)
