"""
Person model — the individual being monitored (e.g. an elderly relative).
Keeps only fields needed for emergency response, per the project's
privacy-minimization requirement — no unnecessary sensitive data.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Person(Base):
    __tablename__ = "people"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Manually configured location — see docs/architecture.md. Never claimed
    # to be live GPS; used for display and for tagging emergencies.
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    medical_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    assigned_caretaker_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    doctor_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    emergency_contacts: Mapped[list["EmergencyContact"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    devices: Mapped[list["Device"]] = relationship(back_populates="person")


class EmergencyContact(Base):
    __tablename__ = "emergency_contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    person_id: Mapped[str] = mapped_column(String(36), ForeignKey("people.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    relation: Mapped[str] = mapped_column(String(60), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    priority_order: Mapped[int] = mapped_column(Integer, default=1)

    person: Mapped["Person"] = relationship(back_populates="emergency_contacts")
