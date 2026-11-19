from typing import Literal

from fastapi import APIRouter
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session, contains_eager, joinedload

import models
from auth import user_dependency
from database import db_dependency
from errors import APIError
from schemas import FriendOut, FriendRequestCreate, FriendRequestOut, SharingLevels, SharingUpdate
from timeutil import utc_now

router = APIRouter(tags=["friends"])


def _make_friends(db: Session, a: models.User, b: models.User) -> None:
    # Two rows, one per direction. Each side's default share levels are copied into its own row.
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
        raise APIError(404, "REQUEST_NOT_FOUND", "Friend request not found.")
    if req.status != "PENDING":
        raise APIError(409, "REQUEST_NOT_PENDING", "This friend request was already handled.")
    return req


def _my_friendship(db: Session, user: models.User, friend_id: int) -> models.Friendship:
    row = db.get(models.Friendship, (user.id, friend_id))
    if row is None:
        raise APIError(404, "FRIEND_NOT_FOUND", "This user is not your friend.")
    return row


# --- Friends -----------------------------------------------------------------

@router.get("/friends", response_model=list[FriendOut])
def list_friends(db: db_dependency, user: user_dependency):
    Friendship = models.Friendship
    rows = db.scalars(
        select(Friendship)
        .join(Friendship.friend)
        .options(contains_eager(Friendship.friend))
        .where(Friendship.user_id == user.id)
        .order_by(models.User.display_name, models.User.id)
    ).all()
    return [{"user": row.friend, "sharing": row.levels()} for row in rows]


@router.delete("/friends/{user_id}", status_code=204)
def unfriend(user_id: int, db: db_dependency, user: user_dependency):
    Friendship = models.Friendship
    result = db.execute(delete(Friendship).where(or_(
        and_(Friendship.user_id == user.id, Friendship.friend_id == user_id),
        and_(Friendship.user_id == user_id, Friendship.friend_id == user.id),
    )))
    if result.rowcount == 0:
        raise APIError(404, "FRIEND_NOT_FOUND", "This user is not your friend.")
    db.commit()


# --- Friend requests ---------------------------------------------------------

@router.get("/friends/requests", response_model=list[FriendRequestOut])
def list_friend_requests(
    db: db_dependency,
    user: user_dependency,
    direction: Literal["incoming", "outgoing"] = "incoming",
):
    FriendRequest = models.FriendRequest
    mine = FriendRequest.to_user_id if direction == "incoming" else FriendRequest.from_user_id
    return db.scalars(
        select(FriendRequest)
        .options(joinedload(FriendRequest.from_user), joinedload(FriendRequest.to_user))
        .where(mine == user.id, FriendRequest.status == "PENDING")
        .order_by(FriendRequest.created_at.desc(), FriendRequest.id.desc())
    ).all()


@router.post("/friends/requests", response_model=FriendRequestOut, status_code=201)
def send_friend_request(body: FriendRequestCreate, db: db_dependency, user: user_dependency):
    if body.to_user_id == user.id:
        raise APIError(400, "INVALID_FRIEND_REQUEST", "You cannot send a friend request to yourself.")
    target = db.get(models.User, body.to_user_id)
    if target is None:
        raise APIError(404, "USER_NOT_FOUND", "User not found.")
    if db.get(models.Friendship, (user.id, target.id)) is not None:
        raise APIError(409, "ALREADY_FRIENDS", "You are already friends.")

    FriendRequest = models.FriendRequest
    reverse = db.scalar(select(FriendRequest).where(
        FriendRequest.from_user_id == target.id,
        FriendRequest.to_user_id == user.id,
        FriendRequest.status == "PENDING",
    ))
    if reverse is not None:
        # They already sent us a request, so accept it right away. The response status is ACCEPTED.
        _accept(db, reverse)
        db.commit()
        return reverse

    req = db.scalar(select(FriendRequest).where(
        FriendRequest.from_user_id == user.id,
        FriendRequest.to_user_id == target.id,
    ))
    if req is None:
        req = FriendRequest(from_user_id=user.id, to_user_id=target.id, status="PENDING")
        db.add(req)
    elif req.status == "PENDING":
        raise APIError(409, "REQUEST_ALREADY_SENT", "You already sent a friend request.")
    else:
        # There is one row per (from, to) pair, so sending again resets the old row to PENDING.
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


# --- Per-friend share levels (what I show this friend) ----------------------

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
