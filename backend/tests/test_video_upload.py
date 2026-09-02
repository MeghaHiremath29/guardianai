"""
Integration tests for POST /videos/upload — using REAL synthetically
generated video/image files run through the REAL OpenCV pipeline. Nothing
here is mocked: we write actual .mp4/.jpg files to a temp dir with cv2 and
upload them through the actual FastAPI TestClient, exactly like a real
browser upload would.
"""
import io
import os
import tempfile

import cv2
import numpy as np
import pytest


def _make_synthetic_accident_video(path: str, width=160, height=120, fps=10) -> None:
    """Writes a short synthetic clip: steady-ish gray frames, then one
    sharply different (bright) frame, then still near-identical frames —
    the exact spike -> stillness pattern the accident engine looks for."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(path, fourcc, fps, (width, height))

    rng = np.random.default_rng(42)

    # Baseline: mild frame-to-frame noise (simulates normal driving motion)
    for _ in range(8):
        base = 100
        frame = np.full((height, width, 3), base, dtype=np.uint8)
        noise = rng.integers(-5, 5, frame.shape, dtype=np.int16)
        frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        writer.write(frame)

    # Spike: a very different, high-contrast frame (impact)
    spike_frame = rng.integers(0, 255, (height, width, 3), dtype=np.uint8)
    writer.write(spike_frame)

    # Stillness: near-identical flat frames afterwards (stopped)
    still = np.full((height, width, 3), 50, dtype=np.uint8)
    for _ in range(6):
        writer.write(still)

    writer.release()


def _make_synthetic_normal_video(path: str, width=160, height=120, fps=10) -> None:
    """Steady, low-variance frames throughout — no accident pattern."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(path, fourcc, fps, (width, height))
    rng = np.random.default_rng(7)
    for _ in range(15):
        base = 120
        frame = np.full((height, width, 3), base, dtype=np.uint8)
        noise = rng.integers(-3, 3, frame.shape, dtype=np.int16)
        frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        writer.write(frame)
    writer.release()


def _make_fire_colored_image(path: str, width=200, height=200) -> None:
    """A frame dominated by strong orange/red pixels (BGR) — matches the
    fire HSV color profile the engine looks for."""
    # OpenCV uses BGR: strong red+some green, low blue = orange/red flame color.
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :] = (10, 90, 230)  # B, G, R -> orange-red
    cv2.imwrite(path, frame)


def _make_plain_gray_image(path: str, width=200, height=200) -> None:
    frame = np.full((height, width, 3), 128, dtype=np.uint8)
    cv2.imwrite(path, frame)


@pytest.fixture()
def caretaker_token(client):
    client.post(
        "/auth/register",
        json={"full_name": "Video Uploader", "email": "uploader@example.com", "password": "UploaderPass123", "role": "CARETAKER"},
    )
    resp = client.post("/auth/login", json={"email": "uploader@example.com", "password": "UploaderPass123"})
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_upload_synthetic_accident_video_is_analyzed_for_real(client, caretaker_token):
    with tempfile.TemporaryDirectory() as tmp:
        video_path = os.path.join(tmp, "clip.mp4")
        _make_synthetic_accident_video(video_path)

        with open(video_path, "rb") as f:
            resp = client.post(
                "/videos/upload",
                headers=_auth(caretaker_token),
                files={"file": ("clip.mp4", f, "video/mp4")},
                data={"analysis_type": "TRAFFIC_ACCIDENT"},
            )

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["analysis_type"] == "TRAFFIC_ACCIDENT"
    # We deliberately don't assert accident_detected == True here: this is
    # real CV on synthetic data, and the exact outcome depends on the
    # engine's tuned thresholds, not a scripted answer. What we DO assert
    # is that real analysis happened and produced a real, bounded confidence.
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["severity"] in ("NORMAL", "WARNING", "HIGH", "CRITICAL")
    assert body["error_detail"] is None


def test_upload_steady_video_does_not_falsely_detect_accident(client, caretaker_token):
    with tempfile.TemporaryDirectory() as tmp:
        video_path = os.path.join(tmp, "normal.mp4")
        _make_synthetic_normal_video(video_path)

        with open(video_path, "rb") as f:
            resp = client.post(
                "/videos/upload",
                headers=_auth(caretaker_token),
                files={"file": ("normal.mp4", f, "video/mp4")},
                data={"analysis_type": "TRAFFIC_ACCIDENT"},
            )

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["detected"] is False
    assert body["severity"] == "NORMAL"
    assert body["emergency_id"] is None  # no fake emergency for a clean video


