"""Apply one migrations/*.sql file to the DB in .env's DATABASE_URL.

A new DB gets NYUEventSchema.sql via apply_schema.py first, then each migrations/ file in number order.
Run: ~/miniconda3/envs/eventapp/bin/python scripts/apply_migration.py migrations/001_supabase_auth.sql
"""
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from apply_schema import BACKEND_DIR, split_statements


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: apply_migration.py migrations/<file>.sql")
    path = os.path.join(BACKEND_DIR, sys.argv[1])

    load_dotenv(os.path.join(BACKEND_DIR, ".env"))
    engine = create_engine(os.environ["DATABASE_URL"])

    with open(path, encoding="utf-8") as f:
        statements = split_statements(f.read())

    # MySQL commits each DDL statement on its own, so run them one by one and print progress.
    with engine.connect() as conn:
        for stmt in statements:
            print("run:", stmt.splitlines()[0])
            conn.execute(text(stmt))
        conn.commit()
    print("done:", sys.argv[1])


if __name__ == "__main__":
    main()
