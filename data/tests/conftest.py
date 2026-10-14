"""테스트 공통 설정: 실제 사이트 대신 tests/fixtures 의 파일을 돌려주는 가짜 http.get.

fixtures 는 2026-10-06~07 에 실제 사이트에서 받은 응답을 줄여 만든 것이다
(wasserman_ubs.ics 와 academic.html 은 실제 내용을 바탕으로 같은 형식으로 재구성).
"""
import json
from datetime import date
from pathlib import Path

import pytest

from ingest import config, http
from ingest.sources import academic, athletics, nyu_events, wasserman

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 10, 6)


class FakeResponse:
    def __init__(self, body: bytes):
        self.content = body
        self.status_code = 200

    def json(self):
        return json.loads(self.content)


class FakeWeb:
    """URL → 응답 본문. 테스트 안에서 바꿔 끼울 수 있다."""

    def __init__(self):
        self.pages = {
            "events.nyu.edu/live/json/events": (FIXTURES / "nyu_events.json").read_bytes(),
            "wasserman.nyu.edu/events/feed/?paged=": None,  # 2페이지부터는 404
            "wasserman.nyu.edu/events/feed/": (FIXTURES / "wasserman_feed.xml").read_bytes(),
            "ubs-investment-banking-info-session.ics/": (FIXTURES / "wasserman_ubs.ics").read_bytes(),
            "gonyuathletics.com/calendar.ashx": (FIXTURES / "athletics.ics").read_bytes(),
            "bulletins.nyu.edu/nyu/academic-calendar/": (FIXTURES / "academic.html").read_bytes(),
        }
        self.requested: list[str] = []

    def get(self, url, *, allow_404=False, **_):
        self.requested.append(url)
        for key, body in self.pages.items():
            if key in url:
                if body is None:
                    if allow_404:
                        return None
                    raise RuntimeError(f"404: {url}")
                return FakeResponse(body)
        if allow_404:
            return None  # 예: 준비 안 된 .ics → 404 취급
        raise RuntimeError(f"테스트에 없는 URL: {url}")


@pytest.fixture
def web(monkeypatch):
    fake = FakeWeb()
    monkeypatch.setattr(http, "get", fake.get)
    monkeypatch.setattr(config, "REQUEST_DELAY_SEC", 0)
    monkeypatch.setattr(config, "NYU_EVENTS_DAYS_AHEAD", 1)
    for module in (nyu_events, wasserman, academic, athletics):
        if hasattr(module, "ny_today"):
            monkeypatch.setattr(module, "ny_today", lambda: TODAY)
    return fake
