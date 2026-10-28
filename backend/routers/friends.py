from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session, contains_eager, joinedload

import models
from auth import user_dependency
from database import get_db
from errors import APIError
from schemas import FriendOut, FriendRequestCreate, FriendRequestOut, SharingLevels, SharingUpdate
from timeutil import utc_now

router = APIRouter(tags=["friends"])

db_dependency = Annotated[Session, Depends(get_db)]


def _make_friends(db: Session, a: models.User, b: models.User) -> None:
    # 양방향 2행. 각자의 기본 공유 수준을 자기 행으로 복사한다.
    for owner, other in ((a, b), (b, a)):
        if db.get(models.Friendship, (owner.id, other.id)) is None:
            db.add(models.Friendship(
                user_id=owner.id,
                friend_id=other.id,
                share_class=owner.default_share_class,
                share_personal=owner.default_share_personal,
                share_event=owner.default_share_event,
            ))


def _accept(db: Session, req: models.FriendRequest) -> None:
    req.status = "ACCEPTED"
    req.responded_at = utc_now()
    _make_friends(db, req.from_user, req.to_user)


def _pending_request(db: Session, user: models.User, request_id: int, incoming: bool) -> models.FriendRequest:
    req = db.get(models.FriendRequest, request_id)
    owner_id = None if req is None else (req.to_user_id if incoming else req.from_user_id)
    if owner_id != user.id:
        raise APIError(404, "REQUEST_NOT_FOUND", "친구 요청을 찾을 수 없습니다.")
    if req.status != "PENDING":
        raise APIError(409, "REQUEST_NOT_PENDING", "이미 처리된 친구 요청입니다.")
    return req


def _my_friendship(db: Session, user: models.User, friend_id: int) -> models.Friendship:
    row = db.get(models.Friendship, (user.id, friend_id))
    if row is None:
        raise APIError(404, "FRIEND_NOT_FOUND", "친구가 아닙니다.")
    return row


# --- 친구 목록 -------------------------------------------------------------

@router.get("/friends", response_model=list[FriendOut])
def list_friends(db: db_dependency, user: user_dependency):
    F = models.Friendship
    rows = db.scalars(
        select(F)
        .join(F.friend)
        .options(contains_eager(F.friend))
        .where(F.user_id == user.id)
        .order_by(models.User.display_name, models.User.id)
    ).all()
    return [{"user": row.friend, "sharing": row.levels()} for row in rows]


@router.delete("/friends/{user_id}", status_code=204)
def unfriend(user_id: int, db: db_dependency, user: user_dependency):
    F = models.Friendship
    result = db.execute(delete(F).where(or_(
        and_(F.user_id == user.id, F.friend_id == user_id),
        and_(F.user_id == user_id, F.friend_id == user.id),
    )))
    if result.rowcount == 0:
        raise APIError(404, "FRIEND_NOT_FOUND", "친구가 아닙니다.")
    db.commit()


# --- 친구 요청 -------------------------------------------------------------

@router.get("/friends/requests", response_model=list[FriendRequestOut])
def list_friend_requests(
    db: db_dependency,
    user: user_dependency,
    direction: Literal["incoming", "outgoing"] = "incoming",
):
    R = models.FriendRequest
    mine = R.to_user_id if direction == "incoming" else R.from_user_id
    return db.scalars(
        select(R)
        .options(joinedload(R.from_user), joinedload(R.to_user))
        .where(mine == user.id, R.status == "PENDING")
        .order_by(R.created_at.desc(), R.id.desc())
    ).all()


@router.post("/friends/requests", response_model=FriendRequestOut, status_code=201)
def send_friend_request(body: FriendRequestCreate, db: db_dependency, user: user_dependency):
    if body.to_user_id == user.id:
        raise APIError(400, "INVALID_FRIEND_REQUEST", "자기 자신에게는 친구 요청을 보낼 수 없습니다.")
    target = db.get(models.User, body.to_user_id)
    if target is None:
        raise APIError(404, "USER_NOT_FOUND", "유저를 찾을 수 없습니다.")
    if db.get(models.Friendship, (user.id, target.id)) is not None:
        raise APIError(409, "ALREADY_FRIENDS", "이미 친구입니다.")

    R = models.FriendRequest
    reverse = db.scalar(select(R).where(R.from_user_id == target.id, R.to_user_id == user.id, R.status == "PENDING"))
    if reverse is not None:
        # 상대가 이미 보낸 요청이 있으면 즉시 수락 처리한다. 응답의 status가 ACCEPTED.
        _accept(db, reverse)
        db.commit()
        return reverse

    req = db.scalar(select(R).where(R.from_user_id == user.id, R.to_user_id == target.id))
    if req is None:
        req = R(from_user_id=user.id, to_user_id=target.id, status="PENDING")
        db.add(req)
    elif req.status == "PENDING":
        raise APIError(409, "REQUEST_ALREADY_SENT", "이미 보낸 친구 요청이 있습니다.")
    else:
        # (from, to) 쌍마다 1행이라 재요청은 기존 행을 PENDING으로 되돌린다.
        req.status, req.created_at, req.responded_at = "PENDING", utc_now(), None
    db.commit()
    return req


@router.post("/friends/requests/{request_id}/accept", response_model=FriendRequestOut)
def accept_friend_request(request_id: int, db: db_dependency, user: user_dependency):
    req = _pending_request(db, user, request_id, incoming=True)
    _accept(db, req)
    db.commit()
    return req


@router.post("/friends/requests/{request_id}/decline", response_model=FriendRequestOut)
def decline_friend_request(request_id: int, db: db_dependency, user: user_dependency):
    req = _pending_request(db, user, request_id, incoming=True)
    req.status = "DECLINED"
    req.responded_at = utc_now()
    db.commit()
    return req


@router.delete("/friends/requests/{request_id}", status_code=204)
def cancel_friend_request(request_id: int, db: db_dependency, user: user_dependency):
    req = _pending_request(db, user, request_id, incoming=False)
    req.status = "CANCELLED"
    db.commit()


# --- 친구별 공유 수준 (내가 이 친구에게 보여 주는 수준) ----------------------

@router.get("/friends/{user_id}/sharing", response_model=SharingLevels)
def get_sharing(user_id: int, db: db_dependency, user: user_dependency):
    return _my_friendship(db, user, user_id).levels()


@router.patch("/friends/{user_id}/sharing", response_model=SharingLevels)
def update_sharing(user_id: int, body: SharingUpdate, db: db_dependency, user: user_dependency):
    row = _my_friendship(db, user, user_id)
    for kind, level in body.model_dump(by_alias=True, exclude_none=True).items():
        setattr(row, f"share_{kind}", level)
    db.commit()
    return row.levels()
