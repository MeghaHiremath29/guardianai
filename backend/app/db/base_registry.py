"""
Import every ORM model here so Base.metadata is fully populated.
This module must be imported (for its side effects) before calling
Base.metadata.create_all(...) or running Alembic autogenerate.
Add new model modules here as they're created in later phases.
"""
from app.db.base import Base  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.person import Person, EmergencyContact  # noqa: F401
from app.models.device import Device  # noqa: F401
from app.models.sensor_reading import SensorReading  # noqa: F401
from app.models.emergency import Emergency, EmergencyTimeline  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.video_analysis import VideoAnalysis, Evidence  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
