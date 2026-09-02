"""
Integration tests for Phase 3: notifications (honest skip/fail — no SMTP
configured in the test environment, so we verify that's reported correctly
rather than faked as "sent"), acknowledge/resolve/false-alarm actions, and
the escalation scheduler's step logic.
"""
from datetime import datetime, timedelta, timezone

from app.models.emergency import Emergency, EmergencyStatus, Severity
from app.services.escalation import run_escalation_check


def _register_and_login(client, email="caretaker@example.com", role="CARETAKER"):
    client.post(
        "/auth/register",
        json={"full_name": "Test Caretaker", "email": email, "password": "supersecret123", "role": role},
    )
    resp = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_person(client, headers, name="Grandfather Rao", **extra):
    payload = {"name": name, "age": 78}
    payload.update(extra)
    resp = client.post("/people", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_device(client, headers, person_id, name="Watch"):
    resp = client.post("/devices", json={"device_name": name, "person_id": person_id}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _trigger_fall(client, headers, device_id):
    resp = client.post(
        f"/sensors/{device_id}/simulate", json={"scenario": "FALL", "duration_seconds": 20}, headers=headers
    )
    assert resp.status_code == 200
    return resp.json()


# ---- Notifications: honest reporting, no faked sends ----

def test_emergency_creation_logs_a_notification_attempt(client):
    # Person creation defaults assigned_caretaker_id to the creating user,
    # so a caretaker with a real email is always on file here.
    headers = _register_and_login(client)
    person_id = _create_person(client, headers)
    device_id = _create_device(client, headers, person_id)
    result = _trigger_fall(client, headers, device_id)

    notifications = client.get(f"/notifications?emergency_id={result['emergency_id']}", headers=headers).json()
    assert len(notifications) >= 1
    caretaker_notification = notifications[-1]
    assert caretaker_notification["recipient_role"] == "CARETAKER"
    assert caretaker_notification["recipient_address"] == "caretaker@example.com"
    # SMTP isn't configured in the test environment, so this must be
    # honestly reported as FAILED — never faked as SENT.
    assert caretaker_notification["status"] == "FAILED"
    assert "smtp" in caretaker_notification["detail"].lower()


def test_notification_skipped_when_family_contact_has_no_email(client, db_session):
    # The person's only emergency contact has no email on file — when
    # escalation reaches the FAMILY step, that must be reported as
    # SKIPPED (no recipient), never FAILED or SENT.
    headers = _register_and_login(client)
    person_id = _create_person(
        client, headers,
        emergency_contacts=[{"name": "Priya", "relation": "Daughter", "priority_order": 1}],  # no email
    )
    device_id = _create_device(client, headers, person_id)
    result = _trigger_fall(client, headers, device_id)
    emergency_id = result["emergency_id"]

    emergency = db_session.query(Emergency).filter(Emergency.id == emergency_id).first()
    emergency.created_at = datetime.now(timezone.utc) - timedelta(seconds=999)
    db_session.commit()

    run_escalation_check(db_session)

    notifications = client.get(f"/notifications?emergency_id={emergency_id}", headers=headers).json()
    family_notification = [n for n in notifications if n["recipient_role"] == "FAMILY"][0]
    assert family_notification["status"] == "SKIPPED"
    assert "no family configured" in family_notification["detail"].lower()


def test_notification_reports_smtp_not_configured_when_caretaker_exists(client):
    headers = _register_and_login(client)
    # Register a second user to act as the assigned caretaker with a real email on file.
    caretaker_resp = client.post(
        "/auth/register",
        json={"full_name": "Priya Rao", "email": "priya@example.com", "password": "supersecret123", "role": "CARETAKER"},
    )
    caretaker_id = caretaker_resp.json()["id"]

    person_id = _create_person(client, headers, assigned_caretaker_id=caretaker_id)
    device_id = _create_device(client, headers, person_id)
    result = _trigger_fall(client, headers, device_id)

    notifications = client.get(f"/notifications?emergency_id={result['emergency_id']}", headers=headers).json()
    caretaker_notification = [n for n in notifications if n["recipient_role"] == "CARETAKER"][0]
    assert caretaker_notification["recipient_address"] == "priya@example.com"
    # SMTP isn't configured in the test env — must be FAILED, not silently SENT.
    assert caretaker_notification["status"] == "FAILED"
    assert "smtp" in caretaker_notification["detail"].lower()


def test_test_notification_endpoint_reports_smtp_not_configured(client):
    headers = _register_and_login(client, email="admin@example.com", role="ADMIN")
    resp = client.post("/notifications/test?recipient_email=someone@example.com", headers=headers)
    assert resp.status_code == 502
    assert "smtp" in resp.json()["detail"].lower()


def test_non_admin_cannot_send_test_notification(client):
    headers = _register_and_login(client)
    resp = client.post("/notifications/test?recipient_email=someone@example.com", headers=headers)
    assert resp.status_code == 403


# ---- Acknowledge / resolve / false-alarm ----

def test_caretaker_can_acknowledge_then_resolve(client):
    headers = _register_and_login(client)
    person_id = _create_person(client, headers)
    device_id = _create_device(client, headers, person_id)
    result = _trigger_fall(client, headers, device_id)
    emergency_id = result["emergency_id"]

    ack_resp = client.post(f"/emergencies/{emergency_id}/acknowledge", headers=headers)
    assert ack_resp.status_code == 200
    assert ack_resp.json()["status"] == "ACKNOWLEDGED"
    assert ack_resp.json()["acknowledged_at"] is not None

    resolve_resp = client.post(f"/emergencies/{emergency_id}/resolve", headers=headers)
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "RESOLVED"
    assert resolve_resp.json()["resolved_at"] is not None

    timeline_texts = [t["event_text"] for t in resolve_resp.json()["timeline"]]
    assert any("Acknowledged by" in t for t in timeline_texts)
    assert any("Resolved by" in t for t in timeline_texts)


def test_false_alarm_can_be_marked_directly_from_open(client):
    headers = _register_and_login(client)
    person_id = _create_person(client, headers)
    device_id = _create_device(client, headers, person_id)
    result = _trigger_fall(client, headers, device_id)
    emergency_id = result["emergency_id"]

    resp = client.post(f"/emergencies/{emergency_id}/false-alarm", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "FALSE_ALARM"


def test_family_role_cannot_acknowledge(client):
    headers = _register_and_login(client)
    person_id = _create_person(client, headers)
    device_id = _create_device(client, headers, person_id)
    result = _trigger_fall(client, headers, device_id)

    family_headers = _register_and_login(client, email="family@example.com", role="FAMILY")
    resp = client.post(f"/emergencies/{result['emergency_id']}/acknowledge", headers=family_headers)
    assert resp.status_code == 403


def test_cannot_act_on_already_resolved_emergency(client):
    headers = _register_and_login(client)
    person_id = _create_person(client, headers)
    device_id = _create_device(client, headers, person_id)
    result = _trigger_fall(client, headers, device_id)
    emergency_id = result["emergency_id"]

    client.post(f"/emergencies/{emergency_id}/resolve", headers=headers)
    resp = client.post(f"/emergencies/{emergency_id}/acknowledge", headers=headers)
    assert resp.status_code == 409


def test_acknowledging_twice_is_idempotent(client):
    headers = _register_and_login(client)
    person_id = _create_person(client, headers)
    device_id = _create_device(client, headers, person_id)
    result = _trigger_fall(client, headers, device_id)
    emergency_id = result["emergency_id"]

    first = client.post(f"/emergencies/{emergency_id}/acknowledge", headers=headers)
    second = client.post(f"/emergencies/{emergency_id}/acknowledge", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["acknowledged_at"] == second.json()["acknowledged_at"]


# ---- Escalation scheduler logic (called directly, not via the real clock) ----

def test_escalation_fires_family_step_after_delay(client, db_session):
    headers = _register_and_login(client)
    person_id = _create_person(client, headers)
    device_id = _create_device(client, headers, person_id)
    result = _trigger_fall(client, headers, device_id)
    emergency_id = result["emergency_id"]

    # Backdate the emergency so the step-1 delay has already elapsed.
    emergency = db_session.query(Emergency).filter(Emergency.id == emergency_id).first()
    emergency.created_at = datetime.now(timezone.utc) - timedelta(seconds=999)
    db_session.commit()

    sent = run_escalation_check(db_session)
    assert sent >= 1

    db_session.refresh(emergency)
    assert emergency.escalation_step >= 1

    notifications = client.get(f"/notifications?emergency_id={emergency_id}", headers=headers).json()
    assert any(n["recipient_role"] == "FAMILY" for n in notifications)


def test_escalation_skips_doctor_step_for_non_critical_severity(client, db_session):
    headers = _register_and_login(client)
    person_id = _create_person(client, headers)
    device_id = _create_device(client, headers, person_id)
    result = _trigger_fall(client, headers, device_id)
    emergency_id = result["emergency_id"]

    emergency = db_session.query(Emergency).filter(Emergency.id == emergency_id).first()
    emergency.created_at = datetime.now(timezone.utc) - timedelta(seconds=9999)
    if emergency.severity == Severity.CRITICAL:
        emergency.severity = Severity.HIGH  # force the non-critical branch
    db_session.commit()

    run_escalation_check(db_session)
    db_session.refresh(emergency)

    # escalation_step should have advanced past step 2 (skipped, not fired)
    assert emergency.escalation_step == 2
    notifications = client.get(f"/notifications?emergency_id={emergency_id}", headers=headers).json()
    assert not any(n["recipient_role"] == "DOCTOR" for n in notifications)


def test_escalation_stops_once_acknowledged(client, db_session):
    headers = _register_and_login(client)
    person_id = _create_person(client, headers)
    device_id = _create_device(client, headers, person_id)
    result = _trigger_fall(client, headers, device_id)
    emergency_id = result["emergency_id"]

    client.post(f"/emergencies/{emergency_id}/acknowledge", headers=headers)

    emergency = db_session.query(Emergency).filter(Emergency.id == emergency_id).first()
    emergency.created_at = datetime.now(timezone.utc) - timedelta(seconds=9999)
    db_session.commit()

    sent = run_escalation_check(db_session)
    assert sent == 0  # ACKNOWLEDGED emergencies aren't OPEN, so the scheduler ignores them
