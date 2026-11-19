"""Users (/users): my own profile and finding other users.

PUT /users/me/password lives in routers/account.py because it goes through Supabase Auth.
Keep fixed paths like /users/me and /users/search above any future /users/{user_id} route.
"""
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

import models
from auth import user_dependency
from database import db_dependency
from errors import APIError
from schemas import MeOut, MeUpdate, OrganizationSummary, UserSearchItem

router = APIRouter(tags=["users"])

SEARCH_LIMIT = 20
# One-letter name searches would list almost everyone.
MIN_NAME_QUERY_LENGTH = 2


# --- Me -----------------------------------------------------------------------

@router.get("/users/me", response_model=MeOut)
def get_me(user: user_dependency):
    return user


@router.patch("/users/me", response_model=MeOut)
def update_me(body: MeUpdate, db: db_dependency, user: user_dependency):
    # The display name lives in MySQL. Supabase's copy is only read once, at the first login.
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    return user


@router.get("/users/me/following", response_model=list[OrganizationSummary])
def my_following(db: db_dependency, user: user_dependency):
    """Organizations I follow, by name. Not paginated: one person follows only a handful."""
    Organization, Follow = models.Organization, models.OrganizationFollow
    return db.scalars(
        select(Organization)
        .join(Follow, Follow.organization_id == Organization.id)
        .where(Follow.user_id == user.id)
        .order_by(Organization.name, Organization.id)
    ).all()


# --- Search -------------------------------------------------------------------

def _friend_statuses(db: Session, me_id: int, other_ids: list[int]) -> dict[int, str]:
    """friend_status of each user toward me. Two queries however many users there are."""
    statuses = dict.fromkeys(other_ids, "NONE")
    if not other_ids:
        return statuses

    Request = models.FriendRequest
    pending = db.execute(
        select(Request.from_user_id, Request.to_user_id).where(
            Request.status == "PENDING",
            or_(
                and_(Request.from_user_id == me_id, Request.to_user_id.in_(other_ids)),
                and_(Request.to_user_id == me_id, Request.from_user_id.in_(other_ids)),
            ),
        )
    )
    for from_id, to_id in pending:
        if from_id == me_id:
            statuses[to_id] = "REQUESTED"
        else:
            statuses[from_id] = "RECEIVED"

    Friendship = models.Friendship
    friend_ids = db.scalars(
        select(Friendship.friend_id).where(Friendship.user_id == me_id, Friendship.friend_id.in_(other_ids))
    )
    for friend_id in friend_ids:  # Being friends wins over any leftover request.
        statuses[friend_id] = "FRIENDS"
    return statuses


@router.get("/users/search", response_model=list[UserSearchItem])
def search_users(
    db: db_dependency,
    user: user_dependency,
    q: Annotated[str, Query(min_length=1, max_length=100, description="An exact email, or part of a name")],
):
    query = q.strip()
    User = models.User
    if "@" in query:
        # Exact match only, so nobody can list addresses by searching "@nyu.edu".
        condition = User.email == query.lower()
    elif len(query) < MIN_NAME_QUERY_LENGTH:
        raise APIError(400, "QUERY_TOO_SHORT", f"Search by name needs at least {MIN_NAME_QUERY_LENGTH} characters.")
    else:
        # The column collation ignores case and accents. % and _ are matched literally.
        condition = User.display_name.contains(query, autoescape=True)

    users = db.scalars(
        select(User).where(condition, User.id != user.id).order_by(User.display_name, User.id).limit(SEARCH_LIMIT)
    ).all()
    statuses = _friend_statuses(db, user.id, [found.id for found in users])
    return [
        {
            "id": found.id,
            "display_name": found.display_name,
            "profile_image_url": found.profile_image_url,
            "friend_status": statuses[found.id],
        }
        for found in users
    ]
