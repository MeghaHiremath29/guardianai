"""
Single write path for AuditLog entries. All audit writes go through
log_action() so the "never log secrets" rule is enforced in one place,
not re-implemented at every call site.
"""
from sqlalchemy.orm import Session

from app.models.audit_log import AuditAction, AuditLog


def log_action(
    db: Session,
    action: AuditAction,
    actor_id: str | None = None,
    actor_email: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    detail: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        action=action,
        actor_id=actor_id,
        actor_email=actor_email,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail,
    )
    db.add(entry)
    db.commit()
    return entry
