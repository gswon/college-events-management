"""NYUEventSchema.sql(백엔드 공유 원본)이 명세와 맞는지, 수집기 코드가 그 스키마와 맞는지 확인한다.
DB 없이 SQL 파일 텍스트만 보고 검사한다. 실제 MySQL 적용은 test_mysql_integration.py.
"""
import re
from pathlib import Path

import pytest

from ingest import config
from ingest.migrate import statements
from ingest.models import CATEGORIES
from ingest.sources import SOURCES
from ingest.store import _EVENT_COLUMNS

ROOT = Path(__file__).resolve().parent.parent

# 명세의 12개 테이블
SPEC_TABLES = {
    "users", "refresh_tokens", "auth_tokens", "event_categories", "organizations",
    "organization_follows", "events", "event_saves", "calendar_entries", "schedule_imports",
    "friend_requests", "friendships",
}

# 명세 events 표: 컬럼 → (타입 앞부분, NOT NULL 여부)
SPEC_EVENT_COLUMNS = {
    "id": ("BIGINT UNSIGNED", True),
    "source": ("VARCHAR(50)", True),
    "external_id": ("VARCHAR(255)", False),   # MANUAL 은 NULL
    "source_url": ("VARCHAR(500)", False),
    "title": ("VARCHAR(255)", True),
    "description": ("TEXT", False),
    "category_id": ("TINYINT UNSIGNED", True),
    "organization_id": ("BIGINT UNSIGNED", False),
    "host_name": ("VARCHAR(200)", False),
    "start_at": ("DATETIME", True),
    "end_at": ("DATETIME", True),
    "is_all_day": ("BOOLEAN", True),
    "location_name": ("VARCHAR(255)", False),
    "address": ("VARCHAR(255)", False),
    "is_online": ("BOOLEAN", True),
    "online_url": ("VARCHAR(500)", False),
    "registration_url": ("VARCHAR(500)", False),
    "image_url": ("VARCHAR(500)", False),
    "is_free": ("BOOLEAN", False),
    "price_text": ("VARCHAR(100)", False),
    "audience_text": ("VARCHAR(255)", False),
    "status": ("ENUM('ACTIVE','CANCELLED','HIDDEN')", True),
    "last_synced_at": ("DATETIME", False),
    "created_at": ("DATETIME", True),
    "updated_at": ("DATETIME", True),
}


def _tables(path: Path) -> dict[str, str]:
    out = {}
    for stmt in statements(path):
        m = re.match(r"CREATE TABLE (?:IF NOT EXISTS )?(\w+) \((.*)\)\s*ENGINE=InnoDB", stmt, re.S)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def _columns(body: str) -> dict[str, str]:
    cols = {}
    for line in body.splitlines():
        m = re.match(r"\s*([a-z_]+)\s+(.+?),?\s*$", line)
        if m and m.group(1) not in ("constraint", "key", "primary", "unique", "fulltext"):
            cols[m.group(1)] = m.group(2)
    return cols


APP = _tables(ROOT / "NYUEventSchema.sql")
INGEST = _tables(ROOT / "schema_ingest.sql")


def test_twelve_spec_tables():
    assert set(APP) == SPEC_TABLES
    assert set(INGEST) == {"raw_events", "ingest_runs"}
    assert not set(APP) & set(INGEST)


@pytest.mark.parametrize("column, spec", SPEC_EVENT_COLUMNS.items())
def test_events_column_matches_spec(column, spec):
    cols = _columns(APP["events"])
    assert column in cols, f"events.{column} 없음"
    type_prefix, not_null = spec
    definition = cols[column]
    assert definition.startswith(type_prefix), definition
    assert ("NOT NULL" in definition) == not_null, definition


def test_events_has_no_extra_columns():
    assert set(_columns(APP["events"])) == set(SPEC_EVENT_COLUMNS)


def test_events_keys():
    body = APP["events"]
    assert "UNIQUE KEY uq_events_source_ext (source, external_id)" in body   # 크롤러 upsert 키
    assert "REFERENCES event_categories (id)" in body
    assert "REFERENCES organizations (id)" in body
    assert "DEFAULT 'ACTIVE'" in body


