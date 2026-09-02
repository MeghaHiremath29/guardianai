"""
Notification channels. Each channel implements .send() and returns a
(success: bool, detail: str) tuple. Channels never pretend to succeed —
if they're not configured, they report that honestly rather than faking
a sent status. This mirrors the project's "no fake implementation" rule.
"""
import logging
import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage

import httpx

from app.core.config import settings

logger = logging.getLogger("guardianai.notifications")


class NotificationChannel(ABC):
    @abstractmethod
    def is_configured(self) -> bool:
        ...

    @abstractmethod
    def send(self, *, recipient: str, subject: str, body: str) -> tuple[bool, str]:
        """Returns (success, detail). detail holds an error message on failure,
        or a short confirmation note on success."""
        ...


class EmailChannel(NotificationChannel):
    def is_configured(self) -> bool:
        return bool(settings.SMTP_HOST and settings.SMTP_USERNAME and settings.SMTP_PASSWORD)

    def send(self, *, recipient: str, subject: str, body: str) -> tuple[bool, str]:
        if not self.is_configured():
            return False, "SMTP is not configured (see backend/.env — SMTP_HOST/USERNAME/PASSWORD)"

        if not recipient:
            return False, "No recipient email address on file"

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME
        msg["To"] = recipient
        msg.set_content(body)

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(msg)
            return True, f"Email sent to {recipient}"
        except Exception as exc:  # noqa: BLE001 - we want to log/report any SMTP failure, not crash
            logger.error("notifications.email_failed recipient=%s error=%s", recipient, str(exc))
            return False, f"SMTP send failed: {exc}"


class TelegramChannel(NotificationChannel):
    """Optional secondary channel. Sends to a single configured chat (not
    per-recipient) — suitable for an ops/monitoring group chat, as noted
    in .env.example."""

    def is_configured(self) -> bool:
        return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)

    def send(self, *, recipient: str, subject: str, body: str) -> tuple[bool, str]:
        if not self.is_configured():
            return False, "Telegram is not configured (see backend/.env — TELEGRAM_BOT_TOKEN/CHAT_ID)"

        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        text = f"*{subject}*\n\n{body}"
        try:
            resp = httpx.post(
                url,
                json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"},
                timeout=10,
            )
            if resp.status_code == 200:
                return True, "Telegram message sent"
            return False, f"Telegram API returned {resp.status_code}: {resp.text[:200]}"
        except Exception as exc:  # noqa: BLE001
            logger.error("notifications.telegram_failed error=%s", str(exc))
            return False, f"Telegram send failed: {exc}"


email_channel = EmailChannel()
telegram_channel = TelegramChannel()
