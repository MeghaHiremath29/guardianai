"""
Integration tests for Phase 2: person/device management, sensor ingestion,
the fall-detection pipeline, and the Emergency Engine — all through real
HTTP calls against the actual FastAPI app and an isolated test database.
"""


def _register_and_login(client, email="caretaker@example.com", role="CARETAKER"):
    client.post(
        "/auth/register",
        json={"full_name": "Test Caretaker", "email": email, "password": "supersecret123", "role": role},
    )
    resp = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_person(client, headers, name="Grandfather Rao"):
    resp = client.post("/people", json={"name": name, "age": 78}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_device(client, headers, person_id, name="Watch"):
    resp = client.post("/devices", json={"device_name": name, "person_id": person_id}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


# ---- People ----

def test_caretaker_can_create_person_with_contacts(client):
    headers = _register_and_login(client)
    resp = client.post(
        "/people",
        json={
            "name": "Grandfather Rao",
            "age": 78,
            "latitude": 12.97,
            "longitude": 77.59,
            "emergency_contacts": [{"name": "Priya", "relation": "Daughter", "priority_order": 1}],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Grandfather Rao"
    assert len(body["emergency_contacts"]) == 1


def test_family_role_cannot_create_person(client):
    headers = _register_and_login(client, email="family@example.com", role="FAMILY")
    resp = client.post("/people", json={"name": "Someone"}, headers=headers)
    assert resp.status_code == 403


def test_list_people_requires_auth(client):
    resp = client.get("/people")
    assert resp.status_code == 401


# ---- Devices ----

def test_create_device_for_nonexistent_person_returns_404(client):
    headers = _register_and_login(client)
    resp = client.post("/devices", json={"device_name": "Watch", "person_id": "does-not-exist"}, headers=headers)
    assert resp.status_code == 404


def test_device_starts_offline_with_full_battery(client):
    headers = _register_and_login(client)
    person_id = _create_person(client, headers)
    device_id = _create_device(client, headers, person_id)

    resp = client.get(f"/devices/{device_id}", headers=headers)
    body = resp.json()
    assert body["status"] == "OFFLINE"
    assert body["battery_level"] == 100.0


# ---- Sensor ingestion + fall detection + Emergency Engine ----

def test_normal_readings_never_create_an_emergency(client):
    headers = _register_and_login(client)
    person_id = _create_person(client, headers)
    device_id = _create_device(client, headers, person_id)

    for _ in range(5):
        resp = client.post(
            f"/sensors/{device_id}/reading",
            json={
                "heart_rate": 70, "accel_x": 0.1, "accel_y": 0.1, "accel_z": 1.0,
                "accel_magnitude": 1.0, "orientation": "upright", "movement": "active",
                "inactivity_duration": 0.0,
            },
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["emergency_created"] is False

    emergencies = client.get("/emergencies", headers=headers).json()
    assert emergencies == []


def test_fall_simulation_creates_an_emergency_with_timeline(client):
    headers = _register_and_login(client)
    person_id = _create_person(client, headers)
    device_id = _create_device(client, headers, person_id)

    resp = client.post(
        f"/sensors/{device_id}/simulate",
        json={"scenario": "FALL", "duration_seconds": 20},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["emergency_created"] is True
    assert body["severity"] in ("HIGH", "CRITICAL")
    assert "sudden acceleration spike" in body["reasons"]

    emergency_id = body["emergency_id"]
    detail = client.get(f"/emergencies/{emergency_id}", headers=headers).json()
    assert detail["status"] == "OPEN"
    assert detail["person_id"] == person_id
    assert detail["device_id"] == device_id
    assert len(detail["timeline"]) >= 2


def test_invalid_scenario_name_is_rejected(client):
    headers = _register_and_login(client)
    person_id = _create_person(client, headers)
    device_id = _create_device(client, headers, person_id)

    resp = client.post(
        f"/sensors/{device_id}/simulate",
        json={"scenario": "NOT_A_REAL_SCENARIO", "duration_seconds": 10},
        headers=headers,
    )
    assert resp.status_code == 422


def test_repeated_fall_signals_reinforce_rather_than_duplicate(client):
    headers = _register_and_login(client)
    person_id = _create_person(client, headers)
    device_id = _create_device(client, headers, person_id)

    first = client.post(
        f"/sensors/{device_id}/simulate", json={"scenario": "FALL", "duration_seconds": 20}, headers=headers
    ).json()
    assert first["emergency_created"] is True

    second = client.post(
        f"/sensors/{device_id}/simulate",
        json={"scenario": "FALL_HIGH_HEART_RATE", "duration_seconds": 20},
        headers=headers,
    ).json()
    assert second["emergency_created"] is True

    # Same person + same event type within the dedup window -> same emergency id.
    assert first["emergency_id"] == second["emergency_id"]

    emergencies = client.get("/emergencies", headers=headers).json()
    assert len(emergencies) == 1


def test_device_status_and_last_seen_update_after_reading(client):
    headers = _register_and_login(client)
    person_id = _create_person(client, headers)
    device_id = _create_device(client, headers, person_id)

    client.post(
        f"/sensors/{device_id}/reading",
        json={
            "heart_rate": 70, "accel_x": 0, "accel_y": 0, "accel_z": 1.0,
            "accel_magnitude": 1.0, "orientation": "upright", "movement": "active",
            "inactivity_duration": 0.0,
        },
        headers=headers,
    )
    device = client.get(f"/devices/{device_id}", headers=headers).json()
    assert device["status"] == "ONLINE"
    assert device["last_seen"] is not None
