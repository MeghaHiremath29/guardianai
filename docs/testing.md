# Testing

## Backend

Run with:
```
cd backend
python -m pytest tests/ -v
```

78 tests total, across 6 files:

- `test_auth.py` (9) — health check, registration, duplicate-email
  rejection, login success/failure, protected routes, role-based auth
- `test_fall_detection.py` (8) — pure unit tests on the fall risk-scoring
  logic against synthetic sensor sequences
- `test_phase2_flow.py` (10) — person/device CRUD + RBAC, simulate →
  emergency creation, duplicate-emergency reinforcement, device status
- `test_phase3_notifications.py` (13) — notification logging, escalation
  timing, acknowledge/resolve/false-alarm, idempotency
- `test_video_detection_engines.py` (12) — pure unit tests on the accident
  and fire/smoke scoring logic against synthetic numeric signal arrays
- `test_video_upload.py` (10) — integration tests that generate genuinely
  synthetic video/image files with OpenCV *inside the test itself* and
  upload them through the real FastAPI endpoint and real CV pipeline
- `test_phase5_analytics_audit.py` (16) — analytics numbers computed
  against real created/acknowledged/resolved emergencies (not fixtures),
  audit-log entries verified for every logged action type, RBAC on
  `/audit-logs` and `/system/config`, and a check that audit log responses
  never contain a password or password hash

Tests run against an isolated SQLite database (`test_guardianai.db`),
created and dropped per test function, and file-upload tests write to an
isolated temp directory — neither touches your real dev database or
`data/` folder (see `tests/conftest.py`).

## Frontend

Not implemented yet — component tests land alongside the pages they cover,
in a future phase. All frontend pages were manually verified against the
live backend during development (see README's Phase 1–5 verification
notes), but there's no automated frontend test runner configured yet.
