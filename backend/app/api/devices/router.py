"""
Device management endpoints.
A "device" represents whichever process sends sensor readings for a person —
the built-in /sensors/{device_id}/simulate endpoint or the standalone
ml/simulator/sensor_simulator.py script. Both go through the same API.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.device import Device
from app.models.person import Person
from app.models.user import User, UserRole
from app.schemas.device import DeviceCreate, DeviceOut

router = APIRouter(prefix="/devices", tags=["devices"])
logger = logging.getLogger("guardianai.devices")


@router.post(
    "",
    response_model=DeviceOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.CARETAKER))],
)
def create_device(payload: DeviceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Device:
    person = db.query(Person).filter(Person.id == payload.person_id).first()
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")

    device = Device(
        device_name=payload.device_name,
        device_type=payload.device_type,
        person_id=payload.person_id,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    logger.info("devices.created device_id=%s person_id=%s by=%s", device.id, person.id, current_user.id)
    return device


@router.get("", response_model=list[DeviceOut])
def list_devices(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[Device]:
    return db.query(Device).order_by(Device.created_at.desc()).all()


@router.get("/{device_id}", response_model=DeviceOut)
def get_device(device_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> Device:
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device
