from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.audit_log import AuditAction


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    action: AuditAction
    actor_id: str | None
    actor_email: str | None
    entity_type: str | None
    entity_id: str | None
    detail: str | None
    created_at: datetime
