"""
Sensor endpoints — the entry point for both real device data (future) and
the software sensor simulator.

Every reading, however it arrives, goes through the same pipeline:
    store reading -> update device status -> run fall-risk engine
    -> (if HIGH/CRITICAL) hand off to the Emergency Engine

No shortcut exists that creates an Emergency without a stored SensorReading
and a real evaluate() call — see app/ai/fall_detection/engine.py.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.fall_detection.engine import WINDOW_SIZE, DetectionResult, SensorSnapshot, evaluate
from app.ai.fall_detection.scenarios import SCENARIOS, generate_sequence
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.device import Device, DeviceStatus
from app.models.emergency import EmergencySource
from app.models.person import Person
from app.models.sensor_reading import SensorReading
from app.models.user import User
from app.schemas.sensor import DetectionResultOut, SensorReadingCreate, SensorReadingOut, SimulateStartRequest
from app.services.emergency_engine import create_emergency_from_detection

router = APIRouter(prefix="/sensors", tags=["sensors"])
logger = logging.getLogger("guardianai.sensors")


def _get_device_or_404(db: Session, device_id: str) -> Device:
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


def _ingest_reading(db: Session, device: Device, payload: SensorReadingCreate) -> tuple[SensorReading, DetectionResult, object | None]:
    """Shared pipeline: store reading, update device, run risk engine, maybe create emergency."""
    reading = SensorReading(
        device_id=device.id,
        heart_rate=payload.heart_rate,
        accel_x=payload.accel_x,
        accel_y=payload.accel_y,
        accel_z=payload.accel_z,
        accel_magnitude=payload.accel_magnitude,
        orientation=payload.orientation,
        movement=payload.movement,
        inactivity_duration=payload.inactivity_duration,
    )
    db.add(reading)

    device.last_seen = datetime.now(timezone.utc)
    device.status = DeviceStatus.ONLINE
    db.commit()
    db.refresh(reading)

    # Build a rolling window (oldest -> newest) so the engine can correlate
    # an earlier impact spike with the stillness that follows it, instead
    # of judging each reading in isolation. See engine.py's module docstring.
    recent = (
        db.query(SensorReading)
        .filter(SensorReading.device_id == device.id)
        .order_by(SensorReading.timestamp.desc())
        .limit(WINDOW_SIZE)
        .all()
    )
    recent = list(reversed(recent))  # oldest -> newest
    window = [
        SensorSnapshot(
            heart_rate=r.heart_rate,
            accel_magnitude=r.accel_magnitude,
            orientation=r.orientation,
            inactivity_duration=r.inactivity_duration,
        )
        for r in recent
    ]
    detection = evaluate(window)

    emergency = None
    if detection.severity in ("HIGH", "CRITICAL"):
        person = db.query(Person).filter(Person.id == device.person_id).first()
        if person:
            emergency = create_emergency_from_detection(
                db,
                detection=detection,
                person=person,
                source=EmergencySource.SENSOR_SIMULATOR,
                device_id=device.id,
            )

    return reading, detection, emergency


@router.post("/{device_id}/reading", response_model=DetectionResultOut, status_code=status.HTTP_201_CREATED)
def submit_reading(
    device_id: str,
    payload: SensorReadingCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DetectionResultOut:
    device = _get_device_or_404(db, device_id)
    _, detection, emergency = _ingest_reading(db, device, payload)

    logger.info(
        "sensors.reading device_id=%s severity=%s score=%s emergency_created=%s",
        device_id, detection.severity, detection.raw_score, bool(emergency),
    )

    return DetectionResultOut(
        event_type=detection.event_type,
        confidence=detection.confidence,
        severity=detection.severity,
        reasons=detection.reasons,
        emergency_created=emergency is not None,
        emergency_id=emergency.id if emergency else None,
    )


@router.get("/{device_id}/latest", response_model=SensorReadingOut)
def get_latest_reading(device_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> SensorReading:
    _get_device_or_404(db, device_id)
    reading = (
        db.query(SensorReading)
        .filter(SensorReading.device_id == device_id)
        .order_by(SensorReading.timestamp.desc())
        .first()
    )
    if not reading:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No readings yet for this device")
    return reading


@router.get("/{device_id}/history", response_model=list[SensorReadingOut])
def get_reading_history(
    device_id: str,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[SensorReading]:
    _get_device_or_404(db, device_id)
    limit = max(1, min(limit, 500))
    readings = (
        db.query(SensorReading)
        .filter(SensorReading.device_id == device_id)
        .order_by(SensorReading.timestamp.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(readings))


@router.post("/{device_id}/simulate", response_model=DetectionResultOut)
def run_simulation(
    device_id: str,
    payload: SimulateStartRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DetectionResultOut:
    """
    Synchronously generates a realistic reading sequence for the requested
    scenario, feeding each reading through the exact same pipeline a real
    device POST would use. Stops early and returns immediately the moment
    an emergency is created — a real system would not wait out the full
    window once it's already confident something is wrong.
    """
    if payload.scenario not in SCENARIOS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown scenario. Must be one of {sorted(SCENARIOS)}",
        )

    device = _get_device_or_404(db, device_id)
    sequence = generate_sequence(payload.scenario, payload.duration_seconds)

    last_detection: DetectionResult | None = None
    last_emergency = None

    for sim_reading in sequence:
        reading_payload = SensorReadingCreate(
            heart_rate=sim_reading.heart_rate,
            accel_x=sim_reading.accel_x,
            accel_y=sim_reading.accel_y,
            accel_z=sim_reading.accel_z,
            accel_magnitude=sim_reading.accel_magnitude,
            orientation=sim_reading.orientation,
            movement=sim_reading.movement,
            inactivity_duration=sim_reading.inactivity_duration,
        )
        _, last_detection, last_emergency = _ingest_reading(db, device, reading_payload)

        if last_emergency is not None:
            break  # alert immediately, don't wait out the rest of the window

    logger.info(
        "sensors.simulate_complete device_id=%s scenario=%s final_severity=%s emergency_created=%s",
        device_id, payload.scenario, last_detection.severity if last_detection else None, bool(last_emergency),
    )

    assert last_detection is not None  # sequence always has >= 3 readings
    return DetectionResultOut(
        event_type=last_detection.event_type,
        confidence=last_detection.confidence,
        severity=last_detection.severity,
        reasons=last_detection.reasons,
        emergency_created=last_emergency is not None,
        emergency_id=last_emergency.id if last_emergency else None,
    )
