"""Business rules over the HTTP API: catalogue behaviour, identity conflicts, lifecycle.

Uses the same stack as production (FastAPI + SQLAlchemy) with an isolated in-memory SQLite DB
per test module run — fast in CI, focused on domain invariants rather than transport edge cases.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.conftest import user_payload


def test_empty_directory_lists_no_users(client):
    """Greenfield: no phantom rows in the user catalogue (admin dashboards start clean)."""
    assert client.get("/users/").json() == []


def test_pagination_returns_stable_window_without_overlap(client):
    """Listing is paged: each page has the expected size until the tail (ops exports, support consoles)."""
    total = 25
    for i in range(total):
        r = client.post("/users/", json=user_payload(i))
        assert r.status_code == 201, r.text

    page1 = client.get("/users/", params={"skip": 0, "limit": 10})
    page2 = client.get("/users/", params={"skip": 10, "limit": 10})
    page3 = client.get("/users/", params={"skip": 20, "limit": 10})

    assert len(page1.json()) == 10
    assert len(page2.json()) == 10
    assert len(page3.json()) == 5

    ids_page1 = {row["id"] for row in page1.json()}
    ids_page2 = {row["id"] for row in page2.json()}
    assert not (ids_page1 & ids_page2)


def test_cannot_steal_another_identity_on_patch(client):
    """Email/username are global identifiers: partial updates must not hijack another account."""
    a = client.post("/users/", json=user_payload(1, username="alice", email="alice@example.com")).json()
    client.post("/users/", json=user_payload(2, username="bob", email="bob@example.com"))

    hijack = client.patch(f"/users/{a['id']}", json={"email": "bob@example.com"})
    assert hijack.status_code == 409
    assert "Email already exists" in hijack.json()["detail"]

    still_alice = client.get(f"/users/{a['id']}").json()
    assert still_alice["email"] == "alice@example.com"


def test_suspended_account_stays_addressable_for_audit(client):
    """Deactivated users remain readable (support, audit) — product does not hide them from GET."""
    created = client.post(
        "/users/",
        json=user_payload(0, username="leaver", email="leaver@example.com"),
    ).json()
    user_id = created["id"]

    off = client.patch(f"/users/{user_id}", json={"active": False})
    assert off.status_code == 200
    body = off.json()
    assert body["active"] is False

    fetched = client.get(f"/users/{user_id}").json()
    assert fetched["active"] is False

    listed = client.get("/users/", params={"limit": 500}).json()
    assert any(u["id"] == user_id and u["active"] is False for u in listed)


def test_offboarding_removes_user_from_active_directory(client):
    """After hard delete, the subject no longer appears in collection responses (GDPR-style removal from service)."""
    ids = []
    for i in range(3):
        r = client.post("/users/", json=user_payload(i + 100))
        assert r.status_code == 201
        ids.append(r.json()["id"])

    assert len(client.get("/users/", params={"limit": 500}).json()) == 3

    target = ids[1]
    assert client.delete(f"/users/{target}").status_code == 204

    rows = client.get("/users/", params={"limit": 500}).json()
    remaining_ids = {r["id"] for r in rows}
    assert target not in remaining_ids
    assert len(rows) == 2


def test_role_promotion_from_guest_to_admin(client):
    """Access posture can evolve (guest contractors → admins) without recreating identity."""
    created = client.post(
        "/users/",
        json=user_payload(0, username="grower", email="grower@example.com", role="guest"),
    ).json()
    assert created["role"] == "guest"

    promoted = client.patch(f"/users/{created['id']}", json={"role": "admin"}).json()
    assert promoted["role"] == "admin"


def test_idempotent_recreate_after_delete_reuses_logical_slot(client):
    """After deletion, identifiers can be re-registered — common when correcting bad imports."""
    payload = user_payload(0, username="reusable", email="reusable@example.com")
    first = client.post("/users/", json=payload).json()
    assert client.delete(f"/users/{first['id']}").status_code == 204

    second = client.post("/users/", json=payload)
    assert second.status_code == 201
    assert second.json()["email"] == payload["email"]


@pytest.mark.parametrize("field", ["username", "email"])
def test_field_level_duplicate_messages_support_ops_triage(client, field):
    """409 responses name the offending field-level constraint (less guesswork when synchronising directories)."""
    base = user_payload(0, username="u1", email="e1@example.com")
    assert client.post("/users/", json=base).status_code == 201

    conflict = dict(base)
    if field == "username":
        conflict["username"] = "u1"
        conflict["email"] = "e2@example.com"
    else:
        conflict["username"] = "u2"
        conflict["email"] = "e1@example.com"

    resp = client.post("/users/", json=conflict)
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    has_user = "Username already exists" in detail
    has_mail = "Email already exists" in detail
    assert has_user ^ has_mail


def test_audit_timestamps_move_forward_on_updates(client):
    """Auditors expect created_at immutable and updated_at monotonic across profile corrections."""
    payload = user_payload(0, username="audited", email="audited@example.com")
    created = client.post("/users/", json=payload).json()
    bumped = client.patch(f"/users/{created['id']}", json={"last_name": "UpdatedAlt"}).json()

    ca = datetime.fromisoformat(created["created_at"].replace("Z", "+00:00"))
    ua1 = datetime.fromisoformat(bumped["updated_at"].replace("Z", "+00:00"))
    assert bumped["created_at"] == created["created_at"]

    ca = ca if ca.tzinfo else ca.replace(tzinfo=UTC)
    ua1 = ua1 if ua1.tzinfo else ua1.replace(tzinfo=UTC)
    assert ua1 >= ca.replace(microsecond=0)

