from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.device import DeviceStatus


class DeviceCreate(BaseModel):
    device_name: str = Field(min_length=1, max_length=120)
    device_type: str = "Software Sensor Simulator"
    person_id: str


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    device_name: str
    device_type: str
    person_id: str
    status: DeviceStatus
    battery_level: float
    last_seen: datetime | None
    created_at: datetime
