# 스키마 원본은 NYUEventSchema.sql. 여기 모델은 그 DDL에 맞춘 매핑일 뿐 테이블을 만들지 않는다.
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.mysql import BIGINT, CHAR, TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

SHARE_LEVELS = ("HIDDEN", "BUSY", "DETAILS")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(50))
    profile_image_url: Mapped[Optional[str]] = mapped_column(String(500))
    role: Mapped[str] = mapped_column(Enum("USER", "ADMIN"), default="USER")
    # 새 친구가 생길 때 friendships 행으로 복사되는 기본 공유 수준
    default_share_class: Mapped[str] = mapped_column(Enum(*SHARE_LEVELS), default="DETAILS")
    default_share_personal: Mapped[str] = mapped_column(Enum(*SHARE_LEVELS), default="BUSY")
    default_share_event: Mapped[str] = mapped_column(Enum(*SHARE_LEVELS), default="DETAILS")
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), server_onupdate=func.current_timestamp()
    )


class EventCategory(Base):
    __tablename__ = "event_categories"

    id: Mapped[int] = mapped_column(TINYINT(unsigned=True), primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(50))
    color: Mapped[Optional[str]] = mapped_column(CHAR(7))
    sort_order: Mapped[int] = mapped_column(TINYINT(unsigned=True), default=0)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    website_url: Mapped[Optional[str]] = mapped_column(String(500))
    instagram_handle: Mapped[Optional[str]] = mapped_column(String(100))
    logo_url: Mapped[Optional[str]] = mapped_column(String(500))
    source: Mapped[Optional[str]] = mapped_column(String(50))
    external_id: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), server_onupdate=func.current_timestamp()
    )


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    source: Mapped[str] = mapped_column(String(50))
    external_id: Mapped[Optional[str]] = mapped_column(String(255))
    source_url: Mapped[Optional[str]] = mapped_column(String(500))

    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    category_id: Mapped[int] = mapped_column(TINYINT(unsigned=True), ForeignKey("event_categories.id"))
    organization_id: Mapped[Optional[int]] = mapped_column(BIGINT(unsigned=True), ForeignKey("organizations.id"))
    host_name: Mapped[Optional[str]] = mapped_column(String(200))

    start_at: Mapped[datetime] = mapped_column(DateTime)
    end_at: Mapped[datetime] = mapped_column(DateTime)
    is_all_day: Mapped[bool] = mapped_column(Boolean, default=False)

    location_name: Mapped[Optional[str]] = mapped_column(String(255))
    address: Mapped[Optional[str]] = mapped_column(String(255))
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    online_url: Mapped[Optional[str]] = mapped_column(String(500))

    registration_url: Mapped[Optional[str]] = mapped_column(String(500))
    image_url: Mapped[Optional[str]] = mapped_column(String(500))
    is_free: Mapped[Optional[bool]] = mapped_column(Boolean)
    price_text: Mapped[Optional[str]] = mapped_column(String(100))
    audience_text: Mapped[Optional[str]] = mapped_column(String(255))

    status: Mapped[str] = mapped_column(Enum("ACTIVE", "CANCELLED", "HIDDEN"), default="ACTIVE")
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), server_onupdate=func.current_timestamp()
    )

    category: Mapped[EventCategory] = relationship()
    organization: Mapped[Optional[Organization]] = relationship()


class EventSave(Base):
    __tablename__ = "event_saves"

    user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id"), primary_key=True)
    event_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("events.id"), primary_key=True)
    status: Mapped[str] = mapped_column(Enum("INTERESTED", "GOING"), default="INTERESTED")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), server_onupdate=func.current_timestamp()
    )

    event: Mapped[Event] = relationship()


class CalendarEntry(Base):
    __tablename__ = "calendar_entries"

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(Enum("CLASS", "PERSONAL"))
    # schedule_imports FK. 시간표 import API를 만들 때 그 모델과 relationship을 붙인다.
    schedule_import_id: Mapped[Optional[int]] = mapped_column(BIGINT(unsigned=True))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    location: Mapped[Optional[str]] = mapped_column(String(255))
    start_at: Mapped[datetime] = mapped_column(DateTime)
    end_at: Mapped[datetime] = mapped_column(DateTime)
    is_all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    color: Mapped[Optional[str]] = mapped_column(CHAR(7))
    course_code: Mapped[Optional[str]] = mapped_column(String(50))
    ics_uid: Mapped[Optional[str]] = mapped_column(String(255))
    # 친구 공유 수준을 이 항목만 더 낮춘다. NULL = 친구 설정 그대로
    visibility_override: Mapped[Optional[str]] = mapped_column(Enum("HIDDEN", "BUSY"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), server_onupdate=func.current_timestamp()
    )


class FriendRequest(Base):
    __tablename__ = "friend_requests"

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    from_user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id"))
    to_user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(
        Enum("PENDING", "ACCEPTED", "DECLINED", "CANCELLED"), default="PENDING"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    from_user: Mapped[User] = relationship(foreign_keys=[from_user_id])
    to_user: Mapped[User] = relationship(foreign_keys=[to_user_id])


class Friendship(Base):
    """친구 1쌍 = 2행. 행 (user_id=A, friend_id=B) 는 "A가 B에게 공유하는 수준"."""

    __tablename__ = "friendships"

    user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id"), primary_key=True)
    friend_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id"), primary_key=True)
    share_class: Mapped[str] = mapped_column(Enum(*SHARE_LEVELS))
    share_personal: Mapped[str] = mapped_column(Enum(*SHARE_LEVELS))
    share_event: Mapped[str] = mapped_column(Enum(*SHARE_LEVELS))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), server_onupdate=func.current_timestamp()
    )

    friend: Mapped[User] = relationship(foreign_keys=[friend_id])

    def levels(self) -> dict[str, str]:
        return {"class": self.share_class, "personal": self.share_personal, "event": self.share_event}
