import models
from tests.conftest import as_user, make_entry, make_user
from tests.test_events import assert_error, at


def entry_body(**fields) -> dict:
    body = {"title": "Study group", "start_at": "2099-01-10T14:00:00Z", "end_at": "2099-01-10T15:00:00Z"}
    body.update(fields)
    return body


# --- 생성 -----------------------------------------------------------------

def test_create_entry(client, db):
    me = make_user(db)
    response = client.post("/api/v1/entries", headers=as_user(me), json=entry_body(
        title="  Study group ", location="Bobst", color="#FF8800", visibility_override="HIDDEN",
        start_at="2099-01-10T09:00:00-05:00", end_at="2099-01-10T10:30:00-05:00",
    ))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body == {
        "id": body["id"],
        "kind": "PERSONAL",
        "title": "Study group",
        "description": None,
        "location": "Bobst",
        "start_at": "2099-01-10T14:00:00Z",
        "end_at": "2099-01-10T15:30:00Z",
        "is_all_day": False,
        "color": "#FF8800",
        "course_code": None,
        "visibility_override": "HIDDEN",
    }
    entry = db.get(models.CalendarEntry, body["id"])
    assert entry.user_id == me.id
    assert entry.start_at == at(10, 14)


def test_created_kind_is_always_personal(client, db):
    body = client.post("/api/v1/entries", headers=as_user(make_user(db)), json=entry_body(kind="CLASS")).json()
    assert body["kind"] == "PERSONAL"


def test_auth_required(client, db):
    assert_error(client.post("/api/v1/entries", json=entry_body()), 401, "AUTH_REQUIRED")
    unknown = {"X-User-Id": "999999999"}
    assert_error(client.post("/api/v1/entries", headers=unknown, json=entry_body()), 401, "AUTH_REQUIRED")


def test_create_validation(client, db):
    headers = as_user(make_user(db))

    def post(**fields):
        return client.post("/api/v1/entries", headers=headers, json=entry_body(**fields))

    assert_error(post(end_at="2099-01-10T13:59:00Z"), 400, "INVALID_RANGE")
    assert post(end_at="2099-01-10T14:00:00Z").status_code == 201  # DB CHECK와 같게 end_at == start_at 허용
    assert_error(post(start_at="2099-01-10T14:00:00"), 422, "VALIDATION_ERROR")  # 오프셋 없음
    assert_error(post(title="   "), 422, "VALIDATION_ERROR")
    assert_error(post(color="red"), 422, "VALIDATION_ERROR")
    assert_error(post(visibility_override="DETAILS"), 422, "VALIDATION_ERROR")  # 친구 설정보다 더 공개 불가


# --- 조회 / 수정 / 삭제 ----------------------------------------------------

def test_get_entry_owner_only(client, db):
    me, other = make_user(db), make_user(db)
    entry = make_entry(db, me, at(10, 14), at(10, 15))
    url = f"/api/v1/entries/{entry.id}"

    assert client.get(url, headers=as_user(me)).json()["id"] == entry.id
    assert_error(client.get(url, headers=as_user(other)), 404, "ENTRY_NOT_FOUND")
    assert_error(client.get("/api/v1/entries/999999999", headers=as_user(me)), 404, "ENTRY_NOT_FOUND")


def test_update_personal_entry(client, db):
    me = make_user(db)
    entry = make_entry(db, me, at(10, 14), at(10, 15), visibility_override="BUSY")
    url, headers = f"/api/v1/entries/{entry.id}", as_user(me)

    response = client.patch(url, headers=headers, json={
        "title": "Moved", "start_at": "2099-01-10T11:00:00-05:00", "end_at": "2099-01-10T12:00:00-05:00",
        "visibility_override": None,
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["title"], body["start_at"], body["end_at"], body["visibility_override"]) == (
        "Moved", "2099-01-10T16:00:00Z", "2099-01-10T17:00:00Z", None
    )

    assert client.patch(url, headers=headers, json={"location": "Bobst"}).json()["title"] == "Moved"  # 보낸 필드만
    assert_error(client.patch(url, headers=headers, json={"end_at": "2099-01-10T15:00:00Z"}), 400, "INVALID_RANGE")
    assert_error(client.patch(url, headers=headers, json={"title": None}), 422, "VALIDATION_ERROR")
    assert_error(client.patch(url, headers=as_user(make_user(db)), json={"title": "x"}), 404, "ENTRY_NOT_FOUND")


def test_update_class_entry(client, db):
    me = make_user(db)
    entry = make_entry(db, me, at(10, 14), at(10, 15), kind="CLASS", title="CSCI-UA 202", course_code="CSCI-UA 202")
    url, headers = f"/api/v1/entries/{entry.id}", as_user(me)

    response = client.patch(url, headers=headers, json={"description": "midterm", "visibility_override": "BUSY"})
    assert response.status_code == 200, response.text
    assert (response.json()["description"], response.json()["visibility_override"]) == ("midterm", "BUSY")

    response = client.patch(url, headers=headers, json={"description": "x", "title": "y", "start_at": "2099-01-10T14:00:00Z"})
    assert_error(response, 400, "FIELD_NOT_EDITABLE")
    assert "start_at, title" in response.json()["error"]["message"]
    assert client.get(url, headers=headers).json()["description"] == "midterm"


def test_delete_entry(client, db):
    me, other = make_user(db), make_user(db)
    personal_id = make_entry(db, me, at(10, 14), at(10, 15)).id
    class_id = make_entry(db, me, at(10, 16), at(10, 17), kind="CLASS").id  # 휴강 등으로 회차 하나 삭제

    assert_error(client.delete(f"/api/v1/entries/{personal_id}", headers=as_user(other)), 404, "ENTRY_NOT_FOUND")
    for entry_id in (personal_id, class_id):
        response = client.delete(f"/api/v1/entries/{entry_id}", headers=as_user(me))
        assert response.status_code == 204
        assert response.content == b""
        assert_error(client.get(f"/api/v1/entries/{entry_id}", headers=as_user(me)), 404, "ENTRY_NOT_FOUND")
