from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.notification import NotificationChannelType, NotificationStatus, RecipientRole


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    emergency_id: str
    recipient_role: RecipientRole
    recipient_name: str | None
    recipient_address: str | None
    channel: NotificationChannelType
    status: NotificationStatus
    detail: str | None
    escalation_step: int
    created_at: datetime