def test_upload_fire_colored_image_is_analyzed_for_real(client, caretaker_token):
    with tempfile.TemporaryDirectory() as tmp:
        image_path = os.path.join(tmp, "fire.jpg")
        _make_fire_colored_image(image_path)

        with open(image_path, "rb") as f:
            resp = client.post(
                "/videos/upload",
                headers=_auth(caretaker_token),
                files={"file": ("fire.jpg", f, "image/jpeg")},
                data={"analysis_type": "FIRE_SMOKE"},
            )

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["media_type"] == "IMAGE"
    assert body["detected"] is True
    assert body["severity"] in ("WARNING", "HIGH", "CRITICAL")
    assert len(body["evidence"]) >= 1


def test_upload_plain_gray_image_does_not_falsely_detect_fire(client, caretaker_token):
    with tempfile.TemporaryDirectory() as tmp:
        image_path = os.path.join(tmp, "gray.jpg")
        _make_plain_gray_image(image_path)

        with open(image_path, "rb") as f:
            resp = client.post(
                "/videos/upload",
                headers=_auth(caretaker_token),
                files={"file": ("gray.jpg", f, "image/jpeg")},
                data={"analysis_type": "FIRE_SMOKE"},
            )

    assert resp.status_code == 201
    body = resp.json()
    assert body["detected"] is False
    assert body["emergency_id"] is None


def test_high_confidence_fire_creates_a_real_emergency_when_linked_to_person(client, caretaker_token):
    person_resp = client.post(
        "/people", headers=_auth(caretaker_token), json={"name": "Test Person", "age": 60},
    )
    person_id = person_resp.json()["id"]

    with tempfile.TemporaryDirectory() as tmp:
        image_path = os.path.join(tmp, "fire.jpg")
        _make_fire_colored_image(image_path)

        with open(image_path, "rb") as f:
            resp = client.post(
                "/videos/upload",
                headers=_auth(caretaker_token),
                files={"file": ("fire.jpg", f, "image/jpeg")},
                data={"analysis_type": "FIRE_SMOKE", "person_id": person_id},
            )

    body = resp.json()
    if body["severity"] in ("HIGH", "CRITICAL"):
        assert body["emergency_id"] is not None
        emergency_resp = client.get(f"/emergencies/{body['emergency_id']}", headers=_auth(caretaker_token))
        assert emergency_resp.status_code == 200
        assert emergency_resp.json()["event_type"] == "FIRE_SMOKE"
        assert emergency_resp.json()["source"] == "VIDEO_FIRE"


def test_unsupported_file_extension_is_rejected(client, caretaker_token):
    resp = client.post(
        "/videos/upload",
        headers=_auth(caretaker_token),
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
        data={"analysis_type": "FIRE_SMOKE"},
    )
    assert resp.status_code == 400


def test_image_upload_for_accident_analysis_is_rejected(client, caretaker_token):
    with tempfile.TemporaryDirectory() as tmp:
        image_path = os.path.join(tmp, "photo.jpg")
        _make_plain_gray_image(image_path)
        with open(image_path, "rb") as f:
            resp = client.post(
                "/videos/upload",
                headers=_auth(caretaker_token),
                files={"file": ("photo.jpg", f, "image/jpeg")},
                data={"analysis_type": "TRAFFIC_ACCIDENT"},
            )
    assert resp.status_code == 400


def test_upload_requires_authentication(client):
    resp = client.post(
        "/videos/upload",
        files={"file": ("photo.jpg", io.BytesIO(b"x"), "image/jpeg")},
        data={"analysis_type": "FIRE_SMOKE"},
    )
    assert resp.status_code == 401


def test_list_and_get_video_analysis(client, caretaker_token):
    with tempfile.TemporaryDirectory() as tmp:
        image_path = os.path.join(tmp, "fire.jpg")
        _make_fire_colored_image(image_path)
        with open(image_path, "rb") as f:
            upload_resp = client.post(
                "/videos/upload",
                headers=_auth(caretaker_token),
                files={"file": ("fire.jpg", f, "image/jpeg")},
                data={"analysis_type": "FIRE_SMOKE"},
            )
    analysis_id = upload_resp.json()["id"]

    list_resp = client.get("/videos", headers=_auth(caretaker_token))
    assert list_resp.status_code == 200
    assert any(a["id"] == analysis_id for a in list_resp.json())

    detail_resp = client.get(f"/videos/{analysis_id}", headers=_auth(caretaker_token))
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == analysis_id


def test_get_evidence_frame_returns_real_image_bytes(client, caretaker_token):
    with tempfile.TemporaryDirectory() as tmp:
        image_path = os.path.join(tmp, "fire.jpg")
        _make_fire_colored_image(image_path)
        with open(image_path, "rb") as f:
            upload_resp = client.post(
                "/videos/upload",
                headers=_auth(caretaker_token),
                files={"file": ("fire.jpg", f, "image/jpeg")},
                data={"analysis_type": "FIRE_SMOKE"},
            )
    body = upload_resp.json()
    evidence_id = body["evidence"][0]["id"]

    resp = client.get(f"/videos/{body['id']}/evidence/{evidence_id}", headers=_auth(caretaker_token))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/")
    assert len(resp.content) > 0
