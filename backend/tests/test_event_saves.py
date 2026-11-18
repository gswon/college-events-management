from datetime import datetime

from sqlalchemy import select

import models
from tests.conftest import as_user, assert_error, at, make_event, make_user


def save_url(event) -> str:
    event_id = event if isinstance(event, int) else event.id
    return f"/api/v1/events/{event_id}/save"


def put_save(client, user, event, status="GOING"):
    return client.put(save_url(event), headers=as_user(user), json={"status": status})


def saved_status(db, user, event):
    db.expire_all()
    return db.scalar(select(models.EventSave.status).where(
        models.EventSave.user_id == user.id, models.EventSave.event_id == event.id
    ))


def test_save_then_change_status(client, db):
    me, event = make_user(db), make_event(db, at(10, 18), at(10, 20))

    response = put_save(client, me, event, "INTERESTED")
    assert response.status_code == 200, response.text
    assert response.json() == {"event_id": event.id, "status": "INTERESTED"}
    assert saved_status(db, me, event) == "INTERESTED"

    assert put_save(client, me, event, "GOING").json() == {"event_id": event.id, "status": "GOING"}
    assert put_save(client, me, event, "GOING").status_code == 200  # same request again
    assert saved_status(db, me, event) == "GOING"
    assert db.scalar(select(models.EventSave.event_id).where(models.EventSave.user_id == me.id)) == event.id


def test_saved_event_appears_on_my_calendar(client, db):
    me, event = make_user(db), make_event(db, at(10, 18), at(10, 20), title="Career Fair")
    put_save(client, me, event, "INTERESTED")
    items = client.get("/api/v1/calendar", headers=as_user(me),
                       params={"start": "2099-01-10T00:00:00Z", "end": "2099-01-11T00:00:00Z"}).json()
    assert [(i["type"], i["id"], i["save_status"]) for i in items] == [("EVENT", event.id, "INTERESTED")]


def test_unsave(client, db):
    me, event = make_user(db), make_event(db, at(10, 18), at(10, 20))
    put_save(client, me, event)

    assert client.delete(save_url(event), headers=as_user(me)).status_code == 204
    assert saved_status(db, me, event) is None
    # Removing again, or an event that does not exist, is still a success.
    assert client.delete(save_url(event), headers=as_user(me)).status_code == 204
    assert client.delete(save_url(999999999), headers=as_user(me)).status_code == 204


def test_unsave_only_touches_my_save(client, db):
    me, other, event = make_user(db), make_user(db), make_event(db, at(10, 18), at(10, 20))
    put_save(client, me, event)
    put_save(client, other, event)
    client.delete(save_url(event), headers=as_user(me))
    assert saved_status(db, other, event) == "GOING"


def test_cannot_save_hidden_or_missing_event(client, db):
    me = make_user(db)
    hidden = make_event(db, at(10, 18), at(10, 20), status="HIDDEN")
    assert_error(put_save(client, me, hidden), 404, "EVENT_NOT_FOUND")
    assert_error(put_save(client, me, 999999999), 404, "EVENT_NOT_FOUND")


def test_cancelled_event_cannot_be_newly_saved(client, db):
    me, event = make_user(db), make_event(db, at(10, 18), at(10, 20), status="CANCELLED")
    assert_error(put_save(client, me, event), 409, "EVENT_CANCELLED")
    assert saved_status(db, me, event) is None


def test_existing_save_of_cancelled_event_can_change_or_be_removed(client, db):
    me, event = make_user(db), make_event(db, at(10, 18), at(10, 20))
    put_save(client, me, event, "GOING")
    event.status = "CANCELLED"
    db.flush()

    assert put_save(client, me, event, "INTERESTED").status_code == 200
    assert saved_status(db, me, event) == "INTERESTED"
    assert client.delete(save_url(event), headers=as_user(me)).status_code == 204


def test_past_event_can_be_saved(client, db):
    me, event = make_user(db), make_event(db, datetime(2000, 1, 1, 18), datetime(2000, 1, 1, 20))
    assert put_save(client, me, event).status_code == 200


