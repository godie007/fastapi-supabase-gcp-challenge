import uuid


def test_create_user_happy_path(client, sample_user_payload):
    response = client.post("/users/", json=sample_user_payload)
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == sample_user_payload["username"]
    assert body["email"] == sample_user_payload["email"]
    assert uuid.UUID(body["id"])


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


def test_patch_user_not_found(client):
    missing_id = uuid.uuid4()
    response = client.patch(f"/users/{missing_id}", json={"first_name": "X"})
    assert response.status_code == 404


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
