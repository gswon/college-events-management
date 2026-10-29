import models
from tests.conftest import as_user, make_user
from tests.test_events import assert_error

REQUESTS = "/api/v1/friends/requests"


def send(client, sender, to):
    return client.post(REQUESTS, headers=as_user(sender), json={"to_user_id": to.id})


def accept(client, request_id, user):
    return client.post(f"{REQUESTS}/{request_id}/accept", headers=as_user(user))


def befriend(client, a, b) -> None:
    accept(client, send(client, a, b).json()["id"], b)


def friend_ids(client, user) -> list[int]:
    return [f["user"]["id"] for f in client.get("/api/v1/friends", headers=as_user(user)).json()]


# --- 요청 → 수락 ------------------------------------------------------------

def test_request_accept_flow(client, db):
    alice = make_user(db, "Alice", default_share_personal="HIDDEN")
    bob = make_user(db, "Bob")

    response = send(client, alice, bob)
    assert response.status_code == 201, response.text
    req = response.json()
    assert req["status"] == "PENDING"
    assert req["from_user"] == {"id": alice.id, "display_name": "Alice", "profile_image_url": None}
    assert req["to_user"]["id"] == bob.id

    assert [r["id"] for r in client.get(REQUESTS, headers=as_user(bob)).json()] == [req["id"]]
    outgoing = client.get(REQUESTS, headers=as_user(alice), params={"direction": "outgoing"}).json()
    assert [r["id"] for r in outgoing] == [req["id"]]
    assert client.get(REQUESTS, headers=as_user(alice)).json() == []

    response = accept(client, req["id"], bob)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ACCEPTED"
    assert client.get(REQUESTS, headers=as_user(bob)).json() == []

    # 친구 행 2개, 각자 자기 기본 공유 수준이 복사된다.
    assert client.get("/api/v1/friends", headers=as_user(alice)).json() == [{
        "user": {"id": bob.id, "display_name": "Bob", "profile_image_url": None},
        "sharing": {"class": "DETAILS", "personal": "HIDDEN", "event": "DETAILS"},
    }]
    bob_friends = client.get("/api/v1/friends", headers=as_user(bob)).json()
    assert bob_friends[0]["user"]["id"] == alice.id
    assert bob_friends[0]["sharing"] == {"class": "DETAILS", "personal": "BUSY", "event": "DETAILS"}


def test_mutual_request_auto_accepts(client, db):
    alice, bob = make_user(db), make_user(db)
    request_id = send(client, alice, bob).json()["id"]

    response = send(client, bob, alice)
    assert response.status_code == 201, response.text
    assert (response.json()["id"], response.json()["status"]) == (request_id, "ACCEPTED")
    assert friend_ids(client, alice) == [bob.id]
    assert friend_ids(client, bob) == [alice.id]


def test_request_errors(client, db):
    alice, bob = make_user(db), make_user(db)
    assert_error(send(client, alice, alice), 400, "INVALID_FRIEND_REQUEST")
    assert_error(client.post(REQUESTS, headers=as_user(alice), json={"to_user_id": 999999999}), 404, "USER_NOT_FOUND")

    request_id = send(client, alice, bob).json()["id"]
    assert_error(send(client, alice, bob), 409, "REQUEST_ALREADY_SENT")
    # 받은 사람만 수락·거절, 보낸 사람만 취소
    assert_error(accept(client, request_id, alice), 404, "REQUEST_NOT_FOUND")
    assert_error(client.delete(f"{REQUESTS}/{request_id}", headers=as_user(bob)), 404, "REQUEST_NOT_FOUND")

    assert accept(client, request_id, bob).status_code == 200
    assert_error(accept(client, request_id, bob), 409, "REQUEST_NOT_PENDING")
    assert_error(send(client, bob, alice), 409, "ALREADY_FRIENDS")
    assert_error(client.get(REQUESTS, headers=as_user(alice), params={"direction": "sideways"}), 422, "VALIDATION_ERROR")


def test_decline_cancel_and_resend(client, db):
    alice, bob = make_user(db), make_user(db)
    request_id = send(client, alice, bob).json()["id"]

    declined = client.post(f"{REQUESTS}/{request_id}/decline", headers=as_user(bob))
    assert declined.status_code == 200
    assert declined.json()["status"] == "DECLINED"

    resent = send(client, alice, bob).json()  # (from, to) 행을 재사용해 PENDING으로
    assert (resent["id"], resent["status"]) == (request_id, "PENDING")

    assert client.delete(f"{REQUESTS}/{request_id}", headers=as_user(alice)).status_code == 204
    assert db.get(models.FriendRequest, request_id).status == "CANCELLED"
    assert_error(accept(client, request_id, bob), 409, "REQUEST_NOT_PENDING")
    assert friend_ids(client, alice) == []


# --- 공유 수준 / 친구 끊기 ---------------------------------------------------

def test_sharing_settings(client, db):
    alice, bob, carol = make_user(db), make_user(db), make_user(db)
    befriend(client, alice, bob)
    url = f"/api/v1/friends/{bob.id}/sharing"

    assert client.get(url, headers=as_user(alice)).json() == {"class": "DETAILS", "personal": "BUSY", "event": "DETAILS"}
    response = client.patch(url, headers=as_user(alice), json={"class": "BUSY", "event": "HIDDEN"})
    assert response.status_code == 200, response.text
    assert response.json() == {"class": "BUSY", "personal": "BUSY", "event": "HIDDEN"}
    # 반대 방향(bob → alice) 행은 그대로
    assert client.get(f"/api/v1/friends/{alice.id}/sharing", headers=as_user(bob)).json() == {
        "class": "DETAILS", "personal": "BUSY", "event": "DETAILS"
    }

    assert_error(client.patch(url, headers=as_user(alice), json={"class": "PUBLIC"}), 422, "VALIDATION_ERROR")
    assert_error(client.get(f"/api/v1/friends/{carol.id}/sharing", headers=as_user(alice)), 404, "FRIEND_NOT_FOUND")


def test_unfriend(client, db):
    alice, bob = make_user(db), make_user(db)
    befriend(client, alice, bob)

    assert client.delete(f"/api/v1/friends/{alice.id}", headers=as_user(bob)).status_code == 204
    assert friend_ids(client, alice) == [] and friend_ids(client, bob) == []
    assert_error(client.delete(f"/api/v1/friends/{alice.id}", headers=as_user(bob)), 404, "FRIEND_NOT_FOUND")
    assert send(client, alice, bob).json()["status"] == "PENDING"  # 다시 요청 가능
