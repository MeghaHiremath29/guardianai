"""
Fire / smoke detection — risk engine.

Methodology (documented honestly — see docs/ai_models.md):

This is a classical HSV color-space heuristic, not a trained CNN. Real fire
pixels cluster in a fairly narrow orange/red/yellow hue band with high
saturation and brightness; smoke tends to be low-saturation gray/blue-gray
with moderate-to-low brightness and often occupies a growing region across
frames. app/ai/fire_detection/image_processor.py computes, per frame, the
fraction of pixels matching each color profile using OpenCV. This module
takes ONLY those numeric ratios — no OpenCV dependency — so it's
unit-testable with synthetic values.

For video, persistence across multiple sampled frames is required before
flagging anything, specifically to cut down on false positives from a
single orange/red object (e.g. a red car, an orange jacket) appearing in
one frame.

Known limitations (documented in docs/ai_models.md):
- Will false-positive on sunsets, orange/red clothing or objects, warm
  indoor lighting, brake lights
- Cannot distinguish a campfire/candle/stove (intentional, contained fire)
  from a hazardous fire
- Smoke detection is weaker than fire detection — gray/hazy scenes
  (fog, overcast sky, dust) can trigger it
- Not trained or validated against a labeled fire dataset (none was
  available) — thresholds are reasoned starting points, not tuned values
"""
from dataclasses import dataclass

# Tunable thresholds — see docs/ai_models.md for rationale.
FIRE_PIXEL_RATIO_THRESHOLD = 0.02      # >=2% of frame matching fire-color profile
SMOKE_PIXEL_RATIO_THRESHOLD = 0.15     # smoke needs a much larger area to be meaningful (grayish tones are common)
MIN_PERSISTENT_FRAMES = 3              # frames (of the sampled set) that must exceed threshold
PERSISTENCE_FRACTION = 0.4             # fraction of ALL sampled frames that must exceed threshold


@dataclass(frozen=True)
class FrameSignal:
    fire_ratio: float   # 0.0-1.0, fraction of pixels matching fire color profile
    smoke_ratio: float  # 0.0-1.0, fraction of pixels matching smoke color profile


@dataclass(frozen=True)
class FireDetectionResult:
    fire_detected: bool
    smoke_detected: bool
    confidence: float
    severity: str
    reasons: list[str]
    peak_fire_ratio: float
    peak_smoke_ratio: float
    persistent_frame_count: int


def evaluate(frame_signals: list[FrameSignal]) -> FireDetectionResult:
    """Evaluates a sequence of per-frame fire/smoke color-ratio signals.
    A single image is just a sequence of length 1 — persistence checks are
    skipped in that case (see below), since there's nothing to persist
    across."""
    if not frame_signals:
        return FireDetectionResult(
            fire_detected=False, smoke_detected=False, confidence=0.0, severity="NORMAL",
            reasons=["no frames to analyze"], peak_fire_ratio=0.0, peak_smoke_ratio=0.0,
            persistent_frame_count=0,
        )

    fire_hits = [s for s in frame_signals if s.fire_ratio >= FIRE_PIXEL_RATIO_THRESHOLD]
    smoke_hits = [s for s in frame_signals if s.smoke_ratio >= SMOKE_PIXEL_RATIO_THRESHOLD]

    peak_fire = max((s.fire_ratio for s in frame_signals), default=0.0)
    peak_smoke = max((s.smoke_ratio for s in frame_signals), default=0.0)

    is_single_frame = len(frame_signals) == 1

    if is_single_frame:
        fire_persistent = len(fire_hits) >= 1
        smoke_persistent = len(smoke_hits) >= 1
        persistent_count = len(fire_hits) + len(smoke_hits)
    else:
        required = max(MIN_PERSISTENT_FRAMES, int(len(frame_signals) * PERSISTENCE_FRACTION))
        fire_persistent = len(fire_hits) >= required
        smoke_persistent = len(smoke_hits) >= required
        persistent_count = max(len(fire_hits), len(smoke_hits))

    reasons: list[str] = []
    if fire_persistent:
        reasons.append(f"fire-colored region covering up to {round(peak_fire * 100)}% of frame")
        if not is_single_frame:
            reasons.append(f"present in {len(fire_hits)}/{len(frame_signals)} sampled frames")
    if smoke_persistent:
        reasons.append(f"smoke-like haze covering up to {round(peak_smoke * 100)}% of frame")
        if not is_single_frame:
            reasons.append(f"present in {len(smoke_hits)}/{len(frame_signals)} sampled frames")

    if not fire_persistent and not smoke_persistent:
        return FireDetectionResult(
            fire_detected=False, smoke_detected=False, confidence=0.0, severity="NORMAL",
            reasons=[], peak_fire_ratio=round(peak_fire, 3), peak_smoke_ratio=round(peak_smoke, 3),
            persistent_frame_count=0,
        )

    # Confidence: fire is stronger evidence than smoke alone (color-only
    # smoke detection is noisier — fog, overcast skies, dust all look
    # similar), but heavy, persistent smoke is still real risk and must be
    # able to reach HIGH/CRITICAL on its own, not just contribute a minor
    # boost to a fire score.
    fire_component = min(peak_fire / (FIRE_PIXEL_RATIO_THRESHOLD * 4), 1.0) if fire_persistent else 0.0
    smoke_component = min(peak_smoke / (SMOKE_PIXEL_RATIO_THRESHOLD * 2.5), 1.0) if smoke_persistent else 0.0

    if fire_persistent and smoke_persistent:
        confidence = round(min(0.6 * fire_component + 0.4 * smoke_component, 0.9), 2)
    elif fire_persistent:
        confidence = round(min(0.85 * fire_component, 0.9), 2)
    else:
        confidence = round(min(0.75 * smoke_component, 0.85), 2)

    if confidence >= 0.7:
        severity = "CRITICAL"
    elif confidence >= 0.5:
        severity = "HIGH"
    elif confidence >= 0.25:
        severity = "WARNING"
    else:
        severity = "NORMAL"

    return FireDetectionResult(
        fire_detected=fire_persistent,
        smoke_detected=smoke_persistent,
        confidence=confidence,
        severity=severity,
        reasons=reasons,
        peak_fire_ratio=round(peak_fire, 3),
        peak_smoke_ratio=round(peak_smoke, 3),
        persistent_frame_count=persistent_count,
    )
