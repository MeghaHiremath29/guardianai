"""
Emergency — the central record created ONLY by the Emergency Engine
(app/services/emergency_engine.py), never written directly by a detection
module. EmergencyTimeline gives a full audit trail of what happened when.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class EmergencyType(str, enum.Enum):
    FALL = "FALL"
    ABNORMAL_HEART_RATE = "ABNORMAL_HEART_RATE"
    TRAFFIC_ACCIDENT = "TRAFFIC_ACCIDENT"
    FIRE_SMOKE = "FIRE_SMOKE"
    GENERAL = "GENERAL"


class Severity(str, enum.Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EmergencyStatus(str, enum.Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    FALSE_ALARM = "FALSE_ALARM"


class EmergencySource(str, enum.Enum):
    SENSOR_SIMULATOR = "SENSOR_SIMULATOR"
    VIDEO_ACCIDENT = "VIDEO_ACCIDENT"
    VIDEO_FIRE = "VIDEO_FIRE"
    MANUAL = "MANUAL"


class Emergency(Base):
    __tablename__ = "emergencies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_type: Mapped[EmergencyType] = mapped_column(Enum(EmergencyType), nullable=False)
    # Nullable: fall/heart-rate emergencies always have a monitored Person,
    # but a traffic-accident or fire video may not be tied to one (e.g. a
    # general street/CCTV clip) — see Phase 4 video upload.
    person_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("people.id"), nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("devices.id"), nullable=True)

    source: Mapped[EmergencySource] = mapped_column(Enum(EmergencySource), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 - 1.0
    severity: Mapped[Severity] = mapped_column(Enum(Severity), nullable=False)
    status: Mapped[EmergencyStatus] = mapped_column(Enum(EmergencyStatus), default=EmergencyStatus.OPEN)

    # Comma-free JSON-encoded list of human-readable contributing signals,
    # e.g. ["sudden acceleration spike", "no movement after impact"]
    reasons: Mapped[str] = mapped_column(Text, default="[]")

    location_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    # How many escalation steps (see app/services/escalation.py policy) have
    # already fired for this emergency. 0 = only the initial notification
    # has gone out (or none yet). Stops incrementing once ACKNOWLEDGED/RESOLVED/FALSE_ALARM.
    escalation_step: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    timeline: Mapped[list["EmergencyTimeline"]] = relationship(
        back_populates="emergency", cascade="all, delete-orphan", order_by="EmergencyTimeline.timestamp"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="emergency", cascade="all, delete-orphan"
    )


class EmergencyTimeline(Base):
    __tablename__ = "emergency_timeline"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    emergency_id: Mapped[str] = mapped_column(String(36), ForeignKey("emergencies.id"), nullable=False)
    event_text: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    emergency: Mapped["Emergency"] = relationship(back_populates="timeline")
