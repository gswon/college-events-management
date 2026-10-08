"""NYUEventSchema.sql을 .env의 DATABASE_URL DB에 적용한다 (1회성).

SQL 파일은 데이터 팀 공유본이라 수정하지 않고, CREATE DATABASE / USE 문만 건너뛴다.
실행: ~/miniconda3/envs/eventapp/bin/python scripts/apply_schema.py
"""
import os
import re
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(BACKEND_DIR, "NYUEventSchema.sql")


def split_statements(sql: str) -> list[str]:
    # DDL 안의 문자열 리터럴에는 '--'가 없으므로 줄 단위 주석 제거로 충분하다.
    no_comments = re.sub(r"--[^\n]*", "", sql)
    return [s.strip() for s in no_comments.split(";") if s.strip()]


def main() -> None:
    load_dotenv(os.path.join(BACKEND_DIR, ".env"))
    engine = create_engine(os.environ["DATABASE_URL"])

    with open(SCHEMA_PATH, encoding="utf-8") as f:
        statements = split_statements(f.read())

    with engine.connect() as conn:
        existing = [r[0] for r in conn.execute(text("SHOW TABLES"))]
        if existing:
            sys.exit(f"DB가 비어 있지 않습니다: {existing}. 중단합니다.")

        for stmt in statements:
            if re.match(r"(CREATE\s+DATABASE|USE)\b", stmt, re.IGNORECASE):
                print("skip:", stmt.splitlines()[0])
                continue
            conn.execute(text(stmt))
        conn.commit()

        tables = [r[0] for r in conn.execute(text("SHOW TABLES"))]
        categories = conn.execute(text("SELECT COUNT(*) FROM event_categories")).scalar()
    print(f"tables ({len(tables)}):", tables)
    print("event_categories rows:", categories)


if __name__ == "__main__":
    main()
