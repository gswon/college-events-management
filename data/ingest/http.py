"""모든 외부 요청은 이 모듈의 get()을 통과한다.

- User-Agent를 붙이고, 요청 사이에 REQUEST_DELAY_SEC 만큼 쉰다.
- 5xx/네트워크 오류는 몇 번 재시도한다.
- 테스트에서는 ingest.http.get 을 바꿔 끼워 실제 사이트에 요청하지 않는다.
"""
from __future__ import annotations

import logging
import time

import requests

from . import config

log = logging.getLogger(__name__)

_session = requests.Session()
_session.headers["User-Agent"] = config.USER_AGENT
_last_request_at = 0.0


def get(url: str, *, allow_404: bool = False, timeout: int = 30, retries: int = 2):
    """URL을 GET 한다. allow_404=True 이면 404일 때 예외 대신 None을 돌려준다."""
    global _last_request_at

    for attempt in range(retries + 1):
        wait = config.REQUEST_DELAY_SEC - (time.monotonic() - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        try:
            resp = _session.get(url, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout) as exc:
            _last_request_at = time.monotonic()
            if attempt == retries:
                raise
            log.warning("요청 실패, 재시도 %s/%s: %s (%s)", attempt + 1, retries, url, exc)
            time.sleep(2 * (attempt + 1))
            continue

        _last_request_at = time.monotonic()
        if resp.status_code == 404 and allow_404:
            return None
        if resp.status_code >= 500 and attempt < retries:
            log.warning("서버 오류 %s, 재시도 %s/%s: %s", resp.status_code, attempt + 1, retries, url)
            time.sleep(2 * (attempt + 1))
            continue
        resp.raise_for_status()
        return resp

    raise RuntimeError(f"unreachable: {url}")
