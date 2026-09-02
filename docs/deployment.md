# Deployment

This project targets local development for a BE major project demo/viva.
This document sketches the real path to a deployed version, honestly
marked as **not built** — no Docker Compose file or hosting config exists
in this repo yet, so don't expect a one-command deploy.

## What would actually need to change

**Database:** swap `DATABASE_URL` in `.env` from the SQLite URL to a
Postgres connection string (`postgresql+psycopg2://user:pass@host:5432/db`).
The schema was written to avoid SQLite-only types, so this should work
without model changes — but it has not been tested against a real Postgres
instance as part of this project. You'd also want to switch from
`Base.metadata.create_all()` (used for fast local iteration) to
`alembic upgrade head`, since `create_all()` never alters existing tables
and silently drifts from the models over time (this exact problem — a
"no such column" error — is called out in the troubleshooting notes this
project's users have hit when upgrading between phases).

**File storage:** `UPLOAD_DIR`/`EVIDENCE_DIR` currently point at local
disk (`../data/uploads`, `../data/evidence`). In a real multi-instance
deployment these would move to object storage (S3-compatible), since local
disk doesn't survive a container restart or scale across replicas.

**Video/image processing:** currently synchronous inside the upload
request (see `docs/architecture.md`). For real traffic, this should move
to a background worker/queue (e.g. Celery + Redis, or FastAPI
`BackgroundTasks` at minimum) so uploads don't block on CPU-bound OpenCV
work.

**Secrets:** `SECRET_KEY`, SMTP credentials, and Telegram tokens must come
from a real secrets manager in production, not a committed `.env` file.

**CORS:** `FRONTEND_ORIGIN` currently allows exactly one origin
(`http://localhost:5173` by default) — update to the real deployed
frontend URL.

**Frontend build:** `npm run build` in `frontend/` produces a static
`dist/` folder that can be served by any static host (Nginx, Netlify,
Vercel, S3+CloudFront). It needs `VITE_API_BASE_URL` set to the deployed
backend's URL at build time.

## Not attempted in this project

Container images, a Compose/Kubernetes manifest, CI/CD, and a live hosted
instance are all out of scope for this academic prototype. Documenting the
path above without pretending it's been built or tested matches the
project's core rule: never claim something works when it hasn't actually
been verified.
