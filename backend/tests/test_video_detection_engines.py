"""
Pure unit tests for the accident and fire/smoke detection engines.
These operate on plain numeric arrays (motion magnitudes, color ratios) —
exactly like test_fall_detection.py tests the sensor risk engine — so no
video file or OpenCV call is needed to validate the scoring logic itself.
"""
from app.ai.accident_detection.engine import evaluate as evaluate_accident
from app.ai.fire_detection.engine import FrameSignal, evaluate as evaluate_fire


# ---- Accident detection ----

def test_steady_driving_motion_is_not_an_accident():
    # Roughly constant motion magnitude — normal driving, no spike.
    magnitudes = [10.0, 11.0, 9.5, 10.5, 10.0, 11.0, 9.0, 10.0, 10.5, 10.0]
    result = evaluate_accident(magnitudes)
    assert result.accident_detected is False
    assert result.severity == "NORMAL"


def test_spike_that_never_settles_is_not_flagged():
    # A spike (e.g. hard acceleration) that stays elevated afterwards —
    # not accident-like, since there's no post-impact stillness.
    magnitudes = [10.0, 10.0, 10.0, 40.0, 38.0, 36.0, 35.0, 34.0, 33.0, 32.0]
    result = evaluate_accident(magnitudes)
    assert result.accident_detected is False


def test_spike_followed_by_stillness_is_flagged_as_accident():
    # Steady driving, sharp spike (impact), then near-total stillness (stopped).
    magnitudes = [10.0, 10.0, 10.0, 10.0, 45.0, 2.0, 1.5, 1.0, 1.5, 2.0]
    result = evaluate_accident(magnitudes)
    assert result.accident_detected is True
    assert result.severity in ("HIGH", "CRITICAL")
    assert result.confidence > 0.5
    assert "spike" in result.reasons[0]


def test_confidence_never_claims_near_certainty():
    magnitudes = [10.0, 10.0, 10.0, 10.0, 90.0, 0.1, 0.1, 0.1, 0.1, 0.1]
    result = evaluate_accident(magnitudes)
    assert result.confidence <= 0.97


def test_too_few_frames_returns_not_detected_not_a_crash():
    result = evaluate_accident([10.0, 12.0])
    assert result.accident_detected is False
    assert "not enough frames" in result.reasons[0]


def test_static_camera_with_no_baseline_motion_is_not_flagged():
    # All zeros — a static, empty scene. Should not divide-by-zero or false-positive.
    magnitudes = [0.0] * 10
    result = evaluate_accident(magnitudes)
    assert result.accident_detected is False


# ---- Fire / smoke detection ----

def test_no_fire_or_smoke_color_present():
    signals = [FrameSignal(fire_ratio=0.001, smoke_ratio=0.01) for _ in range(10)]
    result = evaluate_fire(signals)
    assert result.fire_detected is False
    assert result.smoke_detected is False
    assert result.severity == "NORMAL"


def test_single_frame_fire_flash_does_not_persist_in_video():
    # One frame has fire-colored pixels, rest are normal — should NOT persist
    # (guards against a single red car / orange jacket triggering a false alarm).
    signals = [FrameSignal(fire_ratio=0.001, smoke_ratio=0.0) for _ in range(9)]
    signals.insert(4, FrameSignal(fire_ratio=0.15, smoke_ratio=0.0))
    result = evaluate_fire(signals)
    assert result.fire_detected is False


def test_persistent_fire_color_across_frames_is_detected():
    signals = [FrameSignal(fire_ratio=0.10, smoke_ratio=0.02) for _ in range(10)]
    result = evaluate_fire(signals)
    assert result.fire_detected is True
    assert result.severity in ("WARNING", "HIGH", "CRITICAL")
    assert any("fire" in r for r in result.reasons)


def test_persistent_heavy_smoke_alone_can_reach_high_or_critical():
    signals = [FrameSignal(fire_ratio=0.0, smoke_ratio=0.5) for _ in range(10)]
    result = evaluate_fire(signals)
    assert result.smoke_detected is True
    assert result.fire_detected is False
    assert result.severity in ("HIGH", "CRITICAL")


def test_single_image_with_strong_fire_signal_is_detected():
    # Single image (length-1 list) — persistence check is skipped by design.
    signals = [FrameSignal(fire_ratio=0.12, smoke_ratio=0.0)]
    result = evaluate_fire(signals)
    assert result.fire_detected is True


def test_empty_signal_list_does_not_crash():
    result = evaluate_fire([])
    assert result.fire_detected is False
    assert result.confidence == 0.0
