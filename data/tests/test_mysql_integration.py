"""실제 MySQL 에 스키마 적용 + 1~4단계 전체를 돌려보는 통합 테스트.

테스트용 빈 DB가 있을 때만 실행된다 (그 DB의 테이블을 전부 지우고 다시 만든다!):
  docker compose up -d
  docker compose exec mysql mysql -uroot -proot-change-me -e "CREATE DATABASE IF NOT EXISTS nyu_events_test"
  TEST_DB_NAME=nyu_events_test TEST_DB_USER=root TEST_DB_PASSWORD=root-change-me python -m pytest
"""
import os
import re

import pymysql
import pytest

from ingest import config
from ingest.migrate import apply
from ingest.models import Organization
from ingest.run import run_source
from ingest.store import Lookup

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DB_NAME"), reason="TEST_DB_NAME 이 없으면 건너뜀")


@pytest.fixture
def conn(monkeypatch):
    params = {
        "host": os.getenv("TEST_DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("TEST_DB_PORT", "3306")),
        "user": os.getenv("TEST_DB_USER", "root"),
        "password": os.getenv("TEST_DB_PASSWORD", ""),
        "database": os.environ["TEST_DB_NAME"],
    }
    monkeypatch.setattr(config, "DB", params)
    c = pymysql.connect(**params, charset="utf8mb4", autocommit=False,
                        init_command="SET time_zone = '+00:00'")
    with c.cursor() as cur:
        cur.execute("SHOW TABLES")
        tables = [t for (t,) in cur.fetchall()]
        cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        for t in tables:
            cur.execute(f"DROP TABLE `{t}`")
        cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    c.commit()
    apply(c, "all")
    yield c
    c.close()


def q(conn, sql, *args):
    with conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall()


def ev(conn, external_id, *cols):
    return q(conn, f"SELECT {', '.join(cols)} FROM events WHERE external_id = %s", external_id)[0]


def test_schema_applies_cleanly_and_is_idempotent(conn):
    tables = {t for (t,) in q(conn, "SHOW TABLES")}
    assert len(tables) == 14
    apply(conn, "all")
    assert q(conn, "SELECT COUNT(*) FROM event_categories")[0][0] == 7
    assert q(conn, "SELECT @@session.time_zone")[0][0] == "+00:00"


def test_manual_events_without_external_id(conn):
    """관리자 수동 등록(source=MANUAL)은 external_id 없이 여러 건 넣을 수 있다."""
    for title in ("Manual A", "Manual B"):
        q(conn, "INSERT INTO events (source, title, category_id, start_at, end_at) "
                "VALUES ('MANUAL', %s, 7, '2026-11-01 15:00:00', '2026-11-01 16:00:00')", title)
    conn.commit()
    assert q(conn, "SELECT COUNT(*) FROM events WHERE source = 'MANUAL' AND external_id IS NULL")[0][0] == 2
    with pytest.raises(pymysql.err.OperationalError):
        q(conn, "INSERT INTO events (source, external_id, title, category_id, start_at, end_at) "
                "VALUES ('MANUAL', 'x', 'bad', 7, '2026-11-01 16:00:00', '2026-11-01 15:00:00')")


def test_all_sources_into_mysql(web, conn):
    for slug in ("nyu_events", "wasserman", "athletics", "academic"):
        run_source(conn, slug)

    counts = dict(q(conn, "SELECT source, COUNT(*) FROM events GROUP BY source"))
    assert counts == {"NYU_EVENTS": 8, "WASSERMAN": 2, "ATHLETICS": 5, "ACADEMIC": 7}
    assert q(conn, "SELECT COUNT(*) FROM raw_events")[0][0] == 8 + 2 + 5 + 8

    row = ev(conn, "1997298", "start_at", "end_at", "is_all_day", "registration_url",
             "location_name", "address", "host_name")
    assert str(row[0]) == "2026-10-07 16:00:00" and str(row[1]) == "2026-10-07 18:00:00"
    assert row[2] == 0 and row[3] == "https://nyu.joinhandshake.com/events/1997298"
    assert row[4] == "NYU Kimmel Center, Eisner & Lubin Auditorium" and row[5].startswith("60 Washington")
    assert row[6] == "Wasserman Center for Career Development"

    # 종일 이벤트: 뉴욕 자정 기준 UTC, end_at 은 마지막 날 다음 날 자정 (10/5~10/6 → 10/5 04:00Z ~ 10/7 04:00Z)
    row = ev(conn, "403833", "start_at", "end_at", "is_all_day")
    assert (str(row[0]), str(row[1]), row[2]) == ("2026-10-05 04:00:00", "2026-10-07 04:00:00", 1)
    # 11월(EST) 종일 경기
    row = ev(conn, "14734", "start_at", "end_at")
    assert (str(row[0]), str(row[1])) == ("2026-11-13 05:00:00", "2026-11-14 05:00:00")

    # 종료 시각이 없으면 +1시간, 온라인 플래그
    row = ev(conn, "407309", "TIMESTAMPDIFF(MINUTE, start_at, end_at)", "is_online", "location_name")
    assert row == (60, 1, None)

    cats = dict(q(conn, "SELECT e.external_id, c.code FROM events e "
                        "JOIN event_categories c ON c.id = e.category_id "
                        "WHERE e.external_id IN ('1997298','14651','engage-12713554','407309','403833','401373')"))
    assert cats == {"1997298": "CAREER", "14651": "SPORTS", "engage-12713554": "SOCIAL",
                    "407309": "ARTS", "403833": "ACADEMIC", "401373": "OTHER"}
    assert {c for (c,) in q(conn, "SELECT DISTINCT c.code FROM events e JOIN event_categories c "
                                  "ON c.id = e.category_id WHERE e.source = 'ACADEMIC'")} == {"ACADEMIC"}

    # 단체: 크롤러가 (source, external_id) 로 만든다. Engage 동아리는 NULL.
    orgs = {(s, x): slug for s, x, slug in q(conn, "SELECT source, external_id, slug FROM organizations")}
    assert orgs[("WASSERMAN", "wasserman")] == "wasserman"
    assert orgs[("ATHLETICS", "athletics")] == "nyu-athletics"
    assert orgs[("NYU_EVENTS", "gid-348")] == "the-office-of-global-science-and-technology"
    assert ev(conn, "engage-12713554", "organization_id")[0] is None
    assert q(conn, "SELECT COUNT(*) FROM events WHERE source = 'WASSERMAN' AND organization_id IS NULL")[0][0] == 0

    assert ev(conn, "engage-12252581", "status", "title") == ("CANCELLED", "3rd IFA General Meeting")
    assert ev(conn, "engage-12713554", "title")[0] == "BSB Guess-the-Song & Karaoke Night"
    assert ev(conn, "403833", "is_free", "price_text") == (0, "Industry Registration Fee: $500")
    assert ev(conn, "405921", "is_free")[0] == 1
    assert ev(conn, "401373", "is_free")[0] is None

    assert q(conn, "SELECT COUNT(*) FROM events WHERE last_synced_at IS NULL")[0][0] == 0

    runs = q(conn, "SELECT source, status, fetched_count, upserted_count, skipped_count FROM ingest_runs ORDER BY id")
    assert [r[1] for r in runs] == ["success"] * 4
    assert runs[3] == ("ACADEMIC", "success", 8, 7, 1)


def test_second_run_skips_unchanged_and_detects_changes(web, conn):
    run_source(conn, "athletics")
    # 이전 실행인 것처럼 시각을 과거로 돌려둔다
    q(conn, "UPDATE events SET updated_at = '2026-01-01 00:00:00', last_synced_at = '2026-01-01 00:00:00'")
    conn.commit()

    # 1) 아무것도 안 바뀌면 원본만 확인하고 내용은 건드리지 않음. last_synced_at 만 갱신, updated_at 은 그대로
    counts = run_source(conn, "athletics")
    assert counts["changed"] == 0 and counts["upserted"] == 0 and counts["canceled"] == 0
    assert q(conn, "SELECT COUNT(*) FROM events")[0][0] == 5
    updated, synced = ev(conn, "14651", "updated_at", "last_synced_at")
    assert str(updated) == "2026-01-01 00:00:00" and str(synced) != "2026-01-01 00:00:00"

    # 2) 경기 시간이 바뀌면 같은 줄이 갱신됨 (새 줄이 생기지 않음)
    original = web.pages["gonyuathletics.com/calendar.ashx"]
    web.pages["gonyuathletics.com/calendar.ashx"] = original.replace(
        b"DTSTART:20261107T190000Z", b"DTSTART:20261107T200000Z")
    counts = run_source(conn, "athletics")
    assert counts["changed"] == 1 and counts["upserted"] == 1
    assert str(ev(conn, "14651", "start_at")[0]) == "2026-11-07 20:00:00"
    assert q(conn, "SELECT COUNT(*) FROM events")[0][0] == 5

    # 3) 피드에서 사라진 미래 경기는 지우지 않고 CANCELLED 처리
    without = re.sub(rb"BEGIN:VEVENT\r\nUID:vcal_14651.*?END:VEVENT\r\n", b"", original, flags=re.S)
    web.pages["gonyuathletics.com/calendar.ashx"] = without
    counts = run_source(conn, "athletics")
    assert counts["canceled"] == 1
    assert ev(conn, "14651", "status")[0] == "CANCELLED"
    # 이미 지난 경기(9/1)는 피드에서 빠져도 그대로 둔다
    assert ev(conn, "14700", "status")[0] == "ACTIVE"

    # 4) 다시 나타나면 ACTIVE 로 복구 (원래 시간으로)
    web.pages["gonyuathletics.com/calendar.ashx"] = original
    run_source(conn, "athletics")
    assert tuple(map(str, ev(conn, "14651", "status", "start_at"))) == ("ACTIVE", "2026-11-07 19:00:00")


def test_hidden_events_stay_hidden(web, conn):
    """관리자가 DELETE /admin/events 로 숨긴 이벤트(HIDDEN)는 크롤러가 되살리거나 취소하지 않는다."""
    run_source(conn, "athletics")
    q(conn, "UPDATE events SET status = 'HIDDEN' WHERE external_id IN ('14651', '14675')")
    conn.commit()

    run_source(conn, "athletics", force=True)
    assert ev(conn, "14651", "status")[0] == "HIDDEN"

    original = web.pages["gonyuathletics.com/calendar.ashx"]
    web.pages["gonyuathletics.com/calendar.ashx"] = re.sub(
        rb"BEGIN:VEVENT\r\nUID:vcal_14651.*?END:VEVENT\r\n", b"", original, flags=re.S)
    counts = run_source(conn, "athletics")
    assert counts["canceled"] == 0
    assert ev(conn, "14651", "status")[0] == "HIDDEN"


def test_user_saves_survive_cancellation_and_cascade_on_user_delete(web, conn):
    """event_saves 로 유저 데이터와 공용 이벤트가 만난다. 이벤트는 취소돼도 저장 기록이 남고,
    유저가 탈퇴하면 유저 소유 데이터만 CASCADE 로 지워진다."""
    run_source(conn, "athletics")
    q(conn, "INSERT INTO users (email, password_hash, display_name) VALUES ('a@nyu.edu', 'x', 'A')")
    user_id = q(conn, "SELECT id FROM users WHERE email = 'a@nyu.edu'")[0][0]
    event_id = ev(conn, "14651", "id")[0]
    q(conn, "INSERT INTO event_saves (user_id, event_id, status) VALUES (%s, %s, 'GOING')", user_id, event_id)
    conn.commit()

    original = web.pages["gonyuathletics.com/calendar.ashx"]
    web.pages["gonyuathletics.com/calendar.ashx"] = re.sub(
        rb"BEGIN:VEVENT\r\nUID:vcal_14651.*?END:VEVENT\r\n", b"", original, flags=re.S)
    run_source(conn, "athletics")
    assert ev(conn, "14651", "status")[0] == "CANCELLED"
    assert q(conn, "SELECT status FROM event_saves WHERE event_id = %s", event_id)[0][0] == "GOING"

    q(conn, "DELETE FROM users WHERE id = %s", user_id)
    conn.commit()
    assert q(conn, "SELECT COUNT(*) FROM event_saves")[0][0] == 0
    assert q(conn, "SELECT COUNT(*) FROM events")[0][0] == 5


def test_organization_slug_collision(conn):
    """이름이 같은 단체가 다른 그룹 ID 로 오면 slug 뒤에 ID 를 붙여 UNIQUE 를 지킨다."""
    lookup = Lookup()
    with conn.cursor() as cur:
        a = lookup.organization_id(cur, "NYU_EVENTS", Organization("gid-1", "Same Name", "same-name"))
        b = lookup.organization_id(cur, "NYU_EVENTS", Organization("gid-2", "Same Name", "same-name"))
        again = Lookup().organization_id(cur, "NYU_EVENTS", Organization("gid-1", "Renamed", "renamed"))
    conn.commit()
    assert a != b and again == a
    slugs = {s for (s,) in q(conn, "SELECT slug FROM organizations")}
    assert slugs == {"same-name", "same-name-gid2"}
    # 이미 있는 단체는 덮어쓰지 않는다 (관리자 수정 보호)
    assert q(conn, "SELECT name FROM organizations WHERE external_id = 'gid-1'")[0][0] == "Same Name"
