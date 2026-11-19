"""NYU Athletics (Sidearm Sports) 수집기. 공통 코드는 sidearm.py.

SUMMARY 예시
  "[W] New York University Women's Soccer at Babson College "   ← 끝난 경기 (W/L/T/N)
  "New York University Men's Soccer vs University of Chicago (TEAR IT UP!)"
"""
from __future__ import annotations

from ..models import Event, FetchResult, Organization
from . import sidearm

SLUG = "athletics"
SOURCE = "ATHLETICS"
COLLEGE = "NYU"
NAME = "NYU Athletics"
BASE_URL = "https://gonyuathletics.com"
ORGANIZER = "NYU Athletics"
ORGANIZATION = Organization(external_id="athletics", name=ORGANIZER, slug="nyu-athletics",
                            website_url=BASE_URL)
SITE = sidearm.Site(base_url=BASE_URL, school="New York University", short="NYU",
                    home_prefix="New York, NY", organization=ORGANIZATION)
ICS_URL = SITE.ics_url


def fetch() -> FetchResult:
    return sidearm.fetch(SITE)


def normalize(payload: dict) -> Event:
    return sidearm.normalize(SITE, payload)
