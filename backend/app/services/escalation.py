"""
Escalation engine.

Policy is intentionally a plain Python structure (not a DB table yet) so
it's easy to read and reason about for the viva; a future phase could move
it into a per-user-configurable DB table without changing the scheduler
logic below.

Each step fires once escalation_step < step_number AND enough time has
elapsed since the emergency was created AND (for step 2) severity is
CRITICAL. Acknowledging or resolving an emergency stops further escalation
automatically, because the scheduler only looks at OPEN emergencies.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.emergency import Emergency, EmergencyStatus, EmergencyTimeline, Severity
from app.models.notification import RecipientRole
from app.models.person import Person
from app.services.notifications.service import notify_role

logger = logging.getLogger("guardianai.escalation")


@dataclass(frozen=True)
class EscalationStep:
    step_number: int
    delay_seconds: int
    role: RecipientRole
    critical_only: bool = False


# Step 0 (immediate caretaker notification) fires synchronously inside the
# Emergency Engine at creation time — see app/services/emergency_engine.py —
# so it isn't listed here. This policy covers steps 1+ handled by the
# background scheduler.
ESCALATION_POLICY: list[EscalationStep] = [
    EscalationStep(step_number=1, delay_seconds=settings.ESCALATION_STEP1_DELAY_SECONDS, role=RecipientRole.FAMILY),
    EscalationStep(
        step_number=2,
        delay_seconds=settings.ESCALATION_STEP2_DELAY_SECONDS,
        role=RecipientRole.DOCTOR,
        critical_only=True,
    ),
]


def run_escalation_check(db: Session) -> int:
    """Checks every OPEN emergency and fires any escalation steps that are
    now due. Returns the number of notifications sent this tick (for logging/tests)."""
    open_emergencies = db.query(Emergency).filter(Emergency.status == EmergencyStatus.OPEN).all()
    sent_count = 0

    for emergency in open_emergencies:
        # SQLite does not persist tz info, so a timestamp written as
        # tz-aware UTC can come back naive on read. Normalize before
        # subtracting so this works the same on SQLite and Postgres.
        created_at = emergency.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - created_at).total_seconds()

        for step in ESCALATION_POLICY:
            if emergency.escalation_step >= step.step_number:
                continue
            if elapsed < step.delay_seconds:
                continue
            if step.critical_only and emergency.severity != Severity.CRITICAL:
                # Not critical — this step is permanently skipped for this
                # emergency, but we still advance the counter so we don't
                # re-evaluate it every tick.
                emergency.escalation_step = step.step_number
                db.add(
                    EmergencyTimeline(
                        emergency_id=emergency.id,
                        event_text=(
                            f"Escalation step {step.step_number} skipped "
                            f"(severity is {emergency.severity}, not CRITICAL)."
                        ),
                    )
                )
                db.commit()
                continue

            person = db.query(Person).filter(Person.id == emergency.person_id).first()
            if not person:
                continue

            notification = notify_role(
                db, emergency=emergency, person=person, role=step.role, escalation_step=step.step_number
            )
            emergency.escalation_step = step.step_number
            db.add(
                EmergencyTimeline(
                    emergency_id=emergency.id,
                    event_text=(
                        f"Escalated to {step.role.value.title()} "
                        f"({notification.status.value.lower()}: "
                        f"{notification.recipient_name or 'no recipient on file'})."
                    ),
                )
            )
            db.commit()
            sent_count += 1
            logger.info(
                "escalation.step_fired emergency_id=%s step=%s role=%s status=%s",
                emergency.id, step.step_number, step.role.value, notification.status.value,
            )

    return sent_count
