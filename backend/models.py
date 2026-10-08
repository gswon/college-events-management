# 스키마 원본은 NYUEventSchema.sql. 여기 모델은 그 DDL에 맞춘 매핑일 뿐 테이블을 만들지 않는다.
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.mysql import BIGINT, CHAR, TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


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
