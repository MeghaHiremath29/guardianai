from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SensorReadingCreate(BaseModel):
    heart_rate: float | None = Field(default=None, ge=0, le=300)
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 0.0
    accel_magnitude: float = Field(ge=0)
    orientation: str = "upright"
    movement: str = "active"
    inactivity_duration: float = Field(default=0.0, ge=0)


class SensorReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    device_id: str
    timestamp: datetime
    heart_rate: float | None
    accel_x: float
    accel_y: float
    accel_z: float
    accel_magnitude: float
    orientation: str
    movement: str
    inactivity_duration: float


class SimulateStartRequest(BaseModel):
    scenario: str = Field(
        description="One of: NORMAL, WALKING, FALL, FALL_HIGH_HEART_RATE, INACTIVITY_AFTER_FALL"
    )
    duration_seconds: int = Field(default=20, ge=3, le=120)


class DetectionResultOut(BaseModel):
    """What the fall-detection engine returned for the most recent reading window."""

    event_type: str
    confidence: float
    severity: str
    reasons: list[str]
    emergency_created: bool
    emergency_id: str | None = None
