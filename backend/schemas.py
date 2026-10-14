from datetime import datetime, timezone
from typing import Annotated, Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, PlainSerializer


def _to_utc_z(value: datetime) -> str:
    # DB 값은 naive UTC. aware 값이 들어와도 UTC로 맞춘 뒤 'Z'로 내보낸다.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


UTCDateTime = Annotated[datetime, PlainSerializer(_to_utc_z, return_type=str)]

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: Optional[str]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CategoryOut(ORMModel):
    code: str
    name: str
    color: Optional[str]


class OrganizationBrief(ORMModel):
    id: int
    name: str


class OrganizationSummary(OrganizationBrief):
    slug: str
    logo_url: Optional[str]


class EventListItem(ORMModel):
    id: int
    title: str
    start_at: UTCDateTime
    end_at: UTCDateTime
    is_all_day: bool
    location_name: Optional[str]
    is_online: bool
    category: CategoryOut
    organization: Optional[OrganizationBrief]
    host_name: Optional[str]
    image_url: Optional[str]
    is_free: Optional[bool]
    status: Literal["ACTIVE", "CANCELLED"]


class EventDetail(EventListItem):
    organization: Optional[OrganizationSummary]
    description: Optional[str]
    source_url: Optional[str]
    address: Optional[str]
    online_url: Optional[str]
    registration_url: Optional[str]
    price_text: Optional[str]
    audience_text: Optional[str]
