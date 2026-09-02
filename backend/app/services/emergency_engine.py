"""
Emergency Engine — the single funnel for turning any detection result
(fall risk, accident CV, fire CV) into an actual Emergency record.

Design rule (from the project brief): detection modules NEVER write to the
Emergency table directly. They call `create_emergency()` (or the
`create_emergency_from_detection()` convenience wrapper used by the sensor
pipeline), which owns severity interpretation, deduplication, and the
initial timeline entry. This keeps business logic in one auditable place.
"""
import json
import logging

from sqlalchemy.orm import Session

from app.ai.fall_detection.engine import DetectionResult
from app.models.audit_log import AuditAction
from app.models.emergency import Emergency, EmergencySource, EmergencyStatus, EmergencyTimeline, EmergencyType
from app.models.notification import RecipientRole
from app.models.person import Person
from app.services.audit import log_action
from app.services.notifications.service import notify_role

logger = logging.getLogger("guardianai.emergency_engine")

# A NORMAL/WARNING-severity result does not create an emergency — only
# HIGH and CRITICAL do. WARNING is logged but left for future trend analysis
# (Phase 5 analytics), matching "do not create a fake always-true detector".
EMERGENCY_CREATING_SEVERITIES = {"HIGH", "CRITICAL"}

# If an OPEN emergency of the same type already exists within this scope
# (usually a person), treat new detections as reinforcing evidence
# (timeline entry) rather than spamming duplicate emergencies.
DEDUPLICATION_WINDOW_MINUTES = 10


def _find_recent_open_emergency(db: Session, *, dedup_scope_id: str, event_type: str) -> Emergency | None:
    return (
        db.query(Emergency)
        .filter(
            Emergency.person_id == dedup_scope_id,
            Emergency.event_type == event_type,
            Emergency.status.in_([EmergencyStatus.OPEN, EmergencyStatus.ACKNOWLEDGED]),
        )
        .order_by(Emergency.created_at.desc())
        .first()
    )


def create_emergency(
    db: Session,
    *,
    event_type: EmergencyType,
    confidence: float,
    severity: str,
    reasons: list[str],
    source: EmergencySource,
    person: Person | None = None,
    device_id: str | None = None,
    location_lat: float | None = None,
    location_lng: float | None = None,
) -> Emergency | None:
    """Generic entry point used by every detection module.

    Returns the created/reinforced Emergency, or None if severity is below
    the emergency-creating threshold. Deduplication only applies when a
    `person` is supplied (fall/heart-rate always have one; a general video
    upload with no monitored person always creates a fresh record, since
    there is no reliable scope to dedupe against).
    """
    if severity not in EMERGENCY_CREATING_SEVERITIES:
        logger.info(
            "emergency_engine.below_threshold event_type=%s severity=%s", event_type.value, severity
        )
        return None

    if person is not None:
        existing = _find_recent_open_emergency(db, dedup_scope_id=person.id, event_type=event_type.value)
        if existing:
            existing.confidence = max(existing.confidence, confidence)
            db.add(
                EmergencyTimeline(
                    emergency_id=existing.id,
                    event_text=(
                        f"Additional signal confirmed: {', '.join(reasons)} "
                        f"(confidence {int(confidence * 100)}%)"
                    ),
                )
            )
            db.commit()
            db.refresh(existing)
            logger.info("emergency_engine.reinforced emergency_id=%s", existing.id)
            return existing

    resolved_lat = location_lat if location_lat is not None else (person.latitude if person else None)
    resolved_lng = location_lng if location_lng is not None else (person.longitude if person else None)

    emergency = Emergency(
        event_type=event_type,
        person_id=person.id if person else None,
        device_id=device_id,
        source=source,
        confidence=confidence,
        severity=severity,
        status=EmergencyStatus.OPEN,
        reasons=json.dumps(reasons),
        location_lat=resolved_lat,
        location_lng=resolved_lng,
    )
    db.add(emergency)
    db.commit()
    db.refresh(emergency)

    reasons_text = ", ".join(reasons) if reasons else "no specific signals recorded"
    db.add(
        EmergencyTimeline(
            emergency_id=emergency.id,
            event_text=(
                f"Possible {event_type.value.replace('_', ' ').title()} detected "
                f"(confidence {int(confidence * 100)}%, severity {severity}). "
                f"Reasons: {reasons_text}."
            ),
        )
    )
    db.add(EmergencyTimeline(emergency_id=emergency.id, event_text="Emergency created."))
    db.commit()

    logger.info(
        "emergency_engine.created emergency_id=%s person_id=%s severity=%s type=%s source=%s",
        emergency.id, emergency.person_id, emergency.severity, emergency.event_type, source.value,
    )
    log_action(
        db, AuditAction.EMERGENCY_CREATED, entity_type="Emergency", entity_id=emergency.id,
        detail=f"{event_type.value} via {source.value}, severity {severity}",
    )

    # Step 0 of escalation: notify the caretaker immediately, but only if
    # there's a monitored person to notify about. A general video upload
    # with no linked person has no caretaker to reach — this is logged
    # honestly rather than silently skipped.
    if person is not None:
        notification = notify_role(
            db, emergency=emergency, person=person, role=RecipientRole.CARETAKER, escalation_step=0
        )
        db.add(
            EmergencyTimeline(
                emergency_id=emergency.id,
                event_text=(
                    f"Caretaker notified "
                    f"({notification.status.value.lower()}: {notification.recipient_name or 'no caretaker on file'})."
                ),
            )
        )
    else:
        db.add(
            EmergencyTimeline(
                emergency_id=emergency.id,
                event_text="No monitored person linked to this alert — no caretaker notification sent.",
            )
        )
    db.commit()

    return emergency


def create_emergency_from_detection(
    db: Session,
    *,
    detection: DetectionResult,
    person: Person,
    source: EmergencySource,
    device_id: str | None = None,
) -> Emergency | None:
    """Backward-compatible wrapper for the sensor/fall-detection pipeline."""
    event_type = EmergencyType.FALL if detection.event_type == "FALL" else EmergencyType.ABNORMAL_HEART_RATE
    return create_emergency(
        db,
        event_type=event_type,
        confidence=detection.confidence,
        severity=detection.severity,
        reasons=detection.reasons,
        source=source,
        person=person,
        device_id=device_id,
    )
