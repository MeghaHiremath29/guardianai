"""
Scenario generator for the software sensor simulator.

Produces a realistic time-series of sensor readings for a named scenario.
Values are deterministic-with-jitter, not random-always-true detections —
whether an emergency fires depends entirely on the rule-based engine in
engine.py evaluating the generated values, exactly as it would evaluate
real sensor data.

Used by: app/api/sensors/router.py (POST /sensors/{device_id}/simulate).
The standalone ml/simulator/sensor_simulator.py script has its own copy of
this logic so it can run outside the backend package as a true external
client of the HTTP API — see that file's module docstring.
"""
import random
from dataclasses import dataclass

SCENARIOS = {"NORMAL", "WALKING", "FALL", "FALL_HIGH_HEART_RATE", "INACTIVITY_AFTER_FALL"}


@dataclass
class SimulatedReading:
    heart_rate: float
    accel_x: float
    accel_y: float
    accel_z: float
    accel_magnitude: float
    orientation: str
    movement: str
    inactivity_duration: float


def _jitter(base: float, spread: float) -> float:
    return round(base + random.uniform(-spread, spread), 2)


def generate_sequence(scenario: str, duration_seconds: int, tick_seconds: float = 1.0) -> list[SimulatedReading]:
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario '{scenario}'. Must be one of {sorted(SCENARIOS)}")

    ticks = max(3, int(duration_seconds / tick_seconds))
    readings: list[SimulatedReading] = []
    inactivity = 0.0

    # Every scenario spends its first ~30% of ticks in a normal baseline,
    # so the demo clearly shows "before" vs "after" in the sensor monitor.
    baseline_ticks = max(2, int(ticks * 0.3))

    for i in range(ticks):
        elapsed_after_baseline = i - baseline_ticks

        if scenario == "NORMAL" or i < baseline_ticks:
            hr = _jitter(68, 6)
            accel = _jitter(1.0, 0.15)
            orientation = "upright"
            movement = "active" if i % 4 != 0 else "idle"
            inactivity = 0.0 if movement == "active" else min(inactivity + tick_seconds, 5.0)

        elif scenario == "WALKING":
            hr = _jitter(92, 8)
            accel = _jitter(1.25, 0.3)
            orientation = "upright"
            movement = "active"
            inactivity = 0.0

        elif scenario == "FALL":
            if elapsed_after_baseline == 0:
                hr = _jitter(78, 5)
                accel = _jitter(3.6, 0.4)  # impact spike
                orientation = "lying"
                movement = "none"
                inactivity = 0.0
            else:
                hr = _jitter(80, 6)
                accel = _jitter(0.2, 0.1)  # still, post-impact
                orientation = "lying"
                movement = "none"
                inactivity += tick_seconds

        elif scenario == "FALL_HIGH_HEART_RATE":
            if elapsed_after_baseline == 0:
                hr = _jitter(80, 5)
                accel = _jitter(3.8, 0.4)
                orientation = "lying"
                movement = "none"
                inactivity = 0.0
            else:
                hr = _jitter(148, 10)  # stress response after impact
                accel = _jitter(0.2, 0.1)
                orientation = "lying"
                movement = "none"
                inactivity += tick_seconds

        else:  # INACTIVITY_AFTER_FALL — modest spike, severity builds via prolonged stillness
            if elapsed_after_baseline == 0:
                hr = _jitter(75, 5)
                accel = _jitter(2.6, 0.2)  # right at the spike threshold
                orientation = "lying"
                movement = "none"
                inactivity = 0.0
            else:
                hr = _jitter(76, 6)
                accel = _jitter(0.15, 0.1)
                orientation = "lying"
                movement = "none"
                inactivity += tick_seconds

        magnitude = max(0.0, accel)
        readings.append(
            SimulatedReading(
                heart_rate=round(hr, 1),
                accel_x=_jitter(0, magnitude * 0.3),
                accel_y=_jitter(0, magnitude * 0.3),
                accel_z=round(magnitude, 2),
                accel_magnitude=round(magnitude, 2),
                orientation=orientation,
                movement=movement,
                inactivity_duration=round(inactivity, 1),
            )
        )

    return readings
