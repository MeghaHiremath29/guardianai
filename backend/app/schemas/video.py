from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.video_analysis import AnalysisStatus, AnalysisType, MediaType


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    file_path: str
    file_type: str
    description: str | None


class VideoAnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    person_id: str | None
    emergency_id: str | None
    analysis_type: AnalysisType
    media_type: MediaType
    status: AnalysisStatus
    original_filename: str
    location_lat: float | None
    location_lng: float | None
    location_label: str | None
    detected: bool | None
    confidence: float | None
    severity: str | None
    reasons: list[str]
    event_timestamp_seconds: float | None
    error_detail: str | None
    created_at: datetime
    processed_at: datetime | None
    evidence: list[EvidenceOut] = []
