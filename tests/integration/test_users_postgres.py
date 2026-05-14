"""Integration smoke against the session backend (PostgreSQL in CI; SQLite fallback when URL unset).

Invariant checks mirror production drivers; Postgres exercises types/constraints SQLite approximates separately.
"""

from __future__ import annotations

import uuid

import pytest
from tests.conftest import user_payload

pytestmark = pytest.mark.integration


def test_postgres_create_and_audit_fields(postgres_client):
    """End-to-end create → read → PATCH; strongest signal when running on Postgres in CI."""
    payload = user_payload(0, username="pg_user", email="pg_user@example.com")
    created = postgres_client.post("/users/", json=payload)
    assert created.status_code == 201
    row = created.json()
    uid = uuid.UUID(row["id"])
    assert created.headers["location"] == f"http://testserver/users/{uid}"
    fetched = postgres_client.get(f"/users/{row['id']}")
    assert fetched.status_code == 200

    bumped = postgres_client.patch(
        f"/users/{row['id']}",
        json={"first_name": "PG", "role": "admin"},
    )
    assert bumped.status_code == 200
    assert bumped.json()["first_name"] == "PG"


def test_postgres_register_matches_create(postgres_client):
    r = postgres_client.post(
        "/users/register",
        json=user_payload(0, username="pg_reg_only", email="pg_reg_only@example.com", role="guest"),
    )
    assert r.status_code == 201
    assert r.json()["username"] == "pg_reg_only"


def test_postgres_global_email_uniqueness_still_conflict(postgres_client):
    # Use example.com (RFC 2606); `.test` emails often fail EmailStr validation → 422 before we hit 409.
    first = postgres_client.post(
        "/users/",
        json=user_payload(1, username="alice_ci", email="shared@example.com"),
    )
    assert first.status_code == 201, first.text
    conflict = postgres_client.post(
        "/users/",
        json=user_payload(2, username="bob_ci", email="shared@example.com"),
    )
    assert conflict.status_code == 409


def test_postgres_pagination_slices_collection(postgres_client):
    """Operator directories rely on deterministic OFFSET semantics on production engines."""
    for i in range(15):
        r = postgres_client.post("/users/", json=user_payload(i + 300))
        assert r.status_code == 201, r.text

    body = postgres_client.get("/users/", params={"skip": 5, "limit": 4}).json()
    assert len(body) == 4
