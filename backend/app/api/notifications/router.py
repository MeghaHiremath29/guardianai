"""
Notification read endpoints, plus a manual "send a test notification" route
so a caretaker/admin can verify SMTP is configured correctly without
waiting for a real emergency.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.notification import Notification
from app.models.user import User, UserRole
from app.schemas.notification import NotificationOut
from app.services.notifications.channels import email_channel

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    emergency_id: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Notification]:
    query = db.query(Notification)
    if emergency_id:
        query = query.filter(Notification.emergency_id == emergency_id)
    return query.order_by(Notification.created_at.desc()).limit(200).all()


@router.post(
    "/test",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def send_test_notification(
    recipient_email: str,
    db: Session = Depends(get_db),
) -> dict:
    """Sends a real test email through the configured SMTP channel, so you
    can verify credentials before relying on it during a live demo."""
    success, detail = email_channel.send(
        recipient=recipient_email,
        subject="GuardianAI Test Notification",
        body=(
            "This is a test notification from GuardianAI.\n\n"
            "If you received this, your SMTP configuration in backend/.env is working."
        ),
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
    return {"status": "sent", "detail": detail}
