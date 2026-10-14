"""수집기 사이에서 주고받는 데이터 형식."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .textutil import ny_midnight_utc

# event_categories.code (NYUEventSchema.sql 의 초기값과 같아야 한다)
CATEGORIES = {"SOCIAL", "CAREER", "SPORTS", "ACADEMIC", "ARTS", "WELLNESS", "OTHER"}
# 크롤러가 쓰는 상태. HIDDEN 은 관리자 전용이라 크롤러가 만들지 않는다.
STATUSES = {"ACTIVE", "CANCELLED"}

DEFAULT_DURATION = timedelta(hours=1)   # 종료 시각이 없으면 start_at + 1시간


@dataclass
class RawItem:
    """1단계 결과: 소스에서 받은 이벤트 하나의 원본.

    external_id 는 소스 안에서 이 이벤트를 가리키는 고유 ID (DB의 UNIQUE 키).
    payload 는 JSON으로 저장할 수 있는 dict (raw_events.payload 에 그대로 들어간다).
    """
    external_id: str
    payload: dict


@dataclass
class FetchResult:
    items: list[RawItem]
    # True 이면 이 소스의 '전체' 목록을 받은 것이므로, 목록에서 사라진 미래 이벤트를 취소 처리한다.
    complete: bool = False
    # complete 일 때 취소 처리를 적용할 범위의 끝 (None 이면 제한 없음)
    window_end_utc: datetime | None = None


@dataclass
class Organization:
    """organizations 테이블 한 줄. (source, external_id) 로 찾고 없으면 만든다."""
    external_id: str
    name: str
    slug: str
    website_url: str | None = None


@dataclass
class Event:
    """3단계 결과: 공통 형식으로 변환된 이벤트. events 테이블 한 줄에 대응한다.

    시간 규칙
      * 시간이 있는 이벤트: start_at/end_at (timezone-aware UTC datetime). end_at 이 없으면 +1시간.
      * 종일 이벤트: is_all_day=True 와 start_date/end_date (뉴욕 기준 날짜, end_date 포함) 만 채운다.
        저장할 때 resolve_times() 가 뉴욕 자정 기준 UTC 로 바꾼다 (end_at = 마지막 날 다음 날 자정).
    """
    external_id: str
    title: str
    category: str                     # event_categories.code
    is_all_day: bool = False
    start_at: datetime | None = None
    end_at: datetime | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str = "ACTIVE"
    description: str | None = None
    source_url: str | None = None
    host_name: str | None = None
    organization: Organization | None = None
    location_name: str | None = None
    address: str | None = None
    is_online: bool = False
    online_url: str | None = None
    registration_url: str | None = None
    image_url: str | None = None
    is_free: bool | None = None
    price_text: str | None = None
    audience_text: str | None = None
    # DB에는 저장하지 않는다. 분류와 --dry-run 출력용.
    tags: list[str] = field(default_factory=list)

    def resolve_times(self) -> tuple[datetime, datetime]:
        """DB 에 넣을 (start_at, end_at) — 둘 다 aware UTC."""
        if self.is_all_day:
            last = self.end_date or self.start_date
            return ny_midnight_utc(self.start_date), ny_midnight_utc(last + timedelta(days=1))
        return self.start_at, self.end_at or self.start_at + DEFAULT_DURATION

    def validate(self) -> None:
        if not self.title:
            raise ValueError("title 이 비어 있음")
        if self.category not in CATEGORIES:
            raise ValueError(f"알 수 없는 category: {self.category}")
        if self.status not in STATUSES:
            raise ValueError(f"알 수 없는 status: {self.status}")
        if self.is_all_day:
            if self.start_date is None:
                raise ValueError("종일 이벤트인데 start_date 가 없음")
            if self.end_date and self.end_date < self.start_date:
                raise ValueError("end_date 가 start_date 보다 빠름")
        else:
            if self.start_at is None:
                raise ValueError("start_at 이 없음")
            if self.start_at.tzinfo is None:
                raise ValueError("start_at 은 timezone-aware 여야 함")
            if self.end_at and self.end_at < self.start_at:
                raise ValueError("end_at 이 start_at 보다 빠름")
