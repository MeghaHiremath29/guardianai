"""
Traffic accident detection — risk engine.

Methodology (documented honestly, no invented ML model — see
docs/ai_models.md):

This is a classical computer-vision baseline, not a trained object detector.
It works on a per-frame "motion magnitude" signal (mean absolute pixel
difference between consecutive frames, computed by
app/ai/accident_detection/video_processor.py using OpenCV) and looks for the
same kind of pattern the fall-detection engine looks for in accelerometer
data: a sharp spike (or short burst of spikes — a real collision is rarely
a single clean frame), followed within a bounded lookahead window by a
sustained drop to near-stillness. In traffic footage that pattern
corresponds to normal driving motion (steady, moderate motion) being
interrupted by a collision and then a sudden stop.

This function takes ONLY a list of numeric motion magnitudes (one per
sampled frame) — it has no OpenCV dependency, so it can be unit-tested with
synthetic arrays exactly like fall_detection/engine.py is.

Known limitations (see docs/ai_models.md for the full list):
- Cannot distinguish "sudden hard braking" from "collision"
- Cannot distinguish "camera shake / cut" from "collision"
- No object tracking — it doesn't know how many vehicles are in frame, only
  that pixel motion changed sharply
- Threshold-based, not learned — thresholds are configurable, not tuned
  against a labeled accident dataset (none was available)
"""
from dataclasses import dataclass

# Tunable thresholds — see docs/ai_models.md for rationale. These are
# starting points, not values validated against a labeled dataset.
SPIKE_MULTIPLIER = 2.5       # a frame must exceed baseline * this factor to count as a spike
STILLNESS_RATIO = 0.35       # a settled window must drop below baseline * this factor
MIN_BASELINE_FRAMES = 3      # frames needed before the spike to establish a baseline
MIN_POST_FRAMES = 2          # consecutive frames needed to confirm a "settled" stillness window
MAX_SETTLE_LOOKAHEAD = 8     # how many frames after the spike we're willing to search for stillness


@dataclass(frozen=True)
class AccidentDetectionResult:
    accident_detected: bool
    confidence: float  # 0.0 - 1.0, an AI-assisted estimate, not a certainty
    severity: str       # NORMAL | WARNING | HIGH | CRITICAL
    reasons: list[str]
    spike_frame_index: int | None
    raw_baseline: float
    raw_spike: float


def _find_settled_window(magnitudes: list[float], start: int, baseline: float) -> tuple[float, int] | None:
    """Searches for the first run of MIN_POST_FRAMES consecutive frames,
    starting no earlier than `start`, whose average is below the stillness
    threshold. Returns (window_average, frames_after_spike) or None."""
    n = len(magnitudes)
    limit = min(start + MAX_SETTLE_LOOKAHEAD, n - MIN_POST_FRAMES)
    for offset in range(start, limit + 1):
        window = magnitudes[offset:offset + MIN_POST_FRAMES]
        if len(window) < MIN_POST_FRAMES:
            break
        avg = sum(window) / len(window)
        if avg <= baseline * STILLNESS_RATIO:
            return avg, offset - start
    return None


def evaluate(motion_magnitudes: list[float]) -> AccidentDetectionResult:
    """Evaluates a full sequence of per-frame motion magnitudes.

    Scans every candidate spike frame (after an initial baseline window)
    and picks the one with the strongest spike+eventual-stillness pattern.
    """
    n = len(motion_magnitudes)
    if n < MIN_BASELINE_FRAMES + 1 + MIN_POST_FRAMES:
        return AccidentDetectionResult(
            accident_detected=False,
            confidence=0.0,
            severity="NORMAL",
            reasons=["not enough frames to analyze"],
            spike_frame_index=None,
            raw_baseline=0.0,
            raw_spike=0.0,
        )

    best_score = 0.0
    best_index: int | None = None
    best_baseline = 0.0
    best_spike = 0.0

    for i in range(MIN_BASELINE_FRAMES, n - MIN_POST_FRAMES):
        baseline_window = motion_magnitudes[max(0, i - MIN_BASELINE_FRAMES):i]
        baseline = sum(baseline_window) / len(baseline_window)
        spike = motion_magnitudes[i]

        if baseline <= 1e-6:
            continue  # no meaningful baseline motion (e.g. static camera, empty scene)

        if spike < baseline * SPIKE_MULTIPLIER:
            continue  # not a spike relative to recent driving motion

        settled = _find_settled_window(motion_magnitudes, i + 1, baseline)
        if settled is None:
            continue  # spike never settles within the lookahead window — not accident-like

        poststill, frames_to_settle = settled

        spike_strength = min((spike / baseline) / SPIKE_MULTIPLIER, 2.0)
        stillness_strength = 1.0 - min(poststill / (baseline * STILLNESS_RATIO + 1e-6), 1.0)
        # Settling fast (impact then stop) is stronger evidence than a slow fade.
        promptness = 1.0 - (frames_to_settle / MAX_SETTLE_LOOKAHEAD)
        score = 0.45 * spike_strength + 0.35 * max(stillness_strength, 0.0) + 0.20 * max(promptness, 0.0)

        if score > best_score:
            best_score = score
            best_index = i
            best_baseline = baseline
            best_spike = spike

    if best_index is None:
        return AccidentDetectionResult(
            accident_detected=False,
            confidence=0.0,
            severity="NORMAL",
            reasons=[],
            spike_frame_index=None,
            raw_baseline=0.0,
            raw_spike=0.0,
        )

    confidence = round(min(best_score / 1.7, 0.97), 2)  # cap — never claim near-certainty
    reasons = [
        "sudden sharp motion spike relative to preceding baseline",
        "motion settled to near-stillness shortly after the spike",
    ]

    if confidence >= 0.75:
        severity = "CRITICAL"
    elif confidence >= 0.55:
        severity = "HIGH"
    elif confidence >= 0.35:
        severity = "WARNING"
    else:
        severity = "NORMAL"

    return AccidentDetectionResult(
        accident_detected=severity in ("HIGH", "CRITICAL"),
        confidence=confidence,
        severity=severity,
        reasons=reasons,
        spike_frame_index=best_index,
        raw_baseline=round(best_baseline, 2),
        raw_spike=round(best_spike, 2),
    )
