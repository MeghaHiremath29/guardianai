"""
Unit tests for the fall-detection risk engine (app/ai/fall_detection/engine.py).
Pure function tests — no DB, no HTTP — matching the engine's design as a
side-effect-free scoring function.
"""
from app.ai.fall_detection.engine import SensorSnapshot, evaluate


def _snap(hr=70, accel=1.0, orientation="upright", inactivity=0.0) -> SensorSnapshot:
    return SensorSnapshot(
        heart_rate=hr, accel_magnitude=accel, orientation=orientation, inactivity_duration=inactivity
    )


def test_normal_activity_produces_no_signals():
    window = [_snap(accel=1.0, orientation="upright") for _ in range(5)]
    result = evaluate(window)
    assert result.severity == "NORMAL"
    assert result.reasons == []
    assert result.raw_score == 0


def test_single_reading_window_with_spike_only_is_not_yet_high():
    # A spike alone (no stillness afterward yet) shouldn't be CRITICAL —
    # matches "do not create a fake always-true detector".
    window = [_snap(accel=3.5, orientation="lying", inactivity=0.0)]
    result = evaluate(window)
    assert result.severity in ("WARNING", "HIGH")
    assert result.severity != "CRITICAL"
    assert "sudden acceleration spike" in result.reasons


def test_spike_followed_by_prolonged_stillness_escalates():
    window = [
        _snap(accel=3.5, orientation="lying", inactivity=0.0),
        _snap(accel=0.2, orientation="lying", inactivity=5.0),
        _snap(accel=0.2, orientation="lying", inactivity=10.0),
        _snap(accel=0.2, orientation="lying", inactivity=15.0),
    ]
    result = evaluate(window)
    assert result.severity in ("HIGH", "CRITICAL")
    assert result.event_type == "FALL"
    assert "sudden acceleration spike" in result.reasons
    assert "no movement after impact" in result.reasons


def test_spike_plus_stillness_plus_abnormal_heart_rate_is_critical():
    window = [
        _snap(hr=80, accel=3.8, orientation="lying", inactivity=0.0),
        _snap(hr=150, accel=0.2, orientation="lying", inactivity=10.0),
        _snap(hr=150, accel=0.2, orientation="lying", inactivity=15.0),
    ]
    result = evaluate(window)
    assert result.severity == "CRITICAL"
    assert result.confidence >= 0.9
    assert set(result.reasons) == {
        "sudden acceleration spike",
        "orientation change (lying/fallen position)",
        "no movement after impact",
        "abnormal heart rate",
    }


def test_abnormal_heart_rate_alone_is_classified_separately():
    window = [_snap(hr=160, accel=1.0, orientation="upright", inactivity=0.0)]
    result = evaluate(window)
    assert "abnormal heart rate" in result.reasons
    if result.severity != "NORMAL":
        assert result.event_type == "ABNORMAL_HEART_RATE"


def test_walking_style_activity_stays_normal():
    window = [_snap(hr=95, accel=1.3, orientation="upright", inactivity=0.0) for _ in range(10)]
    result = evaluate(window)
    assert result.severity == "NORMAL"


def test_evaluate_requires_non_empty_window():
    import pytest
    with pytest.raises(ValueError):
        evaluate([])


def test_confidence_is_bounded_between_zero_and_one():
    window = [_snap(hr=200, accel=10.0, orientation="lying", inactivity=100.0)]
    result = evaluate(window)
    assert 0.0 <= result.confidence <= 1.0
