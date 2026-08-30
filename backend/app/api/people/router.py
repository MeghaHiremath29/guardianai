"""
Person management endpoints. ADMIN and CARETAKER can create/manage people;
any authenticated user can read (family/doctor need visibility too — finer-
grained per-person authorization is a documented Phase 5 improvement).
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.person import EmergencyContact, Person
from app.models.user import User, UserRole
from app.schemas.person import PersonCreate, PersonOut

router = APIRouter(prefix="/people", tags=["people"])
logger = logging.getLogger("guardianai.people")


@router.post(
    "",
    response_model=PersonOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.CARETAKER))],
)
def create_person(
    payload: PersonCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Person:
    person = Person(
        name=payload.name,
        age=payload.age,
        address=payload.address,
        latitude=payload.latitude,
        longitude=payload.longitude,
        medical_notes=payload.medical_notes,
        assigned_caretaker_id=payload.assigned_caretaker_id or current_user.id,
        doctor_id=payload.doctor_id,
        created_by_id=current_user.id,
    )
    db.add(person)
    db.flush()  # get person.id before adding contacts

    for contact in payload.emergency_contacts:
        db.add(EmergencyContact(person_id=person.id, **contact.model_dump()))

    db.commit()
    db.refresh(person)
    logger.info("people.created person_id=%s by=%s", person.id, current_user.id)
    return person


@router.get("", response_model=list[PersonOut])
def list_people(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[Person]:
    return db.query(Person).options(joinedload(Person.emergency_contacts)).order_by(Person.created_at.desc()).all()


@router.get("/{person_id}", response_model=PersonOut)
def get_person(person_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> Person:
    person = (
        db.query(Person)
        .options(joinedload(Person.emergency_contacts))
        .filter(Person.id == person_id)
        .first()
    )
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    return person
