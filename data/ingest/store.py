"""2단계(원본 저장)와 4단계(정규 테이블 저장)의 MySQL 쿼리 모음."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from .models import Event, Organization, RawItem


def _naive_utc(dt: datetime | None) -> datetime | None:
    """aware datetime → MySQL DATETIME 에 넣을 naive UTC (초 단위로 자름)."""
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).replace(tzinfo=None, microsecond=0)


def utc_now() -> datetime:
    """현재 UTC (naive). 같은 초에 두 번 실행해도 구분되도록 마이크로초를 남긴다."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def start_run(cur, source: str, started_at: datetime) -> int:
    cur.execute(
        "INSERT INTO ingest_runs (source, started_at, status) VALUES (%s, %s, 'running')",
        (source, started_at),
    )
    return cur.lastrowid


def finish_run(cur, run_id: int, status: str, counts: dict, error: str | None = None) -> None:
    cur.execute(
        """
        UPDATE ingest_runs
           SET finished_at = %s, status = %s, fetched_count = %s, changed_count = %s,
               upserted_count = %s, skipped_count = %s, canceled_count = %s, error = %s
         WHERE id = %s
        """,
        (utc_now(), status, counts.get("fetched", 0), counts.get("changed", 0),
         counts.get("upserted", 0), counts.get("skipped", 0), counts.get("canceled", 0),
         (error or None) and error[:60000], run_id),
    )


def payload_json(payload: dict) -> str:
    # sort_keys: 같은 내용이면 항상 같은 문자열 → 같은 해시
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)


