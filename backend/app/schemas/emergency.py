import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.emergency import EmergencySource, EmergencyStatus, EmergencyType, Severity


class EmergencyTimelineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_text: str
    actor_id: str | None
    timestamp: datetime


class EmergencyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: EmergencyType
    person_id: str
    device_id: str | None
    source: EmergencySource
    confidence: float
    severity: Severity
    status: EmergencyStatus
    reasons: list[str]
    location_lat: float | None
    location_lng: float | None
    created_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None

    @field_validator("reasons", mode="before")
    @classmethod
    def parse_reasons(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v


class EmergencyDetailOut(EmergencyOut):
    timeline: list[EmergencyTimelineOut] = []
