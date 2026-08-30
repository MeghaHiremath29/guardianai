# GuardianAI 🚨
### Intelligent Multi-Emergency Detection & Response System

**Status: Phase 4 complete** — auth, people/device management, the software sensor simulator, fall detection, the Emergency Engine, real email/Telegram notifications, escalation, acknowledge/resolve/false-alarm, and real computer-vision video/image analysis (traffic accident + fire/smoke) with evidence storage are all built and verified working end-to-end. Phase 5 (analytics, maps, audit logs) is not yet implemented — see [Roadmap](#roadmap) below.

---

## 1. Problem Statement

Elderly falls, traffic accidents, and fires often go unnoticed until it's too late, because there's no automated system watching for them and routing an alert to the right person fast. GuardianAI is a prototype software system that ingests sensor data and uploaded video/images, runs AI-assisted detection, and manages the resulting emergency through notification, escalation, and resolution — entirely in software, with no dedicated hardware required for this version.

## 2. Objectives

- Detect possible elderly falls / health emergencies from simulated wearable sensor data
- Detect possible traffic accidents from uploaded video using computer vision
- Detect possible fire/smoke from uploaded images/video using computer vision
- Route every detection through a single, auditable Emergency Engine with configurable severity thresholds
- Escalate unacknowledged emergencies through a caretaker → family → doctor chain
- Provide a professional, role-based dashboard with full incident history and analytics

## 3. Features (see Roadmap for what's live today)

| Area | Feature |
|---|---|
| Auth | JWT login/register, bcrypt hashing, role-based access (ADMIN, CARETAKER, FAMILY, DOCTOR, EMERGENCY_RESPONDER) |
| Fall detection | Software sensor simulator + configurable rule-based risk engine |
| Accident detection | Video upload + CV-based vehicle/motion analysis |
| Fire detection | Image/video upload + CV-based fire/smoke heuristic |
| Emergency engine | Centralized severity + status pipeline for all detection sources |
| Escalation | Configurable, timed notification chain with full timeline |
| Notifications | Real email (SMTP), optional Telegram |
| Analytics | Charts on volume, severity, response time, false-alarm rate |

## 4. System Architecture

```
Frontend (React/Vite/TS) → REST + polling/SSE → Backend (FastAPI)
                                                     │
                                    Emergency Engine (severity, escalation)
                                                     │
                              AI layer: fall risk engine / accident CV / fire CV
                                                     │
                                   SQLite (dev) → Postgres-ready schema
```

The Emergency Engine is the single funnel: detection modules never write emergencies directly to the database — they emit a result, and the engine applies thresholds and creates the record. This keeps severity logic in one place and testable.

## 5. Technology Stack

**Frontend:** React 18, Vite, TypeScript, Tailwind CSS, Axios, React Router, Recharts (charts land in Phase 5)
**Backend:** Python 3.11+, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2.0, Alembic
**Database:** SQLite for local dev; schema written to be Postgres-compatible
**AI/ML:** NumPy/Pandas for the fall-risk engine's sensor math; OpenCV for real frame/pixel processing in both video detectors — motion-magnitude analysis for accidents, HSV color+texture analysis for fire/smoke (both are classical CV baselines, not trained models; see `docs/ai_models.md` for why, and for the documented YOLOv8n upgrade path that was considered but not implemented)
**Auth:** JWT (access + refresh), bcrypt via passlib

## 6. Folder Structure

```
guardianai/
├── frontend/            React + Vite + TS app
│   └── src/{pages,components,services,context}
├── backend/
│   └── app/
│       ├── api/{auth,users,...}   REST endpoints (grows each phase)
│       ├── core/                  config, security, logging
│       ├── db/                    engine/session, model registry
│       ├── models/                SQLAlchemy ORM
│       ├── schemas/                Pydantic request/response models
│       ├── services/              business logic (emergency engine, escalation, notifications)
│       ├── ai/                    fall_detection / accident_detection / fire_detection (all implemented)
│       └── main.py
│   ├── alembic/                   migrations
│   └── tests/                     pytest suite
├── ml/                   datasets, notebooks, training scripts, simulator/
├── data/{uploads,processed,evidence,sample}
├── docs/                 architecture, api, database, ai_models, testing, deployment
└── README.md
```

## 7. Database Design (Phase 4 scope)

`User`, `Person`, `EmergencyContact`, `Device`, `SensorReading`, `Emergency`, `EmergencyTimeline`, `Notification`, `VideoAnalysis`, `Evidence` are all implemented. Only `Doctor` (kept simple — `Person.doctor_id` references a `User` with role `DOCTOR` rather than a separate table) and `AuditLog` (Phase 5) remain. See `docs/database.md`.

## 8. AI/ML Methodology

Three components are implemented, all classical/rule-based baselines (no trained models — none were fabricated, per the project's core rule against fake metrics). Full per-component documentation — problem definition, dataset, preprocessing, features, algorithm, validation, and honestly-reported metrics ("not available until trained on a real dataset") — is in `docs/ai_models.md`.

## 9. Installation (Windows / PowerShell)

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- Git (optional)

### Backend

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
```

Open `.env` and set at minimum:
- `SECRET_KEY` — generate one with:
  ```powershell
  python -c "import secrets; print(secrets.token_urlsafe(64))"
  ```
- Leave `DATABASE_URL` as the default SQLite URL for local dev.

Run the API:

```powershell
python -m uvicorn app.main:app --reload
```

Backend is now live at `http://localhost:8000`. Interactive API docs: `http://localhost:8000/docs`.

### Frontend

```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```

Frontend is now live at `http://localhost:5173`.

### macOS / Linux equivalents

```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt --break-system-packages
cp .env.example .env
python -m uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

## 10. Environment Variables

See `backend/.env.example` and `frontend/.env.example` — every value is explained inline. Nothing is hard-coded in source; `SECRET_KEY`, database URL, SMTP, and Telegram credentials all come from `.env`, which is git-ignored.

## 11. Running Tests

```powershell
cd backend
venv\Scripts\activate
python -m pytest tests/ -v
```

62 tests currently cover:
- **Auth (9)** — health check, registration, duplicate-email rejection, login success/failure, protected routes, role-based authorization
- **Fall detection engine (8)** — pure unit tests on the risk-scoring logic: normal activity, spike-only (not yet high), spike+stillness (escalates), spike+stillness+abnormal heart rate (critical), heart-rate-alone, walking, empty-window handling, confidence bounds
- **Phase 2 flow (10)** — person/device CRUD + RBAC, simulate→emergency creation, duplicate-emergency reinforcement instead of spam, device status/last-seen updates
- **Phase 3 notifications & escalation (13)** — notification logging (sent/failed/skipped, all honestly reported), acknowledge→resolve flow, false-alarm, idempotency, blocked actions on closed emergencies, timed escalation firing, critical-only doctor step, escalation stopping once acknowledged
- **Video/CV detection engines (12)** — pure unit tests on the accident and fire/smoke scoring logic: steady motion vs. spike-then-stillness, spike-that-never-settles rejected, static-camera edge case, single-frame color flash correctly NOT persisted, persistent fire/smoke correctly detected, confidence never claims near-certainty
- **Video upload integration (10)** — uploads genuinely synthetic video/image files (generated with OpenCV in the test itself) through the real FastAPI endpoint and the real CV pipeline: accident video analysis, false-positive rejection on steady footage, fire-colored image detection, false-positive rejection on plain gray images, auto-emergency-creation on HIGH/CRITICAL, wrong-media-type rejection, unsupported extension rejection, auth requirement, list/detail, and real evidence-file retrieval

Tests that upload files write to an isolated temp directory (not your real `data/` folder), and all tests run against an isolated SQLite file, never your dev database.

## 12. How to Use the Sensor Simulator / Video Upload

**The sensor simulator has two forms, both real:**

1. **Built-in scenario runner** (server-side, synchronous) — from the UI's Sensor Monitor page, or directly:
   ```
   POST /sensors/{device_id}/simulate
   { "scenario": "FALL_HIGH_HEART_RATE", "duration_seconds": 30 }
   ```
   Valid scenarios: `NORMAL`, `WALKING`, `FALL`, `FALL_HIGH_HEART_RATE`, `INACTIVITY_AFTER_FALL`.
   This generates a realistic reading sequence and feeds each reading through the exact same
   ingestion pipeline a real device POST would use — it does not create emergencies directly.

2. **Standalone external script** (`ml/simulator/sensor_simulator.py`) — a separate Python
   process that only talks to the backend over HTTP, exactly like a real wearable's companion
   app would:
   ```powershell
   cd guardianai
   pip install requests
   python ml\simulator\sensor_simulator.py --login caretaker@example.com --password yourpassword `
     --base-url http://localhost:8000 --device-id <device-uuid> --scenario FALL_HIGH_HEART_RATE `
     --duration 30
   ```
   You'll see each reading printed with its live confidence/severity as the fall-detection engine
   evaluates it, and the script stops the moment an emergency is actually created.

**Video / image upload (traffic accident + fire/smoke) — from the UI's Video Analysis page, or directly:**

```
POST /videos/upload
Content-Type: multipart/form-data

file: <your .mp4/.avi/.mov or .jpg/.png file>
analysis_type: TRAFFIC_ACCIDENT | FIRE_SMOKE
person_id: <optional — links the result to a monitored person>
```

- **Traffic accident detection requires a video** (motion analysis needs consecutive frames);
  a still image is rejected with a 400.
- **Fire/smoke detection accepts either a video or a single image.**
- Processing is real and synchronous — the response you get back is the actual analysis result
  (confidence, severity, contributing reasons, an evidence frame you can fetch), not a placeholder
  you have to poll for. On genuinely long videos this can take a few seconds; the frontend's upload
  timeout is set to 2 minutes to accommodate that.
- A HIGH/CRITICAL result is automatically routed through the same Emergency Engine used by fall
  detection — you'll see a real `Emergency` created (with notifications/escalation firing exactly
  as in Phase 3) if the confidence clears the threshold.
- Sample test videos/images aren't bundled (see `data/sample/` — empty by design, no synthetic
  "always triggers" fixtures shipped). To try it yourself: any real dashcam clip works for traffic
  accident testing (a clip with a sudden stop/impact is most likely to trigger a HIGH/CRITICAL
  result); any photo of an actual flame or a strongly orange/red-dominated image works for fire
  detection testing.

To get a `device-uuid`, create a Person and a Device first via the People / Devices pages in the
UI, or via `POST /people` and `POST /devices`.

## 13. Notification Setup

Notifications are real — nothing is faked. If SMTP isn't configured, the system honestly logs a `SKIPPED`/`FAILED` notification rather than pretending it sent.

### Email (required for real sends)

1. Use a real SMTP account. The easiest option for testing is a Gmail account with an [App Password](https://myaccount.google.com/apppasswords) (regular Gmail passwords won't work with SMTP).
2. In `backend/.env`, set:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=youraccount@gmail.com
   SMTP_PASSWORD=your16charapppassword
   SMTP_FROM_EMAIL=youraccount@gmail.com
   ```
3. Restart the backend. Test it without waiting for a real emergency:
   - As an ADMIN user, call `POST /notifications/test?recipient_email=you@example.com` from `/docs`, or use the "Test SMTP configuration" box on the Notifications page in the UI.

### Telegram (optional, secondary channel)

1. Create a bot via [@BotFather](https://t.me/BotFather) and grab the bot token.
2. Get your chat ID (e.g. message [@userinfobot](https://t.me/userinfobot), or add the bot to a group and use its chat ID).
3. In `backend/.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456:ABC-your-token
   TELEGRAM_CHAT_ID=123456789
   ```

### Who gets notified

- **Caretaker** — notified immediately when an emergency is created (`Person.assigned_caretaker_id`)
- **Family** — notified after `ESCALATION_STEP1_DELAY_SECONDS` (default 60s, deliberately short for demoing — see below) if still unacknowledged (highest-priority `EmergencyContact` with an email on file)
- **Doctor** — notified after `ESCALATION_STEP2_DELAY_SECONDS` (default 120s) only if the emergency is still open **and** severity is CRITICAL (`Person.doctor_id`)

For a real deployment, raise these to realistic minute-scale values in `.env`; the short defaults exist so you can watch escalation actually happen during a live viva demo without waiting.

A background scheduler (APScheduler) checks all `OPEN` emergencies every `ESCALATION_CHECK_INTERVAL_SECONDS` (default 15s) and fires any step that's now due.

Acknowledging or resolving an emergency stops all further escalation automatically — the background scheduler only evaluates `OPEN` emergencies.

## 14. API Documentation

FastAPI generates live OpenAPI/Swagger docs at `/docs` and ReDoc at `/redoc` whenever the backend is running. Current endpoints:

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | none | Create a user account |
| POST | `/auth/login` | none | Get access + refresh tokens |
| POST | `/auth/refresh` | none (refresh token in body) | Rotate access + refresh tokens |
| GET | `/users/me` | required | Get the current user's profile |
| GET | `/users` | ADMIN only | List all users |
| POST | `/people` | ADMIN/CARETAKER | Create a monitored person + emergency contacts |
| GET | `/people` | required | List monitored people |
| POST | `/devices` | ADMIN/CARETAKER | Register a device for a person |
| GET | `/devices` | required | List devices |
| POST | `/sensors/{device_id}/reading` | required | Ingest one real sensor reading |
| POST | `/sensors/{device_id}/simulate` | required | Run a scenario (NORMAL/WALKING/FALL/FALL_HIGH_HEART_RATE/INACTIVITY_AFTER_FALL) through the real ingestion + detection pipeline |
| GET | `/sensors/{device_id}/history` | required | Recent sensor readings for a device |
| GET | `/emergencies` | required | List emergencies (optional `?status_filter=`) |
| GET | `/emergencies/{id}` | required | Emergency detail + full timeline |
| POST | `/emergencies/{id}/acknowledge` | CARETAKER/ADMIN | Acknowledge, stops escalation |
| POST | `/emergencies/{id}/resolve` | CARETAKER/ADMIN | Resolve |
| POST | `/emergencies/{id}/false-alarm` | CARETAKER/ADMIN | Mark false alarm |
| GET | `/notifications` | required | Notification log (optional `?emergency_id=`) |
| POST | `/notifications/test` | ADMIN only | Send a real test email via configured SMTP |
| POST | `/videos/upload` | required | Upload a video/image, run real CV analysis, auto-create an emergency if HIGH/CRITICAL |
| GET | `/videos` | required | List video/image analyses (optional `?person_id=`) |
| GET | `/videos/{id}` | required | Analysis detail |
| GET | `/videos/{id}/evidence/{evidence_id}` | required | Fetch a stored evidence file |
| GET | `/health` | none | Liveness check |

## 15. Limitations (current, Phase 4)

- Video/image processing runs synchronously inside the upload request — fine for a demo/viva, but a production version would move this to a background task/queue so the upload response returns instantly and the UI polls for completion (see `docs/architecture.md`)
- The accident and fire/smoke detectors are documented classical CV baselines (motion-spike analysis, HSV color heuristics), not trained models — see `docs/ai_models.md` for the full methodology and known false-positive/false-negative cases for each
- No object detection/tracking for accidents (e.g. YOLO-based vehicle counting) — the current approach is frame-to-frame motion analysis only; the original brief's YOLOv8n option remains a documented upgrade path, not yet implemented
- Dashboard shows real, computed stats but no charts/trend analysis yet — that's Phase 5
- The escalation policy is a plain Python structure, not yet a per-person configurable DB table
- No SMS channel — email and Telegram only, as scoped in the original brief
- `Base.metadata.create_all()` is still used for schema creation for fast iteration; switch to `alembic upgrade head` once the first real migration is generated, to avoid schema drift
- The fall-detection risk engine is a documented rule-based baseline, not a trained ML classifier — see `docs/ai_models.md`

## 16. Roadmap

- ~~**Phase 2:** Person/device management, software sensor simulator, fall-detection risk engine, Emergency Engine~~ ✅ done
- ~~**Phase 3:** Real email notifications, escalation scheduler, acknowledge/resolve/false-alarm, incident timeline~~ ✅ done
- ~~**Phase 4:** Video upload, traffic accident CV pipeline, fire/smoke CV pipeline, evidence storage~~ ✅ done
- **Phase 5 (next):** Analytics dashboard, location/maps, audit logs, full test coverage, deployment docs, polish

## 17. Academic / Safety Notice

GuardianAI is an academic prototype. It does not replace doctors, hospitals, certified medical devices, or emergency services. All detections are labeled as AI-assisted estimates ("Possible fall detected"), never medical certainty, and critical alerts will recommend contacting emergency services when the feature is built.

---

**Next step:** say "start Phase 5" to build the analytics dashboard, location/maps display, and audit logs.
