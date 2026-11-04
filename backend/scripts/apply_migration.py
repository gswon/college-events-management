"""migrations/*.sql 하나를 .env의 DATABASE_URL DB에 적용한다.

새 DB는 apply_schema.py로 NYUEventSchema.sql을 적용한 뒤 migrations/ 파일을 번호 순서대로 적용한다.
실행: ~/miniconda3/envs/eventapp/bin/python scripts/apply_migration.py migrations/001_supabase_auth.sql
"""
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from apply_schema import BACKEND_DIR, split_statements


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("사용법: apply_migration.py migrations/<파일>.sql")
    path = os.path.join(BACKEND_DIR, sys.argv[1])

    load_dotenv(os.path.join(BACKEND_DIR, ".env"))
    engine = create_engine(os.environ["DATABASE_URL"])

    with open(path, encoding="utf-8") as f:
        statements = split_statements(f.read())

    # MySQL DDL은 자동 커밋되므로 문장 단위로 실행하고 진행 상황을 남긴다.
    with engine.connect() as conn:
        for stmt in statements:
            print("run:", stmt.splitlines()[0])
            conn.execute(text(stmt))
        conn.commit()
    print("done:", sys.argv[1])


if __name__ == "__main__":
    main()
