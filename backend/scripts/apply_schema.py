"""Apply NYUEventSchema.sql to the DB in .env's DATABASE_URL (one time, on an empty DB).

The SQL file is shared with the data team, so it is not edited here; only CREATE DATABASE / USE are skipped.
Run: ~/miniconda3/envs/eventapp/bin/python scripts/apply_schema.py
"""
import os
import re
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(BACKEND_DIR, "NYUEventSchema.sql")


def split_statements(sql: str) -> list[str]:
    # No string literal in the DDL contains '--', so stripping line comments is enough.
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
            sys.exit(f"The DB is not empty: {existing}. Stopping.")

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
