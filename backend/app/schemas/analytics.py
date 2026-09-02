from pydantic import BaseModel


class SummaryOut(BaseModel):
    total_emergencies: int
    open_count: int
    acknowledged_count: int
    resolved_count: int
    false_alarm_count: int
    critical_count: int
    high_count: int
    warning_count: int
    false_alarm_rate: float  # false_alarm / (resolved + false_alarm), 0.0 if none closed yet
    avg_acknowledgement_seconds: float | None
    avg_response_seconds: float | None  # created -> resolved
    devices_online: int
    devices_total: int


class TypeBreakdownItem(BaseModel):
    event_type: str
    count: int


class SeverityBreakdownItem(BaseModel):
    severity: str
    count: int


class TrendPoint(BaseModel):
    date: str  # YYYY-MM-DD
    count: int


class TrendsOut(BaseModel):
    by_type: list[TypeBreakdownItem]
    by_severity: list[SeverityBreakdownItem]
    daily_counts: list[TrendPoint]  # last N days


class DeviceUptimeItem(BaseModel):
    device_id: str
    device_name: str
    status: str
    last_seen: str | None
    battery_level: float
