"""
Notification service — the single place that turns "notify the caretaker
about this emergency" into an actual email (and optionally Telegram) send,
with a Notification row logged for every attempt, success or failure.
"""
import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.emergency import Emergency
from app.models.notification import (
    Notification,
    NotificationChannelType,
    NotificationStatus,
    RecipientRole,
)
from app.models.person import Person
from app.models.user import User
from app.services.notifications.channels import email_channel, telegram_channel

logger = logging.getLogger("guardianai.notifications")


def _build_message(emergency: Emergency, person: Person, role: RecipientRole) -> tuple[str, str]:
    import json

    reasons = ", ".join(json.loads(emergency.reasons)) if emergency.reasons else "not specified"
    subject = f"GuardianAI Alert: {emergency.severity} — {emergency.event_type.replace('_', ' ').title()}"

    recommended_action = {
        "CARETAKER": "Please check on them now and acknowledge this alert in GuardianAI once you have.",
        "FAMILY": "The assigned caretaker has not yet acknowledged this alert. Please check in if you can.",
        "DOCTOR": "This is a critical, unacknowledged alert escalated to you as the person's doctor.",
    }[role.value]

    location = (
        f"{person.latitude}, {person.longitude}" if person.latitude is not None else "Not configured"
    )

    body = (
        "GuardianAI Emergency Alert\n"
        "===========================\n"
        f"Event: {emergency.event_type.replace('_', ' ').title()}\n"
        f"Person: {person.name}\n"
        f"Severity: {emergency.severity}\n"
        f"Confidence: {int(emergency.confidence * 100)}%\n"
        f"Time: {emergency.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        f"Location: {location}\n"
        f"Reason: {reasons}\n\n"
        f"Recommended action: {recommended_action}\n\n"
        "This is an AI-assisted risk estimate, not a medical diagnosis. "
        "If this looks like a genuine emergency, contact local emergency "
        "services in addition to using GuardianAI.\n"
    )
    return subject, body


def _resolve_recipient(db: Session, person: Person, role: RecipientRole) -> tuple[str | None, str | None]:
    """Returns (name, email) for the given role, or (None, None) if unset."""
    if role == RecipientRole.CARETAKER and person.assigned_caretaker_id:
        user = db.query(User).filter(User.id == person.assigned_caretaker_id).first()
        return (user.full_name, user.email) if user else (None, None)

    if role == RecipientRole.DOCTOR and person.doctor_id:
        user = db.query(User).filter(User.id == person.doctor_id).first()
        return (user.full_name, user.email) if user else (None, None)

    if role == RecipientRole.FAMILY:
        contact = sorted(person.emergency_contacts, key=lambda c: c.priority_order)[:1]
        if contact and contact[0].email:
            return contact[0].name, contact[0].email

    return None, None


def notify_role(
    db: Session,
    *,
    emergency: Emergency,
    person: Person,
    role: RecipientRole,
    escalation_step: int,
) -> Notification:
    """Sends (or honestly fails to send) a notification to the given role
    and always logs a Notification row. Returns that row."""
    name, address = _resolve_recipient(db, person, role)
    subject, body = _build_message(emergency, person, role)

    if not address:
        notification = Notification(
            emergency_id=emergency.id,
            recipient_role=role,
            recipient_name=name,
            recipient_address=None,
            channel=NotificationChannelType.EMAIL,
            status=NotificationStatus.SKIPPED,
            detail=f"No {role.value.lower()} configured for this person",
            escalation_step=escalation_step,
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        logger.info(
            "notifications.skipped emergency_id=%s role=%s reason=no_recipient", emergency.id, role.value
        )
        return notification

    success, detail = email_channel.send(recipient=address, subject=subject, body=body)
    notification = Notification(
        emergency_id=emergency.id,
        recipient_role=role,
        recipient_name=name,
        recipient_address=address,
        channel=NotificationChannelType.EMAIL,
        status=NotificationStatus.SENT if success else NotificationStatus.FAILED,
        detail=detail,
        escalation_step=escalation_step,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    logger.info(
        "notifications.%s emergency_id=%s role=%s recipient=%s",
        "sent" if success else "failed",
        emergency.id,
        role.value,
        address,
    )

    # Optional secondary channel — a single shared ops chat, not per-recipient.
    if telegram_channel.is_configured():
        tg_success, tg_detail = telegram_channel.send(recipient=settings.TELEGRAM_CHAT_ID, subject=subject, body=body)
        db.add(
            Notification(
                emergency_id=emergency.id,
                recipient_role=role,
                recipient_name="Ops Telegram Group",
                recipient_address=settings.TELEGRAM_CHAT_ID,
                channel=NotificationChannelType.TELEGRAM,
                status=NotificationStatus.SENT if tg_success else NotificationStatus.FAILED,
                detail=tg_detail,
                escalation_step=escalation_step,
            )
        )
        db.commit()

    return notification
