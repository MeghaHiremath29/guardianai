from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class EmergencyContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    relation: str = Field(min_length=1, max_length=60)
    phone: str | None = None
    email: EmailStr | None = None
    priority_order: int = 1


class EmergencyContactOut(EmergencyContactCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    person_id: str


class PersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    age: int | None = Field(default=None, ge=0, le=130)
    address: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    medical_notes: str | None = None
    assigned_caretaker_id: str | None = None
    doctor_id: str | None = None
    emergency_contacts: list[EmergencyContactCreate] = []


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    age: int | None
    address: str | None
    latitude: float | None
    longitude: float | None
    medical_notes: str | None
    assigned_caretaker_id: str | None
    doctor_id: str | None
    created_by_id: str
    created_at: datetime
    emergency_contacts: list[EmergencyContactOut] = []
