"""Organizations (/organizations): browse, search, and follow.

Browsing is public. A logged-in viewer also sees which organizations they follow.
Following an organization feeds GET /events?followed_only=true and GET /users/me/following.
"""
from typing import Annotated, Optional

from fastapi import APIRouter, Query
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

import models
from auth import optional_user_dependency, user_dependency
from database import db_dependency
from errors import APIError
from pagination import decode_name_cursor, encode_name_cursor
from schemas import OrganizationDetail, OrganizationFollowOut, OrganizationListItem, OrganizationSummary, Page

router = APIRouter(tags=["organizations"])


def _existing_organization(db: Session, org_id: int) -> models.Organization:
    organization = db.get(models.Organization, org_id)
    if organization is None:
        raise APIError(404, "ORGANIZATION_NOT_FOUND", "Organization not found.")
    return organization


def _followed_ids(db: Session, user: Optional[models.User], org_ids: list[int]) -> set[int]:
    """Which of these organizations the user follows. One query; empty for anonymous requests."""
    if user is None or not org_ids:
        return set()
    Follow = models.OrganizationFollow
    return set(db.scalars(
        select(Follow.organization_id).where(Follow.user_id == user.id, Follow.organization_id.in_(org_ids))
    ))


@router.get("/organizations", response_model=Page[OrganizationListItem])
def list_organizations(
    db: db_dependency,
    user: optional_user_dependency,
    q: Annotated[Optional[str], Query(max_length=100, description="Part of the name")] = None,
    cursor: Optional[str] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    Organization = models.Organization
    stmt = select(Organization)
    query = (q or "").strip()
    if query:
        # The column collation ignores case. % and _ are matched literally.
        stmt = stmt.where(Organization.name.contains(query, autoescape=True))
    if cursor:
        cursor_name, cursor_id = decode_name_cursor(cursor)
        stmt = stmt.where(or_(
            Organization.name > cursor_name,
            and_(Organization.name == cursor_name, Organization.id > cursor_id),
        ))

    rows = db.scalars(stmt.order_by(Organization.name, Organization.id).limit(limit + 1)).all()
    items = rows[:limit]
    followed = _followed_ids(db, user, [organization.id for organization in items])
    next_cursor = encode_name_cursor(items[-1].name, items[-1].id) if len(rows) > limit else None
    return {
        "items": [
            {**OrganizationSummary.model_validate(organization).model_dump(), "is_following": organization.id in followed}
            for organization in items
        ],
        "next_cursor": next_cursor,
    }


@router.get("/organizations/{org_id}", response_model=OrganizationDetail)
def get_organization(org_id: int, db: db_dependency, user: optional_user_dependency):
    detail = OrganizationDetail.model_validate(_existing_organization(db, org_id))
    Follow = models.OrganizationFollow
    detail.follower_count = db.scalar(
        select(func.count()).select_from(Follow).where(Follow.organization_id == org_id)
    )
    detail.is_following = org_id in _followed_ids(db, user, [org_id])
    return detail


@router.put("/organizations/{org_id}/follow", response_model=OrganizationFollowOut)
def follow_organization(org_id: int, db: db_dependency, user: user_dependency):
    """Follow. Sending it again changes nothing, so a double tap is not an error."""
    _existing_organization(db, org_id)
    # INSERT IGNORE: an existing follow is left as it is. The organization was checked above.
    db.execute(
        mysql_insert(models.OrganizationFollow).prefix_with("IGNORE").values(user_id=user.id, organization_id=org_id)
    )
    db.commit()
    return {"organization_id": org_id, "is_following": True}


@router.delete("/organizations/{org_id}/follow", status_code=204)
def unfollow_organization(org_id: int, db: db_dependency, user: user_dependency):
    """Unfollow. Succeeds even if the user was not following."""
    Follow = models.OrganizationFollow
    db.execute(delete(Follow).where(Follow.user_id == user.id, Follow.organization_id == org_id))
    db.commit()
