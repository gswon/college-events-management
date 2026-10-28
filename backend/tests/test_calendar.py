import models
from tests.conftest import as_user, make_entry, make_event, make_user
from tests.test_events import assert_error, at

RANGE = {"start": "2099-01-10T00:00:00Z", "end": "2099-01-11T00:00:00Z"}


def save(db, user, event, status="GOING") -> None:
    db.add(models.EventSave(user_id=user.id, event_id=event.id, status=status))
    db.flush()


def befriend(db, owner, viewer, **owner_levels) -> None:
    """owner → viewer 행은 owner_levels로, 반대 행은 기본값으로."""
    defaults = dict(share_class="DETAILS", share_personal="BUSY", share_event="DETAILS")
    db.add(models.Friendship(user_id=owner.id, friend_id=viewer.id, **{**defaults, **owner_levels}))
    db.add(models.Friendship(user_id=viewer.id, friend_id=owner.id, **defaults))
    db.flush()


def calendar(client, viewer, path="/api/v1/calendar", **params):
    return client.get(path, headers=as_user(viewer), params={**RANGE, **params})


def busy(start_hour: int, end_hour: int) -> dict:
    return {"type": "BUSY", "start_at": f"2099-01-10T{start_hour:02}:00:00Z", "end_at": f"2099-01-10T{end_hour:02}:00:00Z"}


# --- 내 캘린더 --------------------------------------------------------------

def test_my_calendar_merges_and_sorts(client, db):
    me = make_user(db)
    lecture = make_entry(db, me, at(10, 14), at(10, 15), kind="CLASS", title="CSCI-UA 202",
                         location="WWH 101", visibility_override="HIDDEN")
    dentist = make_entry(db, me, at(10, 9), at(10, 10), title="Dentist")
    fair = make_event(db, at(10, 18), at(10, 21), title="Career Fair", category="CAREER", location_name="Kimmel")
    cancelled = make_event(db, at(10, 12), at(10, 13), status="CANCELLED")
    hidden = make_event(db, at(10, 12), at(10, 13), status="HIDDEN")
    for event in (fair, cancelled, hidden):
        save(db, me, event)
    make_entry(db, me, at(11, 9), at(11, 10))               # 기간 밖
    make_entry(db, make_user(db), at(10, 9), at(10, 10))    # 남의 일정

    response = calendar(client, me)
    assert response.status_code == 200, response.text
    items = response.json()
    assert [(i["type"], i["id"]) for i in items] == [
        ("PERSONAL", dentist.id), ("EVENT", cancelled.id), ("CLASS", lecture.id), ("EVENT", fair.id)
    ]
    assert items[1]["is_cancelled"] is True
    # 본인에게는 visibility_override가 적용되지 않는다.
    assert items[2] == {
        "type": "CLASS", "id": lecture.id, "title": "CSCI-UA 202", "start_at": "2099-01-10T14:00:00Z",
        "end_at": "2099-01-10T15:00:00Z", "is_all_day": False, "location": "WWH 101",
    }
    assert items[3] == {
        "type": "EVENT", "id": fair.id, "title": "Career Fair", "start_at": "2099-01-10T18:00:00Z",
        "end_at": "2099-01-10T21:00:00Z", "is_all_day": False, "location": "Kimmel",
        "category": "CAREER", "save_status": "GOING", "is_cancelled": False,
    }


def test_my_calendar_include(client, db):
    me = make_user(db)
    make_entry(db, me, at(10, 9), at(10, 10), kind="CLASS")
    make_entry(db, me, at(10, 11), at(10, 12))
    save(db, me, make_event(db, at(10, 13), at(10, 14)))

    assert [i["type"] for i in calendar(client, me, include="class").json()] == ["CLASS"]
    assert [i["type"] for i in calendar(client, me, include="personal,event").json()] == ["PERSONAL", "EVENT"]
    assert_error(calendar(client, me, include="class,nope"), 400, "INVALID_INCLUDE")
    assert_error(calendar(client, me, include=""), 400, "INVALID_INCLUDE")


# --- 친구 캘린더: 공유 규칙 --------------------------------------------------

