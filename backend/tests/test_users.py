import uuid

from sqlalchemy import event

import models
from database import engine
from tests.conftest import as_user, assert_error, make_user

ME = "/api/v1/users/me"
SEARCH = "/api/v1/users/search"


def test_get_me(client, db):
    me = make_user(db, name="Keonsang Joh", profile_image_url="https://example.com/me.png")
    response = client.get(ME, headers=as_user(me))
    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": me.id, "email": me.email, "display_name": "Keonsang Joh", "profile_image_url": "https://example.com/me.png",
    }


def test_get_me_needs_login(client, db):
    assert_error(client.get(ME), 401, "AUTH_REQUIRED")
    assert_error(client.patch(ME, json={"display_name": "X"}), 401, "AUTH_REQUIRED")


def test_update_name_and_photo(client, db):
    me = make_user(db, name="Old Name")
    response = client.patch(ME, headers=as_user(me), json={
        "display_name": "  New Name ", "profile_image_url": "https://example.com/new.png",
    })
    assert response.status_code == 200, response.text
    assert response.json()["display_name"] == "New Name"
    assert response.json()["profile_image_url"] == "https://example.com/new.png"
    db.refresh(me)
    assert (me.display_name, me.profile_image_url) == ("New Name", "https://example.com/new.png")


def test_update_changes_only_fields_sent(client, db):
    me = make_user(db, name="Keep Me", profile_image_url="https://example.com/keep.png")
    headers = as_user(me)
    assert client.patch(ME, headers=headers, json={"display_name": "Renamed"}).json()["profile_image_url"] == \
        "https://example.com/keep.png"
    unchanged = client.patch(ME, headers=headers, json={})
    assert unchanged.status_code == 200
    assert unchanged.json()["display_name"] == "Renamed"


def test_remove_photo_with_null(client, db):
    me = make_user(db, profile_image_url="https://example.com/old.png")
    response = client.patch(ME, headers=as_user(me), json={"profile_image_url": None})
    assert response.status_code == 200, response.text
    assert response.json()["profile_image_url"] is None


def test_email_cannot_be_changed(client, db):
    me = make_user(db)
    response = client.patch(ME, headers=as_user(me), json={"email": "someone-else@nyu.edu"})
    assert response.status_code == 200, response.text
    assert response.json()["email"] == me.email


def test_invalid_updates(client, db):
    me = make_user(db, name="Unchanged")
    headers = as_user(me)
    for body in (
        {"display_name": None},                              # a name cannot be removed
        {"display_name": "   "},                             # blank after trimming
        {"display_name": "x" * 51},                          # longer than the column
        {"profile_image_url": "not a url"},
        {"profile_image_url": "ftp://example.com/a.png"},    # only http(s)
        {"profile_image_url": "https://example.com/" + "a" * 481},  # 501 characters
    ):
        assert_error(client.patch(ME, headers=headers, json=body), 422, "VALIDATION_ERROR")
    db.refresh(me)
    assert me.display_name == "Unchanged"


# --- Search -------------------------------------------------------------------

def tag() -> str:
    """A random word, so search results never include real users in the shared DB."""
    return "Zq" + uuid.uuid4().hex[:8]


def search(client, viewer, q):
    return client.get(SEARCH, headers=as_user(viewer), params={"q": q})


def names(response) -> list[str]:
    assert response.status_code == 200, response.text
    return [u["display_name"] for u in response.json()]


def test_search_by_exact_email(client, db):
    me, other = make_user(db), make_user(db, name="Email Match")
    response = search(client, me, f"  {other.email.upper()} ")
    assert response.json() == [
        {"id": other.id, "display_name": "Email Match", "profile_image_url": None, "friend_status": "NONE"}
    ]
    assert "email" not in response.json()[0]
    # Only an exact address matches: part of it, or just the domain, finds nobody.
    assert names(search(client, me, other.email[:-1])) == []
    assert names(search(client, me, "@nyu.edu")) == []


def test_search_by_part_of_name(client, db):
    t = tag()
    me = make_user(db, name=f"{t} Me")
    make_user(db, name=f"{t} Bravo")
    make_user(db, name=f"Alpha {t}")
    make_user(db, name="Someone Else")
    assert names(search(client, me, t.lower())) == [f"Alpha {t}", f"{t} Bravo"]  # by name, without me


def test_search_matches_percent_and_underscore_literally(client, db):
    t = tag()
    me = make_user(db)
    make_user(db, name=f"{t}%_x")
    make_user(db, name=f"{t}ab")
    assert names(search(client, me, f"{t}%_")) == [f"{t}%_x"]


def test_search_returns_at_most_20(client, db):
    t = tag()
    me = make_user(db)
    for i in range(21):
        make_user(db, name=f"{t} {i:02}")
    assert len(names(search(client, me, t))) == 20


def test_search_friend_status(client, db):
    t = tag()
    me = make_user(db)
    stranger, friend, asked, asking = (make_user(db, name=f"{t} {n}") for n in ("A", "B", "C", "D"))
    db.add_all([
        models.Friendship(user_id=me.id, friend_id=friend.id, share_class="DETAILS", share_personal="BUSY", share_event="DETAILS"),
        models.Friendship(user_id=friend.id, friend_id=me.id, share_class="DETAILS", share_personal="BUSY", share_event="DETAILS"),
        models.FriendRequest(from_user_id=me.id, to_user_id=asked.id, status="PENDING"),
        models.FriendRequest(from_user_id=asking.id, to_user_id=me.id, status="PENDING"),
        models.FriendRequest(from_user_id=me.id, to_user_id=stranger.id, status="DECLINED"),  # not pending
    ])
    db.flush()
    statuses = {u["id"]: u["friend_status"] for u in search(client, me, t).json()}
    assert statuses == {stranger.id: "NONE", friend.id: "FRIENDS", asked.id: "REQUESTED", asking.id: "RECEIVED"}


def test_search_query_count_does_not_grow_with_results(client, db):
    t = tag()
    me = make_user(db)
    for i in range(10):
        make_user(db, name=f"{t} {i}")

    statements = []
    def record(conn, cursor, statement, *args):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)
    event.listen(engine, "before_cursor_execute", record)
    try:
        assert len(names(search(client, me, t))) == 10
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert len(statements) <= 3, statements  # users + pending requests + friendships


def test_search_errors(client, db):
    me = make_user(db)
    assert_error(client.get(SEARCH, params={"q": "keon"}), 401, "AUTH_REQUIRED")
    assert_error(client.get(SEARCH, headers=as_user(me)), 422, "VALIDATION_ERROR")       # no q
    assert_error(search(client, me, ""), 422, "VALIDATION_ERROR")
    assert_error(search(client, me, "x" * 101), 422, "VALIDATION_ERROR")
    assert_error(search(client, me, "k"), 400, "QUERY_TOO_SHORT")
    assert_error(search(client, me, "  k  "), 400, "QUERY_TOO_SHORT")                    # 1 char after trimming
