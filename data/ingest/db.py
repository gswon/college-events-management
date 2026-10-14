"""MySQL 연결."""
import logging
import time

import pymysql

from . import config

log = logging.getLogger(__name__)


def connect(retries: int = 5):
    """utf8mb4 + 세션 시간대 UTC 로 고정된 연결을 만든다.

    DATETIME 에는 시간대 정보가 없으므로 '여기 들어 있는 시각은 항상 UTC' 라는 규칙을
    연결 단계에서 강제한다. (CURRENT_TIMESTAMP 기본값도 UTC로 들어간다)
    Railway 에서는 MySQL 이 막 깨어나는 중일 수 있어서 몇 번 다시 시도한다.
    """
    for attempt in range(retries + 1):
        try:
            return pymysql.connect(
                **config.DB,
                charset="utf8mb4",
                autocommit=False,
                connect_timeout=10,
                init_command="SET time_zone = '+00:00'",
            )
        except pymysql.err.OperationalError as exc:
            if attempt == retries:
                raise
            wait = 3 * (attempt + 1)
            log.warning("DB 연결 실패 (%s), %s초 후 재시도 %s/%s", exc, wait, attempt + 1, retries)
            time.sleep(wait)
