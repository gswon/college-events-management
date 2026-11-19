from tests.conftest import assert_error, at, make_event, make_org


def events_in(client, start="2099-01-10T00:00:00Z", end="2099-01-11T00:00:00Z", **params):
    return client.get("/api/v1/events", params={"start": start, "end": end, **params})


def ids(response) -> list[int]:
    return [item["id"] for item in response.json()["items"]]


# --- categories -----------------------------------------------------------

def test_categories_sorted(client, db):
    response = client.get("/api/v1/categories")
    assert response.status_code == 200
    codes = [c["code"] for c in response.json()]
    assert codes == ["SOCIAL", "CAREER", "SPORTS", "ACADEMIC", "ARTS", "WELLNESS", "OTHER"]
    assert response.json()[0] == {"code": "SOCIAL", "name": "Social", "color": "#F59E0B"}


# --- list: range / status / filters -----------------------------------------

def test_overlap_boundaries(client, db):
    ends_at_start = make_event(db, at(9, 22), at(10, 0))      # end_at == start -> excluded
    starts_at_end = make_event(db, at(11, 0), at(11, 2))      # start_at == end -> excluded
    crosses_start = make_event(db, at(9, 23), at(10, 1))
    inside = make_event(db, at(10, 12), at(10, 13))
    spans = make_event(db, at(9, 0), at(12, 0))

    response = events_in(client)
    assert response.status_code == 200
    assert ids(response) == [spans.id, crosses_start.id, inside.id]
    assert ends_at_start.id not in ids(response) and starts_at_end.id not in ids(response)


def test_hidden_excluded_cancelled_included(client, db):
    hidden = make_event(db, at(10, 10), at(10, 11), status="HIDDEN")
    cancelled = make_event(db, at(10, 12), at(10, 13), status="CANCELLED")

    items = events_in(client).json()["items"]
    assert [i["id"] for i in items] == [cancelled.id]
    assert items[0]["status"] == "CANCELLED"
    assert hidden.id not in [i["id"] for i in items]


def test_filters(client, db):
    org = make_org(db)
    career = make_event(db, at(10, 10), at(10, 11), category="CAREER", is_free=True)
    org_event = make_event(db, at(10, 12), at(10, 13), organization_id=org.id, is_free=False)
    unknown_price = make_event(db, at(10, 14), at(10, 15), is_free=None)

    assert ids(events_in(client, category="CAREER")) == [career.id]
    assert ids(events_in(client, organization_id=org.id)) == [org_event.id]
    assert ids(events_in(client, free_only="true")) == [career.id]
    assert unknown_price.id in ids(events_in(client))


def test_request_offset_is_converted_to_utc(client, db):
    # 2099-01-10 09:00-05:00 == 14:00Z
    early = make_event(db, at(10, 13), at(10, 13, 30))
    late = make_event(db, at(10, 14), at(10, 15))
    response = events_in(client, start="2099-01-10T09:00:00-05:00", end="2099-01-10T23:00:00-05:00")
    assert ids(response) == [late.id]
    assert early.id not in ids(response)


# --- list: response shape / pagination ---------------------------------------

def test_list_item_shape(client, db):
    org = make_org(db, name="Chess Club")
    event = make_event(
        db, at(10, 18), at(10, 21), title="Fall Career Fair", category="CAREER",
        organization_id=org.id, location_name="Kimmel Center", description="long text",
    )
    item = events_in(client).json()["items"][0]
    assert item == {
        "id": event.id,
        "title": "Fall Career Fair",
        "start_at": "2099-01-10T18:00:00Z",
        "end_at": "2099-01-10T21:00:00Z",
        "is_all_day": False,
        "location_name": "Kimmel Center",
        "is_online": False,
        "category": {"code": "CAREER", "name": "Career", "color": "#3B82F6"},
        "organization": {"id": org.id, "name": "Chess Club"},
        "host_name": None,
        "image_url": None,
        "is_free": None,
        "status": "ACTIVE",
    }


