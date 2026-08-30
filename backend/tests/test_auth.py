"""
Real integration tests for the auth flow — no mocking of the DB or auth logic.
"""


def _register(client, email="alice@example.com", role="FAMILY"):
    return client.post(
        "/auth/register",
        json={"full_name": "Alice Test", "email": email, "password": "supersecret123", "role": role},
    )


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_register_creates_user(client):
    resp = _register(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "alice@example.com"
    assert "hashed_password" not in body  # never leak password hash


def test_register_duplicate_email_rejected(client):
    _register(client)
    resp = _register(client)
    assert resp.status_code == 409


def test_login_with_correct_credentials_returns_tokens(client):
    _register(client)
    resp = client.post("/auth/login", json={"email": "alice@example.com", "password": "supersecret123"})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body


def test_login_with_wrong_password_rejected(client):
    _register(client)
    resp = client.post("/auth/login", json={"email": "alice@example.com", "password": "wrongpassword"})
    assert resp.status_code == 401


def test_protected_endpoint_requires_token(client):
    resp = client.get("/users/me")
    assert resp.status_code == 401


def test_protected_endpoint_works_with_valid_token(client):
    _register(client)
    login_resp = client.post("/auth/login", json={"email": "alice@example.com", "password": "supersecret123"})
    token = login_resp.json()["access_token"]

    resp = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "alice@example.com"


def test_non_admin_cannot_list_users(client):
    _register(client, email="bob@example.com", role="CARETAKER")
    login_resp = client.post("/auth/login", json={"email": "bob@example.com", "password": "supersecret123"})
    token = login_resp.json()["access_token"]

    resp = client.get("/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_admin_can_list_users(client):
    _register(client, email="admin@example.com", role="ADMIN")
    login_resp = client.post("/auth/login", json={"email": "admin@example.com", "password": "supersecret123"})
    token = login_resp.json()["access_token"]

    resp = client.get("/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
