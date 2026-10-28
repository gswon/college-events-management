from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import models
from auth import user_dependency
from database import get_db
from errors import APIError
from schemas import EntryCreate, EntryOut, EntryUpdate
from timeutil import to_utc_naive

router = APIRouter(tags=["entries"])

db_dependency = Annotated[Session, Depends(get_db)]

# 수업(CLASS)은 시간표 import가 관리하므로 이 필드만 직접 고칠 수 있다.
CLASS_EDITABLE = {"description", "visibility_override"}


def _check_times(start_at: datetime, end_at: datetime) -> None:
    if end_at < start_at:
        raise APIError(400, "INVALID_RANGE", "end_at은 start_at보다 앞일 수 없습니다.")


def _own_entry(db: Session, user: models.User, entry_id: int) -> models.CalendarEntry:
    entry = db.get(models.CalendarEntry, entry_id)
    # 남의 일정은 있는지 여부도 알리지 않는다.
    if entry is None or entry.user_id != user.id:
        raise APIError(404, "ENTRY_NOT_FOUND", "일정을 찾을 수 없습니다.")
    return entry


@router.post("/entries", response_model=EntryOut, status_code=201)
def create_entry(body: EntryCreate, db: db_dependency, user: user_dependency):
    values = body.model_dump()
    values["start_at"], values["end_at"] = to_utc_naive(body.start_at), to_utc_naive(body.end_at)
    _check_times(values["start_at"], values["end_at"])
    entry = models.CalendarEntry(user_id=user.id, kind="PERSONAL", **values)
    db.add(entry)
    db.commit()
    return entry


@router.get("/entries/{entry_id}", response_model=EntryOut)
def get_entry(entry_id: int, db: db_dependency, user: user_dependency):
    return _own_entry(db, user, entry_id)


@router.patch("/entries/{entry_id}", response_model=EntryOut)
def update_entry(entry_id: int, body: EntryUpdate, db: db_dependency, user: user_dependency):
    entry = _own_entry(db, user, entry_id)
    changes = body.model_dump(exclude_unset=True)
    if entry.kind == "CLASS":
        locked = sorted(changes.keys() - CLASS_EDITABLE)
        if locked:
            raise APIError(
                400, "FIELD_NOT_EDITABLE",
                f"수업 일정은 description, visibility_override만 수정할 수 있습니다: {', '.join(locked)}",
            )
    for field in ("start_at", "end_at"):
        if field in changes:
            changes[field] = to_utc_naive(changes[field])
    _check_times(changes.get("start_at", entry.start_at), changes.get("end_at", entry.end_at))

    for field, value in changes.items():
        setattr(entry, field, value)
    db.commit()
    return entry


@router.delete("/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: int, db: db_dependency, user: user_dependency):
    db.delete(_own_entry(db, user, entry_id))
    db.commit()
