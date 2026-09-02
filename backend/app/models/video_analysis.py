"""
VideoAnalysis + Evidence models — Phase 4.

VideoAnalysis tracks the lifecycle of one uploaded video/image through the
CV pipeline: PENDING -> PROCESSING -> COMPLETED or FAILED. It never claims
a result before analysis has actually run, and FAILED records keep the
real error message rather than silently disappearing.

Evidence stores the file references generated for a given emergency (the
uploaded source file, plus an extracted evidence frame for videos). Only
what's needed for the incident record is kept, per the project's
data-minimization requirement.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class AnalysisType(str, enum.Enum):
    TRAFFIC_ACCIDENT = "TRAFFIC_ACCIDENT"
    FIRE_SMOKE = "FIRE_SMOKE"


class MediaType(str, enum.Enum):
    VIDEO = "VIDEO"
    IMAGE = "IMAGE"


class AnalysisStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class VideoAnalysis(Base):
    __tablename__ = "video_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    uploaded_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    person_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("people.id"), nullable=True)
    emergency_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("emergencies.id"), nullable=True)

    analysis_type: Mapped[AnalysisType] = mapped_column(Enum(AnalysisType), nullable=False)
    media_type: Mapped[MediaType] = mapped_column(Enum(MediaType), nullable=False)
    status: Mapped[AnalysisStatus] = mapped_column(Enum(AnalysisStatus), default=AnalysisStatus.PENDING)

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)

    # Manually configured location for this footage (see Person.latitude
    # docstring on why this is never claimed to be live GPS).
    location_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_label: Mapped[str | None] = mapped_column(String(255), nullable=True)

    detected: Mapped[bool | None] = mapped_column(nullable=True)  # None until analysis completes
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reasons: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    event_timestamp_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)  # for video

    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    evidence: Mapped[list["Evidence"]] = relationship(back_populates="video_analysis", cascade="all, delete-orphan")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    video_analysis_id: Mapped[str] = mapped_column(String(36), ForeignKey("video_analyses.id"), nullable=False)
    emergency_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("emergencies.id"), nullable=True)

    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "source_video" | "source_image" | "evidence_frame"
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    video_analysis: Mapped["VideoAnalysis"] = relationship(back_populates="evidence")