def test_cursor_pagination_with_ties(client, db):
    same_start = [make_event(db, at(10, 12), at(10, 13)) for _ in range(3)]
    before = make_event(db, at(10, 9), at(10, 10))
    after = make_event(db, at(10, 15), at(10, 16))
    expected = [before.id] + sorted(e.id for e in same_start) + [after.id]

    seen, cursor, pages = [], None, 0
    while True:
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        body = events_in(client, **params).json()
        seen += [i["id"] for i in body["items"]]
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert seen == expected
    assert pages == 3


def test_empty_result(client, db):
    assert events_in(client).json() == {"items": [], "next_cursor": None}


# --- list: errors ---------------------------------------------------------

def test_list_errors(client, db):
    assert_error(client.get("/api/v1/events", params={"end": "2099-01-11T00:00:00Z"}), 422, "VALIDATION_ERROR")
    assert_error(events_in(client, start="2099-01-10T00:00:00"), 422, "VALIDATION_ERROR")  # no UTC offset
    assert_error(events_in(client, start="2099-01-11T00:00:00Z", end="2099-01-10T00:00:00Z"), 400, "INVALID_RANGE")
    assert_error(events_in(client, end="2099-04-13T00:00:00Z"), 400, "INVALID_RANGE")  # 93 days
    assert events_in(client, end="2099-04-12T00:00:00Z").status_code == 200  # 92 days
    assert_error(events_in(client, category="NOPE"), 400, "INVALID_CATEGORY")
    assert_error(events_in(client, cursor="not-a-cursor"), 400, "INVALID_CURSOR")
    assert_error(events_in(client, limit=101), 422, "VALIDATION_ERROR")
    assert_error(events_in(client, followed_only="true"), 401, "AUTH_REQUIRED")  # anonymous


# --- detail ---------------------------------------------------------------

def test_event_detail(client, db):
    org = make_org(db, name="Chess Club")
    event = make_event(
        db, at(10, 18), at(10, 21), organization_id=org.id, description="Bring your resume",
        registration_url="https://example.com/rsvp", price_text="free w/ NYU ID",
    )
    response = client.get(f"/api/v1/events/{event.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["description"] == "Bring your resume"
    assert body["registration_url"] == "https://example.com/rsvp"
    assert body["price_text"] == "free w/ NYU ID"
    assert body["organization"] == {"id": org.id, "name": "Chess Club", "slug": org.slug, "logo_url": None}
    assert body["start_at"] == "2099-01-10T18:00:00Z"
    for internal in ("source", "external_id", "last_synced_at", "category_id", "organization_id"):
        assert internal not in body


def test_event_detail_not_found(client, db):
    hidden = make_event(db, at(10, 18), at(10, 21), status="HIDDEN")
    assert_error(client.get(f"/api/v1/events/{hidden.id}"), 404, "EVENT_NOT_FOUND")
    assert_error(client.get("/api/v1/events/999999999"), 404, "EVENT_NOT_FOUND")
    assert_error(client.get("/api/v1/nope"), 404, "NOT_FOUND")


# --- search (FULLTEXT, needs committed rows) ---------------------------------

def test_search(client, committed_db):
    fair = make_event(committed_db, at(10, 10), at(10, 11), title="Fall Career Fair")
    chess = make_event(committed_db, at(10, 12), at(10, 13), title="Chess Club Meetup",
                       description="Open to all skill levels")
    ai = make_event(committed_db, at(10, 14), at(10, 15), title="AI Talk")
    committed_db.commit()

    assert ids(events_in(client, q="career")) == [fair.id]
    assert ids(events_in(client, q="car")) == [fair.id]                 # prefix
    assert ids(events_in(client, q="skill")) == [chess.id]              # description
    assert ids(events_in(client, q="chess meetup")) == [chess.id]       # every word must match
    assert ids(events_in(client, q="chess career")) == []
    assert ids(events_in(client, q="AI")) == [ai.id]                    # short word -> title LIKE
    assert ids(events_in(client, q='"career" +fair*')) == [fair.id]     # operator characters are ignored


def test_search_operators_only_is_ignored(client, db):
    event = make_event(db, at(10, 10), at(10, 11))
    assert ids(events_in(client, q='+"*')) == [event.id]
