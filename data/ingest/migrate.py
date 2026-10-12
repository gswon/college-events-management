"""스키마 적용.

  python -m ingest.migrate              # INGEST_APPLY_SCHEMA 설정대로 (기본 all)
  python -m ingest.migrate --only ingest

NYUEventSchema.sql 은 백엔드와 공유하는 원본이라 수정하지 않는다.
백엔드 scripts/apply_schema.py 와 같은 방식으로 CREATE DATABASE / USE 문은 건너뛰고,
앱 테이블(events)이 이미 있으면 이 파일은 통째로 건너뛴다.
schema_ingest.sql 은 CREATE TABLE IF NOT EXISTS 라 매번 적용해도 안전하다.
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

from . import config

log = logging.getLogger("ingest.migrate")

ROOT = Path(__file__).resolve().parent.parent
APP_SCHEMA = ROOT / "NYUEventSchema.sql"
INGEST_SCHEMA = ROOT / "schema_ingest.sql"
MODES = ("all", "ingest", "none")

_COMMENT_RE = re.compile(r"--[^\n]*")
_SKIP_RE = re.compile(r"(CREATE\s+DATABASE|USE)\b", re.I)


def statements(path: Path) -> list[str]:
    """SQL 파일을 문장 단위로 나눈다. 스키마 파일의 문자열 안에는 '--' 와 ';' 가 없다."""
    sql = _COMMENT_RE.sub("", path.read_text(encoding="utf-8"))
    return [s.strip() for s in sql.split(";") if s.strip() and not _SKIP_RE.match(s.strip())]


def _table_exists(cur, name: str) -> bool:
    cur.execute("SHOW TABLES LIKE %s", (name,))
    return cur.fetchone() is not None


def apply(conn, mode: str) -> None:
    if mode not in MODES:
        raise ValueError(f"INGEST_APPLY_SCHEMA 는 {' / '.join(MODES)} 중 하나: {mode!r}")
    with conn.cursor() as cur:
        if mode == "all":
            if _table_exists(cur, "events"):
                log.info("앱 테이블이 이미 있어 %s 는 건너뜀", APP_SCHEMA.name)
            else:
                for stmt in statements(APP_SCHEMA):
                    cur.execute(stmt)
                log.info("스키마 적용: %s", APP_SCHEMA.name)
        if mode in ("all", "ingest"):
            for stmt in statements(INGEST_SCHEMA):
                cur.execute(stmt)
            log.info("스키마 적용: %s", INGEST_SCHEMA.name)
    conn.commit()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="스키마 적용")
    parser.add_argument("--only", choices=MODES, default=config.APPLY_SCHEMA)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    from .db import connect

    conn = connect()
    try:
        apply(conn, args.only)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
