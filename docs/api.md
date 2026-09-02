# API Documentation

Live, authoritative docs are served by FastAPI itself:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

This file tracks endpoints at a glance; see README.md section 14 for the
full, current table (updated through Phase 5).

## Phase 5 additions

`/analytics/summary`, `/analytics/trends`, and `/analytics/device-uptime`
are computed live from the database — no caching, no precomputed rollups
(see `docs/architecture.md` for the tradeoff reasoning). `/audit-logs` and
`/system/config` are ADMIN-only, matching the project brief's RBAC design
for admin-level system visibility.
