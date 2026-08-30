"""
GuardianAI — Standalone Software Sensor Simulator
====================================================

This is a REAL external client of the backend HTTP API — it does not import
any backend code and does not touch the database directly. It generates a
time-series of sensor readings and POSTs each one to
`/sensors/{device_id}/reading`, exactly as a real wearable's companion app
would. Whether an emergency is created is decided entirely by the backend's
fall-detection engine evaluating these values — this script has no opinion
about that and cannot force one.

This exists alongside the backend's built-in `/sensors/{id}/simulate`
endpoint (which runs the same scenario logic synchronously, server-side,
for convenience) to demonstrate that the simulator is a genuinely separate
piece of software, not a fake button wired straight to the database.

Usage (from the backend/ virtual environment, or any environment with
`requests` installed):

    python ml/simulator/sensor_simulator.py --login caretaker@example.com --password ... \\
        --device-id <device-uuid> --scenario FALL --duration 20

    python ml/simulator/sensor_simulator.py --list-people --login ... --password ...

Run with --help for all options.
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from dataclasses import dataclass

try:
    import requests
except ImportError:
    print("This script requires the 'requests' package: pip install requests", file=sys.stderr)
    sys.exit(1)

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
    """Same scenario logic as app/ai/fall_detection/scenarios.py, kept as an
    independent copy here so this script has zero dependency on the backend
    package — it only knows the HTTP contract, like any real client would.
    """
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario '{scenario}'. Must be one of {sorted(SCENARIOS)}")

    ticks = max(3, int(duration_seconds / tick_seconds))
    readings: list[SimulatedReading] = []
    inactivity = 0.0
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
                accel = _jitter(3.6, 0.4)
                orientation = "lying"
                movement = "none"
                inactivity = 0.0
            else:
                hr = _jitter(80, 6)
                accel = _jitter(0.2, 0.1)
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
                hr = _jitter(148, 10)
                accel = _jitter(0.2, 0.1)
                orientation = "lying"
                movement = "none"
                inactivity += tick_seconds

        else:  # INACTIVITY_AFTER_FALL
            if elapsed_after_baseline == 0:
                hr = _jitter(75, 5)
                accel = _jitter(2.6, 0.2)
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


def login(base_url: str, email: str, password: str) -> str:
    resp = requests.post(f"{base_url}/auth/login", json={"email": email, "password": password})
    resp.raise_for_status()
    return resp.json()["access_token"]


def list_people(base_url: str, token: str) -> None:
    resp = requests.get(f"{base_url}/people", headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    people = resp.json()
    if not people:
        print("No people found. Create one first via POST /people (see docs/api.md).")
        return
    print(f"{'ID':<38} {'Name':<20} Devices")
    for p in people:
        devices_resp = requests.get(f"{base_url}/devices", headers={"Authorization": f"Bearer {token}"})
        devices = [d for d in devices_resp.json() if d["person_id"] == p["id"]]
        device_summary = ", ".join(f"{d['device_name']} ({d['id'][:8]})" for d in devices) or "(none)"
        print(f"{p['id']:<38} {p['name']:<20} {device_summary}")


def run_simulation(
    base_url: str, token: str, device_id: str, scenario: str, duration: int, playback_delay: float
) -> None:
    """
    `duration` is SIMULATED seconds — it always maps 1 reading per simulated
    second (tick_seconds=1.0 fixed), matching exactly how the backend's own
    built-in /simulate endpoint generates data, so results are consistent
    between the two. `playback_delay` is a SEPARATE real-time pacing knob
    (how long this script sleeps between HTTP calls) purely for watching a
    live demo unfold — it has no effect on the simulated values themselves.
    """
    headers = {"Authorization": f"Bearer {token}"}
    sequence = generate_sequence(scenario, duration, tick_seconds=1.0)

    print(f"Software Sensor Simulator — device {device_id}, scenario {scenario}, {len(sequence)} readings")
    print("-" * 70)

    for i, reading in enumerate(sequence, start=1):
        payload = {
            "heart_rate": reading.heart_rate,
            "accel_x": reading.accel_x,
            "accel_y": reading.accel_y,
            "accel_z": reading.accel_z,
            "accel_magnitude": reading.accel_magnitude,
            "orientation": reading.orientation,
            "movement": reading.movement,
            "inactivity_duration": reading.inactivity_duration,
        }
        resp = requests.post(f"{base_url}/sensors/{device_id}/reading", json=payload, headers=headers)

        if resp.status_code != 201:
            print(f"[{i:02d}] ERROR {resp.status_code}: {resp.text}")
            break

        result = resp.json()
        flag = ""
        if result["emergency_created"]:
            flag = f"  <<< EMERGENCY CREATED ({result['emergency_id']})"
        print(
            f"[{i:02d}] hr={reading.heart_rate:>5.1f} accel={reading.accel_magnitude:>5.2f} "
            f"orientation={reading.orientation:<8} inactivity={reading.inactivity_duration:>5.1f}s  "
            f"-> {result['severity']:<9} conf={result['confidence']:.2f}{flag}"
        )

        if result["emergency_created"]:
            print("-" * 70)
            print("Emergency created — stopping simulation early (a real device would alert immediately).")
            return

        if playback_delay > 0:
            time.sleep(playback_delay)

    print("-" * 70)
    print("Simulation complete — no emergency threshold reached.")


def main() -> None:
    parser = argparse.ArgumentParser(description="GuardianAI standalone software sensor simulator")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--login", required=True, help="Account email")
    parser.add_argument("--password", required=True, help="Account password")
    parser.add_argument("--device-id", help="Target device UUID (see --list-people)")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="FALL")
    parser.add_argument(
        "--duration", type=int, default=20,
        help="Simulated duration in seconds (1 reading per simulated second, same as the backend's own generator)",
    )
    parser.add_argument(
        "--playback-delay", type=float, default=0.3,
        help="Real seconds to pause between HTTP calls, purely for watching the demo unfold live. "
             "Set to 0 to send as fast as possible. Does NOT affect the simulated values.",
    )
    parser.add_argument("--list-people", action="store_true", help="List people + device IDs and exit")

    args = parser.parse_args()

    try:
        token = login(args.base_url, args.login, args.password)
    except requests.exceptions.ConnectionError:
        print(f"Could not reach {args.base_url} — is the backend running?", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.HTTPError:
        print("Login failed — check --login/--password.", file=sys.stderr)
        sys.exit(1)

    if args.list_people:
        list_people(args.base_url, token)
        return

    if not args.device_id:
        print("--device-id is required unless --list-people is used.", file=sys.stderr)
        sys.exit(1)

    run_simulation(args.base_url, token, args.device_id, args.scenario, args.duration, args.playback_delay)


if __name__ == "__main__":
    main()
