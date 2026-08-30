"""
Notification model.

Every attempt to notify someone about an emergency is logged here —
including attempts that failed or were skipped (e.g. no SMTP configured,
or no recipient on file for that role). This gives a full audit trail and
matches the project rule against silently pretending something succeeded.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class RecipientRole(str, enum.Enum):
    CARETAKER = "CARETAKER"
    FAMILY = "FAMILY"
    DOCTOR = "DOCTOR"


class NotificationChannelType(str, enum.Enum):
    EMAIL = "EMAIL"
    TELEGRAM = "TELEGRAM"


class NotificationStatus(str, enum.Enum):
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"  # e.g. channel not configured, or no recipient found


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    emergency_id: Mapped[str] = mapped_column(String(36), ForeignKey("emergencies.id"), nullable=False)

    recipient_role: Mapped[RecipientRole] = mapped_column(Enum(RecipientRole), nullable=False)
    recipient_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    recipient_address: Mapped[str | None] = mapped_column(String(255), nullable=True)  # email or chat id

    channel: Mapped[NotificationChannelType] = mapped_column(Enum(NotificationChannelType), nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(Enum(NotificationStatus), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)  # error message or skip reason

    escalation_step: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    emergency: Mapped["Emergency"] = relationship(back_populates="notifications")  # noqa: F821
