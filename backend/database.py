import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv

load_dotenv()

URL_DATABASE = os.getenv("DATABASE_URL")

# DB의 DATETIME은 전부 UTC. 세션 타임존을 고정해 CURRENT_TIMESTAMP도 UTC가 되게 한다.
engine = create_engine(
    URL_DATABASE,
    pool_pre_ping=True,
    connect_args={"init_command": "SET time_zone = '+00:00'"},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
