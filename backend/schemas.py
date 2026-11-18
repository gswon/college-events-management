import string
from datetime import datetime, timezone
from typing import Annotated, Generic, Literal, Optional, TypeVar, Union

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    model_validator,
)

from models import SHARE_LEVELS


def _to_utc_z(value: datetime) -> str:
    # DB values are naive UTC. An aware value is converted to UTC too, then written with 'Z'.
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


class UserBrief(ORMModel):
    id: int
    display_name: str
    profile_image_url: Optional[str]


# INTERESTED or GOING. Saving an event puts it on the user's calendar.
SaveStatus = Literal["INTERESTED", "GOING"]


class EventSaveIn(BaseModel):
    status: SaveStatus


class EventSaveOut(BaseModel):
    event_id: int
    status: SaveStatus


class EventDetail(EventListItem):
    organization: Optional[OrganizationSummary]
    description: Optional[str]
    source_url: Optional[str]
    address: Optional[str]
    online_url: Optional[str]
    registration_url: Optional[str]
    price_text: Optional[str]
    audience_text: Optional[str]
    # Filled in only for a logged-in viewer; anonymous requests get null / 0 / [].
    my_save_status: Optional[SaveStatus] = None
    # Friends who are GOING and share events with me at DETAILS. Friends sharing BUSY are not counted.
    friends_going_count: int = 0
    friends_going: list[UserBrief] = []  # up to 3, by name


# How a user relates to me. REQUESTED = I sent a pending request, RECEIVED = they sent one to me.
FriendStatus = Literal["NONE", "REQUESTED", "RECEIVED", "FRIENDS"]


class UserSearchItem(UserBrief):
    """A search result. Never includes the email, so a name search cannot collect addresses."""

    friend_status: FriendStatus


# --- My entries (/entries) -----------------------------------------------

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
    """Only the fields sent are changed. null is allowed only for fields that can be empty."""

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
            raise ValueError(f"Cannot be null: {', '.join(nulls)}")
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


# --- Calendar items (the app picks colors and icons from type alone) --------

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
    save_status: SaveStatus
    is_cancelled: bool


class BusyItem(BaseModel):
    """An item a friend shares as BUSY: only the time, no title, place or id."""

    type: Literal["BUSY"] = "BUSY"
    start_at: UTCDateTime
    end_at: UTCDateTime


CalendarItem = Annotated[Union[EntryItem, EventItem, BusyItem], Field(discriminator="type")]


class UserCalendar(BaseModel):
    user_id: int
    items: list[CalendarItem]


# --- Friends / sharing -----------------------------------------------------

ShareLevel = Literal[SHARE_LEVELS]


class SharingLevels(BaseModel):
    # JSON keys are class/personal/event. `class` is a Python keyword, hence the alias.
    class_: ShareLevel = Field(alias="class")
    personal: ShareLevel
    event: ShareLevel


class SharingUpdate(BaseModel):
    class_: Optional[ShareLevel] = Field(default=None, alias="class")
    personal: Optional[ShareLevel] = None
    event: Optional[ShareLevel] = None


class FriendOut(BaseModel):
    user: UserBrief
    sharing: SharingLevels  # what I share with this friend


class FriendRequestCreate(BaseModel):
    to_user_id: int


class FriendRequestOut(ORMModel):
    id: int
    from_user: UserBrief
    to_user: UserBrief
    status: Literal["PENDING", "ACCEPTED", "DECLINED", "CANCELLED"]
    created_at: UTCDateTime


# --- Auth (/auth, /users/me/password) ------------------------------------

Email = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
]
# Login and current passwords go to Supabase as they are, with no rules. 72 = bcrypt's limit.
Password = Annotated[str, StringConstraints(min_length=1, max_length=72)]
# New password rules. Must match the Supabase dashboard setting: 8+ characters with at least one
# lowercase letter, uppercase letter, digit and symbol. A reset code works only once, so a weak
# password must be caught here before Supabase rejects it. The character sets are those of Supabase's
# "Lowercase, uppercase letters, digits and symbols" option.
_PASSWORD_CHAR_SETS = (
    ("a lowercase letter", string.ascii_lowercase),
    ("an uppercase letter", string.ascii_uppercase),
    ("a number", string.digits),
    ("a symbol", "!@#$%^&*()_+-=[]{};'\\:\"|<>?,./`~"),
)


def _check_password_chars(value: str) -> str:
    missing = [name for name, chars in _PASSWORD_CHAR_SETS if not any(c in chars for c in value)]
    if missing:
        raise ValueError(f"Password must include {', '.join(missing)}.")
    return value


NewPassword = Annotated[str, StringConstraints(min_length=8, max_length=72), AfterValidator(_check_password_chars)]
OtpCode = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d{6,10}$")]
DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


class SignupIn(BaseModel):
    email: Email
    password: NewPassword
    display_name: DisplayName


class SignupOut(BaseModel):
    email: str  # where the verification code was sent


class EmailIn(BaseModel):
    email: Email


class VerifyEmailIn(BaseModel):
    email: Email
    code: OtpCode


class LoginIn(BaseModel):
    email: Email
    password: Password


class RefreshIn(BaseModel):
    refresh_token: Annotated[str, StringConstraints(min_length=1)]


class PasswordChangeIn(BaseModel):
    current_password: Password
    new_password: NewPassword


class PasswordResetIn(BaseModel):
    email: Email
    code: OtpCode
    new_password: NewPassword


class MeOut(ORMModel):
    id: int
    email: str
    display_name: str
    profile_image_url: Optional[str]


# Up to 500 characters: the size of users.profile_image_url.
ImageUrl = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500, pattern=r"^https?://\S+$")]


class MeUpdate(BaseModel):
    """Only the fields sent are changed. Send profile_image_url: null to remove the photo."""

    display_name: Optional[DisplayName] = None
    profile_image_url: Optional[ImageUrl] = None

    @model_validator(mode="after")
    def _reject_null_name(self):
        if "display_name" in self.model_fields_set and self.display_name is None:
            raise ValueError("Cannot be null: display_name")
        return self


class AuthSession(BaseModel):
    """The app keeps both tokens in SecureStore and calls the API with Authorization: Bearer <access_token>."""

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # access_token lifetime in seconds
    user: MeOut
