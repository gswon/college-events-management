"""테스트는 .env의 DB를 쓰지만 데이터를 남기지 않는다.

- 기본: 커넥션 트랜잭션 안에서 넣고 테스트가 끝나면 롤백.
- FULLTEXT 검색: InnoDB는 커밋된 행만 인덱싱하므로 커밋 후 source='PYTEST' 행을 지운다.
"""
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

import models
from database import SessionLocal, engine, get_db
from main import app

TEST_SOURCE = "PYTEST"


@pytest.fixture
def db():
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    app.dependency_overrides[get_db] = lambda: session
    try:
        yield session
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        trans.rollback()
        conn.close()


@pytest.fixture
def committed_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.execute(delete(models.Event).where(models.Event.source == TEST_SOURCE))
        session.execute(delete(models.Organization).where(models.Organization.source == TEST_SOURCE))
        session.commit()
        session.close()


@pytest.fixture
def client():
    return TestClient(app)


def category_id(session: Session, code: str) -> int:
    return session.scalar(select(models.EventCategory.id).where(models.EventCategory.code == code))


def make_org(session: Session, name: str = "Test Club") -> models.Organization:
    org = models.Organization(
        name=name, slug=f"test-{uuid.uuid4().hex[:12]}", source=TEST_SOURCE, external_id=uuid.uuid4().hex
    )
    session.add(org)
    session.flush()
    return org


def make_event(session: Session, start_at: datetime, end_at: datetime, **fields) -> models.Event:
    values = dict(
        source=TEST_SOURCE,
        external_id=uuid.uuid4().hex,
        title="Test Event",
        category_id=category_id(session, fields.pop("category", "OTHER")),
        start_at=start_at,
        end_at=end_at,
        is_all_day=False,
        is_online=False,
        status="ACTIVE",
    )
    values.update(fields)
    event = models.Event(**values)
    session.add(event)
    session.flush()
    return event


def make_user(session: Session, name: str = "Test User", **fields) -> models.User:
    values = dict(email=f"pytest-{uuid.uuid4().hex[:12]}@nyu.edu", password_hash="-", display_name=name)
    values.update(fields)
    user = models.User(**values)
    session.add(user)
    session.flush()
    return user


def as_user(user: models.User) -> dict:
    """auth.py의 개발용 인증 헤더."""
    return {"X-User-Id": str(user.id)}


def make_entry(session: Session, user: models.User, start_at: datetime, end_at: datetime, **fields) -> models.CalendarEntry:
    values = dict(user_id=user.id, kind="PERSONAL", title="Test Entry", start_at=start_at, end_at=end_at, is_all_day=False)
    values.update(fields)
    entry = models.CalendarEntry(**values)
    session.add(entry)
    session.flush()
    return entry
