# Architecture

See README.md section 4 for the high-level diagram.

**Key principle:** the Emergency Engine (`app/services/emergency_engine.py`)
is the only path by which an `Emergency` row is created. Detection modules
— the fall risk engine, the accident CV pipeline, the fire/smoke CV
pipeline — never write to the Emergency table directly. Each calls
`create_emergency()` (or the sensor-specific `create_emergency_from_detection()`
wrapper), which owns severity thresholding, deduplication/reinforcement
against existing open emergencies, the initial timeline entry, and the
first (caretaker) notification. This keeps business logic in one
auditable place and makes it trivial to add a fourth detection source
later without touching escalation/notification code at all.

## Video/image analysis pipeline (Phase 4)

```
Upload (multipart) -> validate extension/size -> save to data/uploads/
    -> real OpenCV frame extraction (video_processor.py / image_processor.py)
    -> pure scoring engine (engine.py, no OpenCV dependency, independently
       unit-tested with synthetic numeric arrays)
    -> save an evidence frame to data/evidence/
    -> if HIGH/CRITICAL: Emergency Engine creates a real Emergency
    -> full result returned to the caller
```

Processing currently runs **synchronously inside the upload request** —
this keeps Phase 4 simple and means the person uploading gets the real
result immediately, with no polling needed. For longer videos or higher
concurrent load, the natural upgrade is to return `202 Accepted` with
`status: PROCESSING` immediately, hand the file off to a background task
(FastAPI `BackgroundTasks` or a proper queue like Celery/RQ), and have the
frontend poll `GET /videos/{id}` until `status` becomes `COMPLETED` or
`FAILED`. The `VideoAnalysis.status` field already models this lifecycle
(`PENDING → PROCESSING → COMPLETED/FAILED`), so this upgrade doesn't
require a schema change — only moving the `try/except` block in
`app/api/videos/router.py` into a background task.

## Real-time dashboard updates

The frontend currently polls (`GET /emergencies` every 5s on the Live
Emergencies page). The natural upgrade path is Server-Sent Events: an
`/emergencies/stream` endpoint that pushes a message whenever the
Emergency Engine creates or updates a record, replacing the `setInterval`
poll with an `EventSource` subscription. Not implemented, since polling is
reliable and sufficient for the current scale.
