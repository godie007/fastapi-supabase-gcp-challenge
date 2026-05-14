"""Users API HTTP contract — status codes, headers, validation, and conflict mapping."""

from __future__ import annotations

import uuid

import pytest


def test_create_user_happy_path(client, sample_user_payload):
    response = client.post("/users/", json=sample_user_payload)
    assert response.status_code == 201
    body = response.json()
    uid = uuid.UUID(body["id"])
    assert response.headers["location"] == f"http://testserver/users/{uid}"
    assert body["username"] == sample_user_payload["username"]
    assert body["email"] == sample_user_payload["email"]


def test_register_user_happy_path(client):
    payload = {
        "username": "newsignup",
        "email": "newsignup@example.com",
        "first_name": "New",
        "last_name": "User",
        "role": "guest",
        "active": True,
    }
    response = client.post("/users/register", json=payload)
    assert response.status_code == 201
    body = response.json()
    uid = uuid.UUID(body["id"])
    assert response.headers["location"] == f"http://testserver/users/{uid}"
    assert body["username"] == payload["username"]
    assert body["email"] == payload["email"]
    assert body["role"] == "guest"
    assert uuid.UUID(body["id"])


def test_register_user_duplicate_email_conflict(client):
    payload = {
        "username": "u_reg_a",
        "email": "shared_reg@example.com",
        "first_name": "A",
        "last_name": "A",
        "role": "user",
        "active": True,
    }
    assert client.post("/users/register", json=payload).status_code == 201
    conflict = {
        **payload,
        "username": "u_reg_b",
    }
    response = client.post("/users/register", json=conflict)
    assert response.status_code == 409


def test_get_user_not_found(client):
    missing_id = uuid.uuid4()
    response = client.get(f"/users/{missing_id}")
    assert response.status_code == 404


def test_get_user_happy_path(client, sample_user_payload):
    created = client.post("/users/", json=sample_user_payload).json()
    user_id = created["id"]
    response = client.get(f"/users/{user_id}")
    assert response.status_code == 200
    assert response.json()["id"] == user_id


def test_list_users(client, sample_user_payload):
    client.post("/users/", json=sample_user_payload)
    response = client.get("/users/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1


def test_patch_user_happy_path(client, sample_user_payload):
    created = client.post("/users/", json=sample_user_payload).json()
    user_id = created["id"]
    response = client.patch(
        f"/users/{user_id}",
        json={"first_name": "Janet", "role": "admin"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "Janet"
    assert body["role"] == "admin"


def test_patch_user_empty_body_keeps_representation(client, sample_user_payload):
    """PATCH with no fields set is accepted; resource is refreshed unchanged aside from timestamps."""
    created = client.post("/users/", json=sample_user_payload).json()
    user_id = created["id"]
    r = client.patch(f"/users/{user_id}", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == sample_user_payload["username"]
    assert body["email"] == sample_user_payload["email"]


def test_patch_user_not_found(client):
    missing_id = uuid.uuid4()
    response = client.patch(f"/users/{missing_id}", json={"first_name": "X"})
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("params",),
    (
        ({"skip": -1},),
        ({"limit": 0},),
        ({"limit": 501},),
        ({"skip": "x"},),
    ),
)
def test_list_users_validation_422(client, params):
    assert client.get("/users/", params=params).status_code == 422


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_user_id_path_invalid_uuid_rejected(client, method):
    bogus = "/users/definitely-not-uuid"
    if method == "get":
        assert client.get(bogus).status_code == 422
    elif method == "patch":
        assert client.patch(bogus, json={"first_name": "z"}).status_code == 422
    else:
        assert client.delete(bogus).status_code == 422


def test_delete_user_happy_path(client, sample_user_payload):
    created = client.post("/users/", json=sample_user_payload).json()
    user_id = created["id"]
    response = client.delete(f"/users/{user_id}")
    assert response.status_code == 204
    assert response.content == b""


def test_delete_user_not_found(client):
    missing_id = uuid.uuid4()
    response = client.delete(f"/users/{missing_id}")
    assert response.status_code == 404


def test_duplicate_username_conflict(client, sample_user_payload):
    assert client.post("/users/", json=sample_user_payload).status_code == 201
    dup = {**sample_user_payload, "email": "other@example.com"}
    response = client.post("/users/", json=dup)
    assert response.status_code == 409


def test_duplicate_email_conflict(client, sample_user_payload):
    assert client.post("/users/", json=sample_user_payload).status_code == 201
    dup = {**sample_user_payload, "username": "otheruser"}
    response = client.post("/users/", json=dup)
    assert response.status_code == 409


def test_patch_duplicate_username_conflict(client):
    a = client.post(
        "/users/",
        json={
            "username": "alice_pt",
            "email": "alice_pt@example.com",
            "first_name": "A",
            "last_name": "A",
            "role": "user",
            "active": True,
        },
    )
    b = client.post(
        "/users/",
        json={
            "username": "bob_pt",
            "email": "bob_pt@example.com",
            "first_name": "B",
            "last_name": "B",
            "role": "user",
            "active": True,
        },
    )
    assert a.status_code == b.status_code == 201
    bid = b.json()["id"]
    clash = client.patch(f"/users/{bid}", json={"username": "alice_pt"})
    assert clash.status_code == 409
    assert "Username already exists" in clash.json()["detail"]


def test_patch_normalized_email_conflict(client):
    first = client.post(
        "/users/",
        json={
            "username": "owner_em",
            "email": "shared_norm@example.com",
            "first_name": "O",
            "last_name": "O",
            "role": "user",
            "active": True,
        },
    )
    second = client.post(
        "/users/",
        json={
            "username": "other_em",
            "email": "other_em@example.com",
            "first_name": "T",
            "last_name": "T",
            "role": "user",
            "active": True,
        },
    )
    assert first.status_code == second.status_code == 201
    sid = second.json()["id"]
    stolen = client.patch(f"/users/{sid}", json={"email": "  SHARED_NORM@EXAMPLE.COM  "})
    assert stolen.status_code == 409


def test_create_invalid_role_returns_422(client, sample_user_payload):
    bad = {**sample_user_payload, "role": "superuser"}
    assert client.post("/users/", json=bad).status_code == 422


def test_create_missing_required_field_returns_422(client):
    assert client.post("/users/", json={"username": "only"}).status_code == 422


def test_create_invalid_email_format_returns_422(client, sample_user_payload):
    bad = {**sample_user_payload, "email": "not-an-email"}
    assert client.post("/users/", json=bad).status_code == 422


def test_email_normalized_for_uniqueness(client, sample_user_payload):
    """Same mailbox with different casing / surrounding spaces must conflict (409)."""
    assert client.post("/users/", json=sample_user_payload).status_code == 201
    dup = {
        **sample_user_payload,
        "username": "otheruser",
        "email": "  JDOE@Example.COM  ",
    }
    assert client.post("/users/", json=dup).status_code == 409


def test_create_stores_trimmed_lowercase_email(client):
    payload = {
        "username": "trimmail",
        "email": "  Trim.Mail@Example.COM  ",
        "first_name": " Trim ",
        "last_name": " User ",
        "role": "user",
        "active": True,
    }
    r = client.post("/users/", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "trim.mail@example.com"
    assert body["username"] == "trimmail"
    assert body["first_name"] == "Trim"
    assert body["last_name"] == "User"


def test_whitespace_only_username_returns_422(client, sample_user_payload):
    bad = {**sample_user_payload, "username": "   "}
    assert client.post("/users/", json=bad).status_code == 422
