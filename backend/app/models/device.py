"""
Device model. In this software-only version, a "device" is virtual — it
represents whichever process (the built-in simulate endpoint, or the
standalone ml_sim/sensor_simulator.py script) is sending sensor readings
for a given person. last_seen and battery_level are updated on every
incoming reading, exactly as a real watch integration would.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class DeviceStatus(str, enum.Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    device_name: Mapped[str] = mapped_column(String(120), nullable=False)
    device_type: Mapped[str] = mapped_column(String(60), default="Software Sensor Simulator")
    person_id: Mapped[str] = mapped_column(String(36), ForeignKey("people.id"), nullable=False)

    status: Mapped[DeviceStatus] = mapped_column(Enum(DeviceStatus), default=DeviceStatus.OFFLINE)
    battery_level: Mapped[float] = mapped_column(Float, default=100.0)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    person: Mapped["Person"] = relationship(back_populates="devices")
