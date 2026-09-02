"""
Analytics endpoints — Phase 5.

Every number here is computed directly from real rows in the database at
request time. Nothing is cached, mocked, or precomputed with placeholder
data — if there's no data yet, counts are honestly 0 and averages are null,
not invented.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.device import Device, DeviceStatus
from app.models.emergency import Emergency, EmergencyStatus
from app.models.user import User
from app.schemas.analytics import (
    DeviceUptimeItem,
    SeverityBreakdownItem,
    SummaryOut,
    TrendPoint,
    TrendsOut,
    TypeBreakdownItem,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _aware(dt: datetime) -> datetime:
    """SQLite can return naive datetimes even for tz-aware columns
    (see docs/architecture.md for the same fix applied in escalation.py)."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _avg_seconds(pairs: list[tuple[datetime, datetime]]) -> float | None:
    if not pairs:
        return None
    total = sum((_aware(b) - _aware(a)).total_seconds() for a, b in pairs)
    return round(total / len(pairs), 1)


@router.get("/summary", response_model=SummaryOut)
def get_summary(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> SummaryOut:
    emergencies = db.query(Emergency).all()
    devices = db.query(Device).all()

    status_counts = Counter(e.status for e in emergencies)
    severity_counts = Counter(e.severity for e in emergencies)

    ack_pairs = [(e.created_at, e.acknowledged_at) for e in emergencies if e.acknowledged_at]
    resolve_pairs = [(e.created_at, e.resolved_at) for e in emergencies if e.resolved_at]

    closed = status_counts[EmergencyStatus.RESOLVED] + status_counts[EmergencyStatus.FALSE_ALARM]
    false_alarm_rate = (
        round(status_counts[EmergencyStatus.FALSE_ALARM] / closed, 3) if closed > 0 else 0.0
    )

    return SummaryOut(
        total_emergencies=len(emergencies),
        open_count=status_counts[EmergencyStatus.OPEN],
        acknowledged_count=status_counts[EmergencyStatus.ACKNOWLEDGED],
        resolved_count=status_counts[EmergencyStatus.RESOLVED],
        false_alarm_count=status_counts[EmergencyStatus.FALSE_ALARM],
        critical_count=severity_counts["CRITICAL"],
        high_count=severity_counts["HIGH"],
        warning_count=severity_counts["WARNING"],
        false_alarm_rate=false_alarm_rate,
        avg_acknowledgement_seconds=_avg_seconds(ack_pairs),
        avg_response_seconds=_avg_seconds(resolve_pairs),
        devices_online=sum(1 for d in devices if d.status == DeviceStatus.ONLINE),
        devices_total=len(devices),
    )


@router.get("/trends", response_model=TrendsOut)
def get_trends(
    days: int = 14, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> TrendsOut:
    emergencies = db.query(Emergency).all()

    type_counts = Counter(e.event_type.value for e in emergencies)
    severity_counts = Counter(e.severity.value for e in emergencies)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    daily = Counter()
    for e in emergencies:
        created = _aware(e.created_at)
        if created >= cutoff:
            daily[created.date().isoformat()] += 1

    # Fill in every day in the window, even ones with zero emergencies,
    # so the frontend chart doesn't have gaps that look like missing data.
    daily_counts = []
    for i in range(days - 1, -1, -1):
        day = (datetime.now(timezone.utc) - timedelta(days=i)).date().isoformat()
        daily_counts.append(TrendPoint(date=day, count=daily.get(day, 0)))

    return TrendsOut(
        by_type=[TypeBreakdownItem(event_type=k, count=v) for k, v in sorted(type_counts.items())],
        by_severity=[SeverityBreakdownItem(severity=k, count=v) for k, v in sorted(severity_counts.items())],
        daily_counts=daily_counts,
    )


@router.get("/device-uptime", response_model=list[DeviceUptimeItem])
def get_device_uptime(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[DeviceUptimeItem]:
    devices = db.query(Device).order_by(Device.device_name).all()
    return [
        DeviceUptimeItem(
            device_id=d.id,
            device_name=d.device_name,
            status=d.status.value,
            last_seen=d.last_seen.isoformat() if d.last_seen else None,
            battery_level=d.battery_level,
        )
        for d in devices
    ]
