import uuid

from sqlalchemy import event

from database import engine
from tests.conftest import as_user, assert_error, at, make_event, make_org, make_user

ORGS = "/api/v1/organizations"


def tag() -> str:
    """A random word, so results never include the real organizations in the shared DB."""
    return "Zq" + uuid.uuid4().hex[:8]


def org_list(client, viewer=None, **params):
    response = client.get(ORGS, headers=as_user(viewer) if viewer else {}, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def follow(client, user, org):
    return client.put(f"{ORGS}/{org.id}/follow", headers=as_user(user))


# --- List / search -----------------------------------------------------------------

def test_list_searches_by_name_sorted(client, db):
    t = tag()
    bravo = make_org(db, name=f"{t} Bravo")
    alpha = make_org(db, name=f"Alpha {t}")
    make_org(db, name="Unrelated Club")

    body = org_list(client, q=t.lower())
    assert body["next_cursor"] is None
    assert body["items"] == [
        {"id": alpha.id, "name": f"Alpha {t}", "slug": alpha.slug, "logo_url": None, "is_following": False},
        {"id": bravo.id, "name": f"{t} Bravo", "slug": bravo.slug, "logo_url": None, "is_following": False},
    ]


def test_list_shows_what_i_follow(client, db):
    t = tag()
    me = make_user(db)
    followed, other = make_org(db, name=f"{t} A"), make_org(db, name=f"{t} B")
    follow(client, me, followed)
    items = org_list(client, me, q=t)["items"]
    assert {i["id"]: i["is_following"] for i in items} == {followed.id: True, other.id: False}


def test_list_pagination_by_name_with_ties(client, db):
    t = tag()
    same = [make_org(db, name=f"{t} Same") for _ in range(3)]
    first, last = make_org(db, name=f"{t} Aaa"), make_org(db, name=f"{t} Zzz")
    expected = [first.id] + sorted(o.id for o in same) + [last.id]

    seen, cursor, pages = [], None, 0
    while True:
        body = org_list(client, q=t, limit=2, **({"cursor": cursor} if cursor else {}))
        seen += [i["id"] for i in body["items"]]
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert seen == expected
    assert pages == 3


def test_list_matches_percent_literally(client, db):
    t = tag()
    make_org(db, name=f"{t} 100% Club")
    make_org(db, name=f"{t} 1000 Club")
    assert [i["name"] for i in org_list(client, q=f"{t} 100%")["items"]] == [f"{t} 100% Club"]


def test_list_query_count_does_not_grow_with_results(client, db):
    t = tag()
    me = make_user(db)
    orgs = [make_org(db, name=f"{t} {i}") for i in range(8)]
    for org in orgs[:4]:
        follow(client, me, org)

    statements = []
    def record(conn, cursor, statement, *args):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)
    event.listen(engine, "before_cursor_execute", record)
    try:
        assert len(org_list(client, me, q=t)["items"]) == 8
    finally:
        event.remove(engine, "before_cursor_execute", record)
    # Loading the current user + organizations + my follows, however many organizations come back.
    assert len(statements) <= 3, statements


def test_list_errors(client, db):
    assert_error(client.get(ORGS, params={"cursor": "not-a-cursor"}), 400, "INVALID_CURSOR")
    assert_error(client.get(ORGS, params={"limit": 101}), 422, "VALIDATION_ERROR")
    assert_error(client.get(ORGS, params={"q": "x" * 101}), 422, "VALIDATION_ERROR")


# --- Detail -----------------------------------------------------------------------

def test_detail(client, db):
    me, fan1, fan2 = make_user(db), make_user(db), make_user(db)
    org = make_org(db, name="Chess Club")
    org.website_url, org.instagram_handle = "https://example.com/chess", "nyuchess"
    db.flush()
    follow(client, fan1, org)
    follow(client, fan2, org)

    anonymous = client.get(f"{ORGS}/{org.id}").json()
    assert anonymous == {
        "id": org.id, "name": "Chess Club", "slug": org.slug, "logo_url": None, "description": None,
        "website_url": "https://example.com/chess", "instagram_handle": "nyuchess",
        "follower_count": 2, "is_following": False,
    }
    assert client.get(f"{ORGS}/{org.id}", headers=as_user(me)).json()["is_following"] is False
    assert client.get(f"{ORGS}/{org.id}", headers=as_user(fan1)).json()["is_following"] is True


def test_detail_not_found(client, db):
    assert_error(client.get(f"{ORGS}/999999999"), 404, "ORGANIZATION_NOT_FOUND")


# --- Follow / unfollow ------------------------------------------------------------

def test_follow_and_unfollow(client, db):
    me, org = make_user(db), make_org(db)

    response = follow(client, me, org)
    assert response.status_code == 200, response.text
    assert response.json() == {"organization_id": org.id, "is_following": True}
    assert follow(client, me, org).status_code == 200  # again: no change, no error
    assert client.get(f"{ORGS}/{org.id}").json()["follower_count"] == 1

    assert client.delete(f"{ORGS}/{org.id}/follow", headers=as_user(me)).status_code == 204
    assert client.get(f"{ORGS}/{org.id}").json()["follower_count"] == 0
    assert client.delete(f"{ORGS}/{org.id}/follow", headers=as_user(me)).status_code == 204  # not following


def test_follow_errors(client, db):
    me, org = make_user(db), make_org(db)
    assert_error(client.put(f"{ORGS}/999999999/follow", headers=as_user(me)), 404, "ORGANIZATION_NOT_FOUND")
    assert_error(client.put(f"{ORGS}/{org.id}/follow"), 401, "AUTH_REQUIRED")
    assert_error(client.delete(f"{ORGS}/{org.id}/follow"), 401, "AUTH_REQUIRED")


# --- What following feeds -----------------------------------------------------------

def test_events_followed_only(client, db):
    me = make_user(db)
    followed, other = make_org(db), make_org(db)
    mine = make_event(db, at(10, 10), at(10, 11), organization_id=followed.id)
    make_event(db, at(10, 12), at(10, 13), organization_id=other.id)
    make_event(db, at(10, 14), at(10, 15))  # no organization
    follow(client, me, followed)

    response = client.get("/api/v1/events", headers=as_user(me), params={
        "start": "2099-01-10T00:00:00Z", "end": "2099-01-11T00:00:00Z", "followed_only": "true",
    })
    assert response.status_code == 200, response.text
    assert [i["id"] for i in response.json()["items"]] == [mine.id]


def test_my_following(client, db):
    t = tag()
    me = make_user(db)
    assert client.get("/api/v1/users/me/following", headers=as_user(me)).json() == []
    b, a = make_org(db, name=f"{t} B"), make_org(db, name=f"{t} A")
    make_org(db, name=f"{t} Not followed")
    follow(client, me, b)
    follow(client, me, a)

    response = client.get("/api/v1/users/me/following", headers=as_user(me))
    assert response.status_code == 200, response.text
    assert [o["id"] for o in response.json()] == [a.id, b.id]
    assert_error(client.get("/api/v1/users/me/following"), 401, "AUTH_REQUIRED")
