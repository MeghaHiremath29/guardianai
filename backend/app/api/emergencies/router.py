"""
Emergency read + response-action endpoints.

Acknowledge / resolve / false-alarm are the three actions a caretaker can
take on an OPEN or ACKNOWLEDGED emergency (see FEATURE 12 in the project
brief). Acknowledging/resolving/marking-false-alarm all move the emergency
out of the scheduler's OPEN-only escalation query, so escalation stops
automatically — no separate "cancel escalation" call is needed.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.emergency import Emergency, EmergencyStatus, EmergencyTimeline
from app.models.user import User, UserRole
from app.schemas.emergency import EmergencyDetailOut, EmergencyOut

router = APIRouter(prefix="/emergencies", tags=["emergencies"])

# Only these roles can act on an emergency. FAMILY/DOCTOR can view (see
# list/get below, which allow any authenticated user) but not change status,
# matching the brief: caretakers acknowledge/resolve; admins can too.
RESPONDER_ROLES = (UserRole.CARETAKER, UserRole.ADMIN)


@router.get("", response_model=list[EmergencyOut])
def list_emergencies(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Emergency]:
    query = db.query(Emergency)
    if status_filter:
        query = query.filter(Emergency.status == status_filter)
    return query.order_by(Emergency.created_at.desc()).all()


@router.get("/{emergency_id}", response_model=EmergencyDetailOut)
def get_emergency(emergency_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> Emergency:
    emergency = (
        db.query(Emergency)
        .options(joinedload(Emergency.timeline))
        .filter(Emergency.id == emergency_id)
        .first()
    )
    if not emergency:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emergency not found")
    return emergency


def _get_actionable_emergency(db: Session, emergency_id: str) -> Emergency:
    emergency = db.query(Emergency).filter(Emergency.id == emergency_id).first()
    if not emergency:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emergency not found")
    if emergency.status in (EmergencyStatus.RESOLVED, EmergencyStatus.FALSE_ALARM):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Emergency is already {emergency.status.value} and cannot be changed further",
        )
    return emergency


@router.post(
    "/{emergency_id}/acknowledge",
    response_model=EmergencyDetailOut,
    dependencies=[Depends(require_roles(*RESPONDER_ROLES))],
)
def acknowledge_emergency(
    emergency_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Emergency:
    emergency = _get_actionable_emergency(db, emergency_id)

    if emergency.status == EmergencyStatus.OPEN:
        emergency.status = EmergencyStatus.ACKNOWLEDGED
        emergency.acknowledged_at = datetime.now(timezone.utc)
        emergency.acknowledged_by_id = current_user.id
        db.add(
            EmergencyTimeline(
                emergency_id=emergency.id,
                event_text=f"Acknowledged by {current_user.full_name} ({current_user.role.value}).",
                actor_id=current_user.id,
            )
        )
        db.commit()
        db.refresh(emergency)

    return _reload_with_timeline(db, emergency.id)


@router.post(
    "/{emergency_id}/resolve",
    response_model=EmergencyDetailOut,
    dependencies=[Depends(require_roles(*RESPONDER_ROLES))],
)
def resolve_emergency(
    emergency_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Emergency:
    emergency = _get_actionable_emergency(db, emergency_id)

    emergency.status = EmergencyStatus.RESOLVED
    emergency.resolved_at = datetime.now(timezone.utc)
    emergency.resolved_by_id = current_user.id
    db.add(
        EmergencyTimeline(
            emergency_id=emergency.id,
            event_text=f"Resolved by {current_user.full_name} ({current_user.role.value}).",
            actor_id=current_user.id,
        )
    )
    db.commit()
    db.refresh(emergency)

    return _reload_with_timeline(db, emergency.id)


@router.post(
    "/{emergency_id}/false-alarm",
    response_model=EmergencyDetailOut,
    dependencies=[Depends(require_roles(*RESPONDER_ROLES))],
)
def mark_false_alarm(
    emergency_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Emergency:
    emergency = _get_actionable_emergency(db, emergency_id)

    emergency.status = EmergencyStatus.FALSE_ALARM
    emergency.resolved_at = datetime.now(timezone.utc)
    emergency.resolved_by_id = current_user.id
    db.add(
        EmergencyTimeline(
            emergency_id=emergency.id,
            event_text=f"Marked as false alarm by {current_user.full_name} ({current_user.role.value}).",
            actor_id=current_user.id,
        )
    )
    db.commit()
    db.refresh(emergency)

    return _reload_with_timeline(db, emergency.id)


def _reload_with_timeline(db: Session, emergency_id: str) -> Emergency:
    return (
        db.query(Emergency)
        .options(joinedload(Emergency.timeline))
        .filter(Emergency.id == emergency_id)
        .first()
    )
