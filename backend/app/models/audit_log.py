"""
AuditLog — a record of security-relevant and data-changing actions across
the system: logins, registrations, emergency status changes, video
uploads, and admin actions. This is separate from EmergencyTimeline (which
narrates one incident's story) — AuditLog is the system-wide security/
compliance trail an admin can review.

Never logs passwords, tokens, or other secrets — see log_action() in
app/services/audit.py for the single write path, which enforces this.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class AuditAction(str, enum.Enum):
    USER_REGISTERED = "USER_REGISTERED"
    USER_LOGIN = "USER_LOGIN"
    USER_LOGIN_FAILED = "USER_LOGIN_FAILED"
    PERSON_CREATED = "PERSON_CREATED"
    DEVICE_CREATED = "DEVICE_CREATED"
    EMERGENCY_CREATED = "EMERGENCY_CREATED"
    EMERGENCY_ACKNOWLEDGED = "EMERGENCY_ACKNOWLEDGED"
    EMERGENCY_RESOLVED = "EMERGENCY_RESOLVED"
    EMERGENCY_FALSE_ALARM = "EMERGENCY_FALSE_ALARM"
    VIDEO_UPLOADED = "VIDEO_UPLOADED"
    NOTIFICATION_TEST_SENT = "NOTIFICATION_TEST_SENT"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction), nullable=False, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)  # denormalized for readability even if user is later deleted
    entity_type: Mapped[str | None] = mapped_column(String(60), nullable=True)  # e.g. "Emergency", "Person"
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)  # short human-readable context, never secrets
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