def test_spec_constraints_on_other_tables():
    assert "UNIQUE KEY uq_users_email (email)" in APP["users"]
    assert "ENUM('USER','ADMIN')" in APP["users"]
    for kind, default in (("class", "DETAILS"), ("personal", "BUSY"), ("event", "DETAILS")):
        assert re.search(rf"default_share_{kind}\s+ENUM\('HIDDEN','BUSY','DETAILS'\) NOT NULL DEFAULT '{default}'",
                         APP["users"])
        assert re.search(rf"share_{kind}\s+ENUM\('HIDDEN','BUSY','DETAILS'\) NOT NULL", APP["friendships"])
    assert "UNIQUE KEY uq_refresh_tokens_hash (token_hash)" in APP["refresh_tokens"]
    for col in ("purpose", "token_hash", "expires_at", "used_at"):
        assert col in _columns(APP["auth_tokens"])
    assert "UNIQUE KEY uq_event_categories_code (code)" in APP["event_categories"]
    assert "UNIQUE KEY uq_organizations_slug (slug)" in APP["organizations"]
    assert "UNIQUE KEY uq_organizations_source_ext (source, external_id)" in APP["organizations"]
    assert "PRIMARY KEY (user_id, organization_id)" in APP["organization_follows"]
    assert "PRIMARY KEY (user_id, event_id)" in APP["event_saves"]
    assert "ENUM('INTERESTED','GOING')" in APP["event_saves"]
    entries = _columns(APP["calendar_entries"])
    assert entries["kind"].startswith("ENUM('CLASS','PERSONAL')")
    for col in ("start_at", "end_at", "schedule_import_id", "course_code", "visibility_override", "ics_uid"):
        assert col in entries
    assert "REFERENCES schedule_imports (id) ON DELETE CASCADE" in APP["calendar_entries"]
    assert "UNIQUE KEY uq_schedule_imports_user_term (user_id, term_code)" in APP["schedule_imports"]
    assert "UNIQUE KEY uq_friend_requests_pair (from_user_id, to_user_id)" in APP["friend_requests"]
    assert "PRIMARY KEY (user_id, friend_id)" in APP["friendships"]


def test_user_owned_tables_cascade_on_user_delete():
    for table in ("refresh_tokens", "auth_tokens", "organization_follows", "event_saves",
                  "calendar_entries", "schedule_imports", "friend_requests", "friendships"):
        refs = re.findall(r"REFERENCES users \(id\)(\s+ON DELETE CASCADE)?", APP[table])
        assert refs and all(refs), f"{table}: users FK 는 ON DELETE CASCADE 여야 함"


def test_category_seed_matches_spec_and_code():
    seed = re.search(r"INSERT INTO event_categories[^;]*", (ROOT / "NYUEventSchema.sql").read_text()).group(0)
    codes = set(re.findall(r"\('([A-Z]+)',", seed))
    assert codes == {"SOCIAL", "CAREER", "SPORTS", "ACADEMIC", "ARTS", "WELLNESS", "OTHER"}
    assert codes == CATEGORIES


def test_store_writes_only_existing_columns():
    assert set(_EVENT_COLUMNS) <= set(_columns(APP["events"]))
    required = ({c for c, (_, nn) in SPEC_EVENT_COLUMNS.items() if nn} | {"external_id"}) - {"id", "created_at", "updated_at"}
    assert required <= set(_EVENT_COLUMNS)


def test_source_codes():
    codes = {m.SOURCE for m in SOURCES.values()}
    assert codes == {"NYU_EVENTS", "WASSERMAN", "ATHLETICS", "ACADEMIC"}
    assert all(len(c) <= 50 and c.isupper() for c in codes)


def test_config_reads_railway_url(monkeypatch):
    monkeypatch.setenv("MYSQL_URL", "mysql://root:p%40ss@mysql.railway.internal:3306/railway")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert config._db_from_env() == {
        "host": "mysql.railway.internal", "port": 3306, "user": "root",
        "password": "p@ss", "database": "railway",
    }
    monkeypatch.delenv("MYSQL_URL")
    monkeypatch.setenv("MYSQLHOST", "h")
    monkeypatch.setenv("MYSQLPASSWORD", "pw")
    db = config._db_from_env()
    assert (db["host"], db["password"], db["database"]) == ("h", "pw", "railway")
