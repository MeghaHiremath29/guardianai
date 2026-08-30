"""
Background scheduler for the escalation check. Uses APScheduler's
BackgroundScheduler (thread-based) rather than an async job so it can use
the same synchronous SQLAlchemy session pattern as the rest of the app.
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.escalation import run_escalation_check

logger = logging.getLogger("guardianai.scheduler")

scheduler = BackgroundScheduler()


def _escalation_tick() -> None:
    db = SessionLocal()
    try:
        sent = run_escalation_check(db)
        if sent:
            logger.info("scheduler.escalation_tick notifications_sent=%s", sent)
    except Exception as exc:  # noqa: BLE001 - a scheduler job must never crash the loop
        logger.error("scheduler.escalation_tick_failed error=%s", str(exc))
    finally:
        db.close()


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        _escalation_tick,
        "interval",
        seconds=settings.ESCALATION_CHECK_INTERVAL_SECONDS,
        id="escalation_check",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("scheduler.started interval_seconds=%s", settings.ESCALATION_CHECK_INTERVAL_SECONDS)


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("scheduler.stopped")
