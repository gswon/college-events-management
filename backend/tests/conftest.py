"""Tests use the DB in .env (the shared team DB) but leave no data behind.

- Default: rows are written inside a connection transaction that is rolled back after each test.
- FULLTEXT search: InnoDB only indexes committed rows, so those tests commit, then delete source='PYTEST' rows.
"""
import uuid
from datetime import datetime
from typing import Annotated, Optional

import pytest
from fastapi import Depends, Header
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

import models
from auth import get_current_user, get_optional_user
from database import SessionLocal, engine, get_db
from errors import APIError
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


def _user_from_header(
    db: Annotated[Session, Depends(get_db)],
    x_user_id: Annotated[Optional[int], Header()] = None,
) -> models.User:
    """get_current_user for tests: the user in the X-User-Id header is the current user, no token needed."""
    user = db.get(models.User, x_user_id) if x_user_id is not None else None
    if user is None:
        raise APIError(401, "AUTH_REQUIRED", "Please log in.")
    return user


def _optional_user_from_header(
    db: Annotated[Session, Depends(get_db)],
    x_user_id: Annotated[Optional[int], Header()] = None,
) -> Optional[models.User]:
    """get_optional_user for tests: no X-User-Id header means an anonymous request."""
    return None if x_user_id is None else _user_from_header(db, x_user_id)


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = _user_from_header
    app.dependency_overrides[get_optional_user] = _optional_user_from_header
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_optional_user, None)


@pytest.fixture
def auth_client():
    """A client with the real get_current_user, for tests of token verification."""
    return TestClient(app)


def at(day: int, hour: int = 0, minute: int = 0) -> datetime:
    """A time on 2099-01-<day>. Tests use far-future dates so they never overlap real data."""
    return datetime(2099, 1, day, hour, minute)


def assert_error(response, status: int, code: str) -> None:
    """The response is the API's standard error body with this status and error code."""
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert body["error"]["message"]


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
    """Auth header for the client fixture (read by _user_from_header)."""
    return {"X-User-Id": str(user.id)}


def make_entry(session: Session, user: models.User, start_at: datetime, end_at: datetime, **fields) -> models.CalendarEntry:
    values = dict(user_id=user.id, kind="PERSONAL", title="Test Entry", start_at=start_at, end_at=end_at, is_all_day=False)
    values.update(fields)
    entry = models.CalendarEntry(**values)
    session.add(entry)
    session.flush()
    return entry