def test_friend_calendar_default_levels(client, db):
    owner, viewer = make_user(db), make_user(db)
    befriend(db, owner, viewer)  # class DETAILS, personal BUSY, event DETAILS
    lecture = make_entry(db, owner, at(10, 9), at(10, 10), kind="CLASS", title="CSCI-UA 202")
    make_entry(db, owner, at(10, 11), at(10, 12), kind="CLASS", visibility_override="BUSY")
    make_entry(db, owner, at(10, 13), at(10, 14), kind="CLASS", visibility_override="HIDDEN")
    make_entry(db, owner, at(10, 15), at(10, 16), title="Therapy")
    event = make_event(db, at(10, 18), at(10, 19))
    save(db, owner, event, "INTERESTED")

    response = calendar(client, viewer, f"/api/v1/users/{owner.id}/calendar")
    assert response.status_code == 200, response.text
    items = response.json()
    assert [i["type"] for i in items] == ["CLASS", "BUSY", "BUSY", "EVENT"]
    assert (items[0]["id"], items[0]["title"]) == (lecture.id, "CSCI-UA 202")
    assert items[1] == busy(11, 12)  # override로 수업 하나만 BUSY
    assert items[2] == busy(15, 16)  # 개인 일정 기본값 BUSY: 제목·ID 없음
    assert (items[3]["id"], items[3]["save_status"]) == (event.id, "INTERESTED")


def test_friend_calendar_lowered_levels(client, db):
    owner, viewer = make_user(db), make_user(db)
    befriend(db, owner, viewer, share_class="HIDDEN", share_personal="HIDDEN", share_event="BUSY")
    make_entry(db, owner, at(10, 9), at(10, 10), kind="CLASS")
    make_entry(db, owner, at(10, 11), at(10, 12), visibility_override="BUSY")  # override로 더 공개할 수는 없다
    save(db, owner, make_event(db, at(10, 18), at(10, 19)))
    save(db, owner, make_event(db, at(10, 20), at(10, 21), status="CANCELLED"))  # 취소된 건 바쁜 시간 아님

    # 반대 방향(viewer → owner)은 DETAILS지만 owner → viewer 행만 본다.
    assert calendar(client, viewer, f"/api/v1/users/{owner.id}/calendar").json() == [busy(18, 19)]


def test_friend_calendar_requires_friendship(client, db):
    owner, stranger = make_user(db), make_user(db)
    make_entry(db, owner, at(10, 9), at(10, 10), visibility_override="HIDDEN")

    assert_error(calendar(client, stranger, f"/api/v1/users/{owner.id}/calendar"), 403, "NOT_FRIENDS")
    assert_error(calendar(client, stranger, "/api/v1/users/999999999/calendar"), 403, "NOT_FRIENDS")
    assert len(calendar(client, owner, f"/api/v1/users/{owner.id}/calendar").json()) == 1  # 본인은 전부


# --- 겹쳐 보기 ---------------------------------------------------------------

def test_overlay(client, db):
    me, f1, f2, stranger = (make_user(db) for _ in range(4))
    befriend(db, f1, me)
    befriend(db, f2, me)
    mine = make_entry(db, me, at(10, 9), at(10, 10))
    make_entry(db, f1, at(10, 9), at(10, 10))

    response = calendar(client, me, "/api/v1/calendar/overlay", user_ids=f"{f2.id}, {f1.id},{me.id},{f1.id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert [c["user_id"] for c in body] == [me.id, f2.id, f1.id]  # 나를 맨 앞에, 중복 제거
    assert [i["id"] for i in body[0]["items"]] == [mine.id]
    assert body[1]["items"] == []
    assert body[2]["items"] == [busy(9, 10)]

    overlay = "/api/v1/calendar/overlay"
    assert_error(calendar(client, me, overlay, user_ids=f"{f1.id},{stranger.id}"), 403, "NOT_FRIENDS")
    assert_error(calendar(client, me, overlay, user_ids="1,abc"), 400, "INVALID_USER_IDS")
    too_many = ",".join(str(10**12 + i) for i in range(11))
    assert_error(calendar(client, me, overlay, user_ids=too_many), 400, "INVALID_USER_IDS")


def test_calendar_errors(client, db):
    me = make_user(db)
    assert_error(client.get("/api/v1/calendar", params=RANGE), 401, "AUTH_REQUIRED")
    assert_error(calendar(client, me, start="2099-01-11T00:00:00Z"), 400, "INVALID_RANGE")
    assert_error(calendar(client, me, end="2099-04-13T00:00:00Z"), 400, "INVALID_RANGE")
    assert_error(calendar(client, me, start="2099-01-10T00:00:00"), 422, "VALIDATION_ERROR")
