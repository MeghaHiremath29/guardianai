"""
SensorReading — one time-series data point from a device. Every reading
that reaches the fall-detection engine passes through this table first;
nothing is injected directly into Emergency.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    device_id: Mapped[str] = mapped_column(String(36), ForeignKey("devices.id"), index=True, nullable=False)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    heart_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    accel_x: Mapped[float] = mapped_column(Float, default=0.0)
    accel_y: Mapped[float] = mapped_column(Float, default=0.0)
    accel_z: Mapped[float] = mapped_column(Float, default=0.0)
    accel_magnitude: Mapped[float] = mapped_column(Float, default=0.0)

    orientation: Mapped[str] = mapped_column(String(30), default="upright")
    movement: Mapped[str] = mapped_column(String(30), default="active")
    inactivity_duration: Mapped[float] = mapped_column(Float, default=0.0)  # seconds
