"""
Integration tests for Phase 5: analytics, audit logs, and read-only system
config — all computed from real data created through real HTTP calls, not
mocked or pre-seeded.
"""


def _register_and_login(client, email="caretaker@example.com", role="CARETAKER"):
    client.post(
        "/auth/register",
        json={"full_name": "Test Caretaker", "email": email, "password": "supersecret123", "role": role},
    )
    resp = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_person_and_device(client, headers):
    person_resp = client.post("/people", json={"name": "Grandfather Rao", "age": 78}, headers=headers)
    person_id = person_resp.json()["id"]
    device_resp = client.post(
        "/devices", json={"device_name": "Watch", "person_id": person_id}, headers=headers
    )
    return person_id, device_resp.json()["id"]


def _simulate_fall(client, headers, device_id):
    return client.post(
        f"/sensors/{device_id}/simulate",
        json={"scenario": "FALL", "duration_seconds": 20},
        headers=headers,
    )


# ---- Analytics: summary ----

def test_summary_is_all_zero_with_no_data(client):
    headers = _register_and_login(client)
    resp = client.get("/analytics/summary", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_emergencies"] == 0
    assert body["avg_acknowledgement_seconds"] is None
    assert body["avg_response_seconds"] is None
    assert body["false_alarm_rate"] == 0.0


def test_summary_reflects_a_real_created_emergency(client):
    headers = _register_and_login(client)
    _person_id, device_id = _create_person_and_device(client, headers)
    sim_resp = _simulate_fall(client, headers, device_id)
    assert sim_resp.status_code == 200

    resp = client.get("/analytics/summary", headers=headers)
    body = resp.json()
    assert body["total_emergencies"] == 1
    assert body["open_count"] == 1
    assert body["high_count"] + body["critical_count"] == 1


def test_summary_avg_response_time_reflects_real_acknowledge_resolve(client):
    headers = _register_and_login(client)
    _person_id, device_id = _create_person_and_device(client, headers)
    sim_resp = _simulate_fall(client, headers, device_id)
    emergency_id = sim_resp.json()["emergency_id"]

    client.post(f"/emergencies/{emergency_id}/acknowledge", headers=headers)
    client.post(f"/emergencies/{emergency_id}/resolve", headers=headers)

    resp = client.get("/analytics/summary", headers=headers)
    body = resp.json()
    assert body["resolved_count"] == 1
    assert body["avg_acknowledgement_seconds"] is not None
    assert body["avg_response_seconds"] is not None
    assert body["avg_response_seconds"] >= 0


def test_summary_false_alarm_rate_computed_correctly(client):
    headers = _register_and_login(client)
    _person_id, device_id = _create_person_and_device(client, headers)
    sim_resp = _simulate_fall(client, headers, device_id)
    emergency_id = sim_resp.json()["emergency_id"]

    client.post(f"/emergencies/{emergency_id}/false-alarm", headers=headers)

    resp = client.get("/analytics/summary", headers=headers)
    body = resp.json()
    assert body["false_alarm_count"] == 1
    assert body["false_alarm_rate"] == 1.0


def test_summary_reflects_device_online_count(client):
    headers = _register_and_login(client)
    _person_id, device_id = _create_person_and_device(client, headers)
    _simulate_fall(client, headers, device_id)  # simulating marks the device ONLINE

    resp = client.get("/analytics/summary", headers=headers)
    body = resp.json()
    assert body["devices_total"] == 1
    assert body["devices_online"] == 1


# ---- Analytics: trends ----

def test_trends_by_type_and_severity_reflect_real_data(client):
    headers = _register_and_login(client)
    _person_id, device_id = _create_person_and_device(client, headers)
    _simulate_fall(client, headers, device_id)

    resp = client.get("/analytics/trends", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    fall_entry = next((t for t in body["by_type"] if t["event_type"] == "FALL"), None)
    assert fall_entry is not None
    assert fall_entry["count"] == 1
    assert sum(s["count"] for s in body["by_severity"]) == 1


def test_trends_daily_counts_has_no_gaps(client):
    headers = _register_and_login(client)
    resp = client.get("/analytics/trends?days=7", headers=headers)
    body = resp.json()
    assert len(body["daily_counts"]) == 7
    # Every entry has a date and a count, even with zero data.
    for point in body["daily_counts"]:
        assert "date" in point
        assert point["count"] >= 0


# ---- Analytics: device uptime ----

def test_device_uptime_reflects_real_device(client):
    headers = _register_and_login(client)
    _person_id, device_id = _create_person_and_device(client, headers)

    resp = client.get("/analytics/device-uptime", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert any(d["device_id"] == device_id for d in body)


def test_analytics_requires_authentication(client):
    resp = client.get("/analytics/summary")
    assert resp.status_code == 401


# ---- Audit logs ----

def test_audit_log_created_on_registration_and_login(client):
    admin_headers = _register_and_login(client, email="admin@example.com", role="ADMIN")

    resp = client.get("/audit-logs", headers=admin_headers)
    assert resp.status_code == 200
    actions = [entry["action"] for entry in resp.json()]
    assert "USER_REGISTERED" in actions
    assert "USER_LOGIN" in actions


def test_audit_log_created_on_failed_login(client):
    client.post(
        "/auth/register",
        json={"full_name": "Someone", "email": "someone@example.com", "password": "correctpass1", "role": "FAMILY"},
    )
    client.post("/auth/login", json={"email": "someone@example.com", "password": "wrongpassword"})

    admin_headers = _register_and_login(client, email="admin@example.com", role="ADMIN")
    resp = client.get("/audit-logs?action=USER_LOGIN_FAILED", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_audit_log_created_on_emergency_lifecycle(client):
    headers = _register_and_login(client, email="admin@example.com", role="ADMIN")
    _person_id, device_id = _create_person_and_device(client, headers)
    sim_resp = _simulate_fall(client, headers, device_id)
    emergency_id = sim_resp.json()["emergency_id"]
    client.post(f"/emergencies/{emergency_id}/acknowledge", headers=headers)
    client.post(f"/emergencies/{emergency_id}/resolve", headers=headers)

    resp = client.get("/audit-logs", headers=headers)
    actions = [entry["action"] for entry in resp.json()]
    assert "EMERGENCY_CREATED" in actions
    assert "EMERGENCY_ACKNOWLEDGED" in actions
    assert "EMERGENCY_RESOLVED" in actions


def test_non_admin_cannot_view_audit_logs(client):
    headers = _register_and_login(client, email="caretaker2@example.com", role="CARETAKER")
    resp = client.get("/audit-logs", headers=headers)
    assert resp.status_code == 403


def test_audit_log_never_contains_password_field(client):
    admin_headers = _register_and_login(client, email="admin@example.com", role="ADMIN")
    resp = client.get("/audit-logs", headers=admin_headers)
    body_text = resp.text.lower()
    assert "supersecret123" not in body_text
    assert "hashed_password" not in body_text


# ---- System config ----

def test_admin_can_view_system_config(client):
    headers = _register_and_login(client, email="admin@example.com", role="ADMIN")
    resp = client.get("/system/config", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "fall_detection" in body
    assert "escalation" in body
    assert body["fall_detection"]["critical_threshold"] == 90


def test_non_admin_cannot_view_system_config(client):
    headers = _register_and_login(client, email="caretaker3@example.com", role="CARETAKER")
    resp = client.get("/system/config", headers=headers)
    assert resp.status_code == 403