def save_raw(cur, source: str, item: RawItem, seen_at: datetime) -> bool:
    """원본을 저장하고, 새로 생겼거나 내용이 바뀌었으면 True 를 돌려준다.

    내용이 같으면 last_seen_at 만 갱신한다 (피드에 아직 있다는 표시).
    """
    body = payload_json(item.payload)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()

    cur.execute(
        "SELECT payload_hash FROM raw_events WHERE source = %s AND external_id = %s",
        (source, item.external_id),
    )
    row = cur.fetchone()

    if row is None:
        cur.execute(
            """
            INSERT INTO raw_events
                (source, external_id, payload, payload_hash, first_seen_at, last_seen_at, fetched_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (source, item.external_id, body, digest, seen_at, seen_at, seen_at),
        )
        return True

    if row[0] != digest:
        cur.execute(
            """
            UPDATE raw_events SET payload = %s, payload_hash = %s, last_seen_at = %s, fetched_at = %s
             WHERE source = %s AND external_id = %s
            """,
            (body, digest, seen_at, seen_at, source, item.external_id),
        )
        return True

    cur.execute(
        "UPDATE raw_events SET last_seen_at = %s WHERE source = %s AND external_id = %s",
        (seen_at, source, item.external_id),
    )
    return False


class Lookup:
    """event_categories 코드 → id, organizations (source, external_id) → id 를 실행 중에 캐시한다."""

    def __init__(self):
        self.categories: dict[str, int] = {}
        self.organizations: dict[tuple[str, str], int] = {}

    def category_id(self, cur, code: str) -> int:
        if not self.categories:
            cur.execute("SELECT code, id FROM event_categories")
            self.categories = {c: i for c, i in cur.fetchall()}
        if code not in self.categories:
            raise ValueError(f"event_categories 에 없는 코드: {code} (NYUEventSchema.sql 초기값 확인)")
        return self.categories[code]

    def organization_id(self, cur, source: str, org: Organization | None) -> int | None:
        """단체를 (source, external_id) 로 찾고, 없으면 만든다.

        이미 있는 단체는 덮어쓰지 않는다 — 관리자가 PATCH /admin/organizations 로 고친 이름·소개를 지키기 위해.
        """
        if org is None:
            return None
        key = (source, org.external_id)
        if key in self.organizations:
            return self.organizations[key]

        cur.execute("SELECT id FROM organizations WHERE source = %s AND external_id = %s", key)
        row = cur.fetchone()
        if row is None:
            slug = self._free_slug(cur, org.slug or "org", org.external_id)
            cur.execute(
                "INSERT INTO organizations (slug, name, website_url, source, external_id) "
                "VALUES (%s, %s, %s, %s, %s)",
                (slug, org.name[:200], org.website_url, source, org.external_id),
            )
            row = (cur.lastrowid,)
        self.organizations[key] = row[0]
        return row[0]

    @staticmethod
    def _free_slug(cur, slug: str, external_id: str) -> str:
        """slug 는 전체에서 UNIQUE 이므로, 이미 쓰이고 있으면 external_id 를 붙인다."""
        slug = slug[:200]
        cur.execute("SELECT 1 FROM organizations WHERE slug = %s", (slug,))
        if cur.fetchone() is None:
            return slug
        suffix = "-" + "".join(ch for ch in external_id.lower() if ch.isalnum())[:30]
        return slug[: 200 - len(suffix)] + suffix


_EVENT_COLUMNS = (
    "source", "external_id", "source_url", "title", "description", "category_id",
    "organization_id", "host_name", "start_at", "end_at", "is_all_day",
    "location_name", "address", "is_online", "online_url", "registration_url", "image_url",
    "is_free", "price_text", "audience_text", "status", "last_synced_at",
)
_UPDATE_COLUMNS = [c for c in _EVENT_COLUMNS if c not in ("source", "external_id", "status")]
_UPSERT_SQL = (
    f"INSERT INTO events ({', '.join(_EVENT_COLUMNS)}) "
    f"VALUES ({', '.join(['%s'] * len(_EVENT_COLUMNS))}) AS new "
    "ON DUPLICATE KEY UPDATE "
    + ", ".join(f"{c} = new.{c}" for c in _UPDATE_COLUMNS)
    # 관리자가 숨긴(HIDDEN) 이벤트는 크롤러가 다시 살리지 않는다
    + ", status = IF(events.status = 'HIDDEN', 'HIDDEN', new.status)"
)


def upsert_event(cur, source: str, event: Event, lookup: Lookup, synced_at: datetime) -> int:
    """events 에 넣거나(새 이벤트) 갱신하고(기존 이벤트) id 를 돌려준다."""
    event.validate()
    start_at, end_at = event.resolve_times()
    values = (
        source,
        event.external_id[:255],
        event.source_url,
        event.title[:255],
        event.description,
        lookup.category_id(cur, event.category),
        lookup.organization_id(cur, source, event.organization),
        (event.host_name or None) and event.host_name[:200],
        _naive_utc(start_at),
        _naive_utc(end_at),
        event.is_all_day,
        (event.location_name or None) and event.location_name[:255],
        (event.address or None) and event.address[:255],
        event.is_online,
        event.online_url,
        event.registration_url,
        event.image_url,
        event.is_free,
        (event.price_text or None) and event.price_text[:100],
        (event.audience_text or None) and event.audience_text[:255],
        event.status,
        synced_at.replace(microsecond=0),
    )
    cur.execute(_UPSERT_SQL, values)
    cur.execute(
        "SELECT id FROM events WHERE source = %s AND external_id = %s",
        (source, event.external_id[:255]),
    )
    return cur.fetchone()[0]


def touch_synced(cur, source: str, seen_at: datetime) -> int:
    """이번 실행에서 피드에 보인(내용은 안 바뀐) 이벤트의 last_synced_at 을 갱신한다.

    updated_at 은 그대로 둔다 — '내용이 바뀐 시각'으로 쓸 수 있게.
    """
    return cur.execute(
        """
        UPDATE events e
          JOIN raw_events r ON r.source = e.source AND r.external_id = e.external_id
           SET e.last_synced_at = %s, e.updated_at = e.updated_at
         WHERE r.source = %s AND r.last_seen_at = %s
        """,
        (seen_at.replace(microsecond=0), source, seen_at),
    )


def cancel_missing(cur, source: str, run_started_at: datetime,
                   window_end_utc: datetime | None) -> int:
    """이번 실행에서 피드에 안 보인 '미래' 이벤트를 CANCELLED 로 바꾼다. 지우지는 않는다.

    (유저가 저장한 이벤트(event_saves)가 말없이 사라지는 것을 막기 위해 DELETE 하지 않음.
     관리자가 숨긴 HIDDEN 이벤트는 건드리지 않는다.)
    """
    sql = """
        SELECT e.external_id
          FROM events e
          JOIN raw_events r
            ON r.source = e.source AND r.external_id = e.external_id
         WHERE e.source = %s
           AND r.last_seen_at < %s
           AND e.status = 'ACTIVE'
           AND e.start_at >= %s
    """
    params: list = [source, run_started_at, run_started_at.replace(microsecond=0)]
    if window_end_utc is not None:
        sql += " AND e.start_at < %s"
        params.append(_naive_utc(window_end_utc))
    cur.execute(sql, params)
    missing = [row[0] for row in cur.fetchall()]

    for i in range(0, len(missing), 500):
        chunk = missing[i:i + 500]
        marks = ", ".join(["%s"] * len(chunk))
        # 1) 원본 해시를 비워둔다 → 나중에 피드에 다시 나타나면 '바뀜'으로 잡혀서
        #    다시 변환되고 status 도 ACTIVE 로 돌아온다.
        cur.execute(f"UPDATE raw_events SET payload_hash = '' "
                    f"WHERE source = %s AND external_id IN ({marks})", [source, *chunk])
        cur.execute(f"UPDATE events SET status = 'CANCELLED' "
                    f"WHERE source = %s AND external_id IN ({marks})", [source, *chunk])
    return len(missing)
