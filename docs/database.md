# Database Design

## Implemented (Phase 4)

**`users`** — id (UUID), full_name, email (unique), hashed_password (bcrypt),
role (ADMIN/CARETAKER/FAMILY/DOCTOR/EMERGENCY_RESPONDER), is_active, created_at

**`people`** — the monitored person: id, name, age, address, latitude/longitude
(manually configured, never claimed as live GPS), assigned_caretaker_id (FK
users), doctor_id (FK users, must have role DOCTOR), medical_notes

**`emergency_contacts`** — id, person_id (FK), name, relation, phone, email,
priority_order (used to pick the highest-priority contact for FAMILY escalation)

**`devices`** — id, device_name, device_type, person_id (FK), status
(ONLINE/OFFLINE), battery_level, last_seen

**`sensor_readings`** — id, device_id (FK), timestamp, heart_rate,
accel_x/y/z, accel_magnitude, orientation, movement, inactivity_duration

**`emergencies`** — id, event_type (FALL/ABNORMAL_HEART_RATE/TRAFFIC_ACCIDENT/
FIRE_SMOKE/GENERAL), person_id (FK, nullable — a general video upload may have
no linked person), device_id (FK, nullable), source (SENSOR_SIMULATOR/
VIDEO_ACCIDENT/VIDEO_FIRE/MANUAL), confidence, severity, status
(OPEN/ACKNOWLEDGED/RESOLVED/FALSE_ALARM), reasons (JSON), location_lat/lng,
escalation_step, created_at, acknowledged_at/by_id, resolved_at/by_id

**`emergency_timeline`** — id, emergency_id (FK), event_text, actor_id
(FK users, nullable for system-generated entries), timestamp

**`notifications`** — id, emergency_id (FK), recipient_role, recipient_name,
recipient_address, channel (EMAIL/TELEGRAM), status (SENT/FAILED/SKIPPED —
every attempt is logged, including failures), detail, escalation_step, created_at

**`video_analyses`** — id, uploaded_by_id (FK users), person_id (FK, nullable),
emergency_id (FK, nullable — only set if the result crossed the HIGH/CRITICAL
threshold), analysis_type (TRAFFIC_ACCIDENT/FIRE_SMOKE), media_type
(VIDEO/IMAGE), status (PENDING/PROCESSING/COMPLETED/FAILED), original_filename,
stored_path, location_lat/lng/label, detected, confidence, severity, reasons
(JSON), event_timestamp_seconds, error_detail, created_at, processed_at

**`evidence`** — id, video_analysis_id (FK), emergency_id (FK, nullable),
file_path, file_type (source_video/source_image/evidence_frame), description

## Not yet implemented

- **`Doctor`** as a dedicated table — kept simple by design: `Person.doctor_id`
  references a `User` with role `DOCTOR` rather than a separate table with its
  own fields. If a real deployment needs doctor-specific fields (specialty,
  license number, etc.), promoting this to its own table is a small, isolated
  migration.
- **`AuditLog`** — lands in Phase 5 alongside the rest of the analytics/audit work.

## Migration approach

`Base.metadata.create_all()` is used for schema creation during active
development for fast iteration. Before any real deployment, generate a
proper Alembic migration (`alembic revision --autogenerate`) from the
current models and switch to `alembic upgrade head`, to avoid schema drift
and to get real migration history.
