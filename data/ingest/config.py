"""환경 변수 기반 설정. 로컬에서는 .env 파일에 적어두면 된다 (.env.example 참고)."""
import os
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

load_dotenv()


def _db_from_env() -> dict:
    """DB 접속 정보. 먼저 찾은 것을 쓴다.

    1) DATABASE_URL 또는 MYSQL_URL  (mysql://user:pass@host:port/db — Railway MySQL 이 주는 형식)
    2) MYSQLHOST / MYSQLPORT / MYSQLUSER / MYSQLPASSWORD / MYSQLDATABASE  (Railway MySQL 개별 변수)
    3) DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME  (로컬 .env)
    """
    url = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL")
    if url:
        u = urlparse(url)
        if not u.scheme.startswith("mysql"):
            raise ValueError(f"MySQL URL 이 아님: scheme={u.scheme!r}")
        return {
            "host": u.hostname or "127.0.0.1",
            "port": u.port or 3306,
            "user": unquote(u.username or ""),
            "password": unquote(u.password or ""),
            "database": u.path.lstrip("/") or "railway",
        }
    if os.getenv("MYSQLHOST"):
        return {
            "host": os.environ["MYSQLHOST"],
            "port": int(os.getenv("MYSQLPORT", "3306")),
            "user": os.getenv("MYSQLUSER", "root"),
            "password": os.getenv("MYSQLPASSWORD", ""),
            "database": os.getenv("MYSQLDATABASE", "railway"),
        }
    return {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "nyu_ingest"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "nyu_calendar"),
    }


DB = _db_from_env()

# `python -m ingest.run` 을 --source 없이 돌릴 때 수집할 소스 (쉼표로 구분).
# 학사일정(academic)은 틀리면 치명적이라 기본값에서 빼고 --source academic 으로 따로 돌린다.
DEFAULT_SOURCES = os.getenv("INGEST_SOURCES", "nyu_events,wasserman,athletics")

# --migrate 때 적용할 스키마
#   all    : 앱 테이블(NYUEventSchema.sql, 없을 때만) + 수집기 테이블
#   ingest : 수집기 테이블만 (앱 테이블은 백엔드가 만들 때)
#   none   : 적용 안 함
APPLY_SCHEMA = os.getenv("INGEST_APPLY_SCHEMA", "all").lower()

USER_AGENT = os.getenv(
    "INGEST_USER_AGENT",
    "NYUEventsBot/0.1 (LikeLion NYU student project; contact via team repo)",
)
REQUEST_DELAY_SEC = float(os.getenv("INGEST_REQUEST_DELAY", "1.0"))

# events.nyu.edu: 오늘부터 며칠 뒤까지 받을지, 한 번에 며칠씩 끊어서 요청할지
NYU_EVENTS_DAYS_AHEAD = int(os.getenv("NYU_EVENTS_DAYS_AHEAD", "60"))
NYU_EVENTS_CHUNK_DAYS = int(os.getenv("NYU_EVENTS_CHUNK_DAYS", "1"))

# Wasserman RSS: 최대 몇 페이지까지 넘길지 (페이지당 10건)
WASSERMAN_MAX_PAGES = int(os.getenv("WASSERMAN_MAX_PAGES", "15"))

# 변환된 결과를 몇 건마다 커밋할지
COMMIT_EVERY = int(os.getenv("INGEST_COMMIT_EVERY", "200"))
