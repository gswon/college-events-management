from datetime import datetime, timezone
from typing import Annotated, Generic, Literal, Optional, TypeVar, Union

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, PlainSerializer, StringConstraints, model_validator


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


class UserBrief(ORMModel):
    id: int
    display_name: str
    profile_image_url: Optional[str]


# --- 내 일정 (/entries) ---------------------------------------------------

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
Location = Annotated[str, StringConstraints(max_length=255)]
HexColor = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]
VisibilityOverride = Literal["HIDDEN", "BUSY"]


class EntryCreate(BaseModel):
    title: Title
    description: Optional[str] = None
    location: Optional[Location] = None
    start_at: AwareDatetime
    end_at: AwareDatetime
    is_all_day: bool = False
    color: Optional[HexColor] = None
    visibility_override: Optional[VisibilityOverride] = None


class EntryUpdate(BaseModel):
    """보낸 필드만 바꾼다. null은 비울 수 있는 필드에만 허용."""

    title: Optional[Title] = None
    description: Optional[str] = None
    location: Optional[Location] = None
    start_at: Optional[AwareDatetime] = None
    end_at: Optional[AwareDatetime] = None
    is_all_day: Optional[bool] = None
    color: Optional[HexColor] = None
    visibility_override: Optional[VisibilityOverride] = None

    @model_validator(mode="after")
    def _reject_null_required(self):
        nulls = [f for f in ("title", "start_at", "end_at", "is_all_day")
                 if f in self.model_fields_set and getattr(self, f) is None]
        if nulls:
            raise ValueError(f"null일 수 없습니다: {', '.join(nulls)}")
        return self


class EntryOut(ORMModel):
    id: int
    kind: Literal["CLASS", "PERSONAL"]
    title: str
    description: Optional[str]
    location: Optional[str]
    start_at: UTCDateTime
    end_at: UTCDateTime
    is_all_day: bool
    color: Optional[str]
    course_code: Optional[str]
    visibility_override: Optional[VisibilityOverride]


# --- 캘린더 항목 (type만 보고 프론트가 색·아이콘을 고른다) ----------------

class EntryItem(BaseModel):
    type: Literal["CLASS", "PERSONAL"]
    id: int
    title: str
    start_at: UTCDateTime
    end_at: UTCDateTime
    is_all_day: bool
    location: Optional[str]


class EventItem(BaseModel):
    type: Literal["EVENT"] = "EVENT"
    id: int
    title: str
    start_at: UTCDateTime
    end_at: UTCDateTime
    is_all_day: bool
    location: Optional[str]
    category: str
    save_status: Literal["INTERESTED", "GOING"]
    is_cancelled: bool


class BusyItem(BaseModel):
    """친구가 BUSY로 공유한 항목. 제목·장소·ID 없이 시간대만."""

    type: Literal["BUSY"] = "BUSY"
    start_at: UTCDateTime
    end_at: UTCDateTime


CalendarItem = Annotated[Union[EntryItem, EventItem, BusyItem], Field(discriminator="type")]


class UserCalendar(BaseModel):
    user_id: int
    items: list[CalendarItem]


# --- 친구 / 공유 -----------------------------------------------------------

ShareLevel = Literal["HIDDEN", "BUSY", "DETAILS"]


class SharingLevels(BaseModel):
    # JSON 키는 class/personal/event. class는 파이썬 예약어라 alias로 받는다.
    class_: ShareLevel = Field(alias="class")
    personal: ShareLevel
    event: ShareLevel


class SharingUpdate(BaseModel):
    class_: Optional[ShareLevel] = Field(default=None, alias="class")
    personal: Optional[ShareLevel] = None
    event: Optional[ShareLevel] = None


class FriendOut(BaseModel):
    user: UserBrief
    sharing: SharingLevels  # 내가 이 친구에게 공유하는 수준


class FriendRequestCreate(BaseModel):
    to_user_id: int


class FriendRequestOut(ORMModel):
    id: int
    from_user: UserBrief
    to_user: UserBrief
    status: Literal["PENDING", "ACCEPTED", "DECLINED", "CANCELLED"]
    created_at: UTCDateTime
