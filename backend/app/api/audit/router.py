"""
Audit log endpoints — Phase 5. Admin-only, since this is a system-wide
security/compliance trail (see app/services/audit.py for the write path
and app/models/audit_log.py for what gets logged).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.audit_log import AuditAction, AuditLog
from app.models.user import UserRole
from app.schemas.audit_log import AuditLogOut

router = APIRouter(prefix="/audit-logs", tags=["audit"], dependencies=[Depends(require_roles(UserRole.ADMIN))])


@router.get("", response_model=list[AuditLogOut])
def list_audit_logs(
    action: AuditAction | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> list[AuditLog]:
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    return query.order_by(AuditLog.created_at.desc()).limit(min(limit, 500)).all()
