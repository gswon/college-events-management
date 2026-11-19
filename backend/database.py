import os
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()

URL_DATABASE = os.getenv("DATABASE_URL")

# Every DATETIME in the DB is UTC. Pinning the session time zone makes CURRENT_TIMESTAMP UTC too.
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


# Route parameter type for a request-scoped DB session: `def route(db: db_dependency): ...`
db_dependency = Annotated[Session, Depends(get_db)]