def test_save_errors(client, db):
    me, event = make_user(db), make_event(db, at(10, 18), at(10, 20))
    assert_error(client.put(save_url(event), json={"status": "GOING"}), 401, "AUTH_REQUIRED")
    assert_error(client.delete(save_url(event)), 401, "AUTH_REQUIRED")
    assert_error(put_save(client, me, event, "MAYBE"), 422, "VALIDATION_ERROR")
    assert_error(client.put(save_url(event), headers=as_user(me), json={}), 422, "VALIDATION_ERROR")


# --- Event detail: my save status and friends going ----------------------------

def befriend(db, friend, me, share_event="DETAILS") -> None:
    """friend shares events with me at share_event; I share defaults back."""
    db.add_all([
        models.Friendship(user_id=friend.id, friend_id=me.id, share_class="DETAILS", share_personal="BUSY",
                          share_event=share_event),
        models.Friendship(user_id=me.id, friend_id=friend.id, share_class="DETAILS", share_personal="BUSY",
                          share_event="DETAILS"),
    ])
    db.flush()


def detail(client, event, viewer=None):
    headers = as_user(viewer) if viewer else {}
    response = client.get(f"/api/v1/events/{event.id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_detail_anonymous_has_empty_viewer_fields(client, db):
    event = make_event(db, at(10, 18), at(10, 20))
    body = detail(client, event)
    assert (body["my_save_status"], body["friends_going_count"], body["friends_going"]) == (None, 0, [])


def test_detail_shows_my_save_status(client, db):
    me, event = make_user(db), make_event(db, at(10, 18), at(10, 20))
    assert detail(client, event, me)["my_save_status"] is None
    put_save(client, me, event, "INTERESTED")
    assert detail(client, event, me)["my_save_status"] == "INTERESTED"


def test_detail_counts_only_going_friends_who_share_details(client, db):
    me, event = make_user(db), make_event(db, at(10, 18), at(10, 20))
    going = make_user(db, name="A Going")
    interested = make_user(db, name="B Interested")
    busy_sharer = make_user(db, name="C Busy")
    hidden_sharer = make_user(db, name="D Hidden")
    stranger = make_user(db, name="E Stranger")
    befriend(db, going, me)
    befriend(db, interested, me)
    befriend(db, busy_sharer, me, share_event="BUSY")
    befriend(db, hidden_sharer, me, share_event="HIDDEN")
    put_save(client, going, event, "GOING")
    put_save(client, interested, event, "INTERESTED")
    put_save(client, busy_sharer, event, "GOING")
    put_save(client, hidden_sharer, event, "GOING")
    put_save(client, stranger, event, "GOING")
    put_save(client, me, event, "GOING")  # I am not my own friend

    body = detail(client, event, me)
    assert body["friends_going_count"] == 1
    assert body["friends_going"] == [{"id": going.id, "display_name": "A Going", "profile_image_url": None}]


def test_detail_previews_three_friends_by_name_but_counts_all(client, db):
    me, event = make_user(db), make_event(db, at(10, 18), at(10, 20))
    friends = [make_user(db, name=name) for name in ("Dana", "Alex", "Casey", "Blake")]
    for friend in friends:
        befriend(db, friend, me)
        put_save(client, friend, event, "GOING")

    body = detail(client, event, me)
    assert body["friends_going_count"] == 4
    assert [f["display_name"] for f in body["friends_going"]] == ["Alex", "Blake", "Casey"]


def test_detail_with_bad_token_is_401_not_anonymous(auth_client, db):
    event = make_event(db, at(10, 18), at(10, 20))
    response = auth_client.get(f"/api/v1/events/{event.id}", headers={"Authorization": "Bearer not-a-jwt"})
    assert_error(response, 401, "INVALID_TOKEN")
    assert auth_client.get(f"/api/v1/events/{event.id}").status_code == 200  # no token: anonymous view
