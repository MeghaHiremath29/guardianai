"""
Fall / health-emergency risk engine — Phase 2.

This is a RULE-BASED scoring model, not a trained classifier. It is an
explainable first version, matching the project's "simplest reliable
architecture first" principle. A classical ML classifier (e.g. RandomForest
trained on labeled simulator sequences) can be added later as a documented
comparison — see docs/ai_models.md.

IMPORTANT: this is a software risk ESTIMATE, not a medically validated
diagnosis. It is surfaced to the user as "Possible fall detected", never
as a certainty.

WINDOWED EVALUATION (important design note):
A real fall is a pattern across time — impact, THEN stillness — not a
single instantaneous reading. Evaluating one reading in isolation misses
this: by the time inactivity has built up enough to matter, the impact
spike that caused it is long past and no longer in that single reading.
So `evaluate()` takes a short rolling WINDOW of recent readings for the
device (oldest → newest) and:
    - looks for an acceleration spike ANYWHERE in the window
    - reads orientation, inactivity, and heart rate from the LATEST reading
This mirrors how a real wearable's fall algorithm correlates an impact
event with what happens in the following seconds.

Signals and weights (all configurable below):
    - acceleration spike anywhere in the window   -> +30
    - current orientation is lying/fallen         -> +20
    - current post-impact inactivity              -> +30 (scales with duration)
    - current heart rate outside normal range     -> +20

Thresholds:
    - score >= 90                    -> CRITICAL
    - score >= 70                    -> HIGH
    - score >= 40                    -> WARNING
    - score <  40                    -> NORMAL (no emergency)

A reading only reaches this engine after being stored via the sensor API —
detection never bypasses the data pipeline.
"""
from dataclasses import dataclass, field

# ---- Configurable thresholds (kept in one place, per project requirement) ----

ACCEL_SPIKE_THRESHOLD_G = 2.5          # accel_magnitude above this counts as a spike
ACCEL_SPIKE_SCORE = 30

ORIENTATION_CHANGE_SCORE = 20
FALL_ORIENTATIONS = {"lying", "fallen"}

# Inactivity starts contributing quickly and saturates within ~15s, so a
# demo scenario (default 20s) has time to show WARNING -> HIGH -> CRITICAL
# escalate visibly, without the score sitting flat while nothing changes.
INACTIVITY_THRESHOLD_SECONDS = 5.0
INACTIVITY_MAX_SCORE = 30
INACTIVITY_SATURATION_SECONDS = 15.0

HEART_RATE_LOW = 45
HEART_RATE_HIGH = 130
HEART_RATE_SCORE = 20

SEVERITY_CRITICAL = 90
SEVERITY_HIGH = 70
SEVERITY_WARNING = 40

# How much history the engine looks back over to find a spike. The sensor
# API supplies this many of the most recent readings for the device. Sized
# with margin above the default 20-second demo scenario duration so the
# impact reading doesn't scroll out of the window before inactivity has
# had time to build up and score.
WINDOW_SIZE = 40


@dataclass
class SensorSnapshot:
    """The minimal signal set the engine needs from one SensorReading row."""
    heart_rate: float | None
    accel_magnitude: float
    orientation: str
    inactivity_duration: float


@dataclass
class DetectionResult:
    event_type: str  # "FALL" | "ABNORMAL_HEART_RATE" | "NORMAL"
    confidence: float  # 0.0 - 1.0
    severity: str  # "NORMAL" | "WARNING" | "HIGH" | "CRITICAL"
    reasons: list[str] = field(default_factory=list)
    raw_score: int = 0


def evaluate(window: list[SensorSnapshot]) -> DetectionResult:
    """Pure function: a window of sensor signals in, risk assessment out.
    No I/O, no DB — this makes the engine trivially unit-testable
    (see tests/test_fall_detection.py). `window` must be non-empty and
    ordered oldest -> newest; the last element is treated as "now".
    """
    if not window:
        raise ValueError("evaluate() requires at least one reading")

    current = window[-1]
    score = 0
    reasons: list[str] = []

    spike_in_window = any(s.accel_magnitude >= ACCEL_SPIKE_THRESHOLD_G for s in window)
    if spike_in_window:
        score += ACCEL_SPIKE_SCORE
        reasons.append("sudden acceleration spike")

    if current.orientation in FALL_ORIENTATIONS:
        score += ORIENTATION_CHANGE_SCORE
        reasons.append("orientation change (lying/fallen position)")

    if current.inactivity_duration >= INACTIVITY_THRESHOLD_SECONDS:
        span = INACTIVITY_SATURATION_SECONDS - INACTIVITY_THRESHOLD_SECONDS
        progress = (
            min(1.0, (current.inactivity_duration - INACTIVITY_THRESHOLD_SECONDS) / span)
            if span > 0 else 1.0
        )
        inactivity_score = round(INACTIVITY_MAX_SCORE * progress)
        score += inactivity_score
        reasons.append("no movement after impact" if spike_in_window else "prolonged inactivity")

    abnormal_hr = current.heart_rate is not None and (
        current.heart_rate < HEART_RATE_LOW or current.heart_rate > HEART_RATE_HIGH
    )
    if abnormal_hr:
        score += HEART_RATE_SCORE
        reasons.append("abnormal heart rate")

    score = min(100, score)
    confidence = round(score / 100, 2)

    if score >= SEVERITY_CRITICAL:
        severity = "CRITICAL"
    elif score >= SEVERITY_HIGH:
        severity = "HIGH"
    elif score >= SEVERITY_WARNING:
        severity = "WARNING"
    else:
        severity = "NORMAL"

    if severity == "NORMAL":
        event_type = "NORMAL"
    elif "abnormal heart rate" in reasons and len(reasons) == 1:
        event_type = "ABNORMAL_HEART_RATE"
    else:
        event_type = "FALL"

    return DetectionResult(
        event_type=event_type,
        confidence=confidence,
        severity=severity,
        reasons=reasons,
        raw_score=score,
    )
