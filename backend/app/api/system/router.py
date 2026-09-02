"""
Read-only system configuration — Phase 5.

Genuinely read-only by design: values come straight from the running
process's settings (loaded from .env). There is no write endpoint here
because thresholds/escalation timings are not yet a runtime-configurable,
per-user DB table (see the brief's "configure thresholds" ADMIN feature —
this is the honestly-documented first step toward it, not the full thing).
Changing behavior today means editing backend/.env and restarting.
"""
from fastapi import APIRouter, Depends

from app.ai.fall_detection import engine as fall_engine
from app.api.deps import require_roles
from app.core.config import settings
from app.models.user import UserRole

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/config", dependencies=[Depends(require_roles(UserRole.ADMIN))])
def get_system_config() -> dict:
    return {
        "environment": settings.ENVIRONMENT,
        "fall_detection": {
            # These are read directly from the engine module's constants
            # (app/ai/fall_detection/engine.py) — not from .env, since
            # they're not yet a runtime-configurable setting. Shown here
            # so an admin can see the real, currently-active values rather
            # than guessing from the docs.
            "acceleration_spike_score": fall_engine.ACCEL_SPIKE_SCORE,
            "orientation_change_score": fall_engine.ORIENTATION_CHANGE_SCORE,
            "inactivity_max_score": fall_engine.INACTIVITY_MAX_SCORE,
            "abnormal_heart_rate_score": fall_engine.HEART_RATE_SCORE,
            "critical_threshold": fall_engine.SEVERITY_CRITICAL,
            "high_threshold": fall_engine.SEVERITY_HIGH,
            "warning_threshold": fall_engine.SEVERITY_WARNING,
        },
        "escalation": {
            "step1_delay_seconds": settings.ESCALATION_STEP1_DELAY_SECONDS,
            "step2_delay_seconds": settings.ESCALATION_STEP2_DELAY_SECONDS,
            "check_interval_seconds": settings.ESCALATION_CHECK_INTERVAL_SECONDS,
        },
        "uploads": {
            "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
        },
        "notifications": {
            "smtp_configured": bool(settings.SMTP_HOST and settings.SMTP_USERNAME),
            "telegram_configured": bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID),
        },
        "editable_note": (
            "These values are read from backend/.env at startup. To change them, "
            "edit .env and restart the backend — there is no live-edit API yet "
            "(see docs/roadmap notes on per-user configurable thresholds)."
        ),
    }
