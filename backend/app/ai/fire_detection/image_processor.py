"""
Image processor for fire/smoke detection — real OpenCV/HSV color analysis.
Computes the fraction of pixels in a frame matching a fire-color profile
and a smoke-color profile. No fabricated output.
"""
import logging
import os

import cv2
import numpy as np

from app.ai.fire_detection.engine import FrameSignal

logger = logging.getLogger("guardianai.fire_detection")

# HSV ranges (OpenCV: H 0-179, S/V 0-255). Two ranges for fire because
# orange/yellow fire hues can wrap near the low end of the hue circle.
FIRE_HSV_RANGES = [
    (np.array([0, 100, 120]), np.array([35, 255, 255])),   # red-orange-yellow, high sat/value
]

# Smoke: low saturation (grayish), mid brightness — deliberately broad,
# which is exactly why it's treated as weaker evidence than fire (see
# engine.py docstring on limitations).
SMOKE_HSV_LOWER = np.array([0, 0, 60])
SMOKE_HSV_UPPER = np.array([179, 40, 200])

# Local-variance band (in grayscale intensity units) that real smoke tends
# to fall into — enough texture to not be a flat painted surface, not so
# much as to be a busy detailed scene. See compute_frame_signal().
SMOKE_MIN_LOCAL_STD = 2.0
SMOKE_MAX_LOCAL_STD = 25.0

MAX_SAMPLED_FRAMES = 30
PROCESSING_WIDTH = 320


class ImageProcessingError(Exception):
    pass


def _resize(frame: np.ndarray) -> np.ndarray:
    height, width = frame.shape[:2]
    if width <= PROCESSING_WIDTH:
        return frame
    scale = PROCESSING_WIDTH / width
    return cv2.resize(frame, (PROCESSING_WIDTH, int(height * scale)))


def compute_frame_signal(frame_bgr: np.ndarray) -> FrameSignal:
    """Computes fire/smoke pixel ratios for a single BGR frame (as read by
    OpenCV). Pure function over pixel data — no I/O."""
    frame = _resize(frame_bgr)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    total_pixels = frame.shape[0] * frame.shape[1]

    fire_mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for lower, upper in FIRE_HSV_RANGES:
        fire_mask |= cv2.inRange(hsv, lower, upper)
    # Clean up isolated noise pixels so a handful of stray warm pixels
    # (skin tone, etc.) don't count as "fire".
    fire_mask = cv2.morphologyEx(fire_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    fire_ratio = float(np.count_nonzero(fire_mask)) / total_pixels

    smoke_mask = cv2.inRange(hsv, SMOKE_HSV_LOWER, SMOKE_HSV_UPPER)
    smoke_mask = cv2.morphologyEx(smoke_mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))

    # Color alone is a very weak smoke signal — almost any flat gray
    # surface (wall, road, overcast sky) matches it. Real smoke has soft,
    # non-uniform texture (gentle density gradients), unlike a flat painted
    # surface (near-zero local variance) or a busy detailed scene (high
    # local variance). Gate the color mask with a local-variance band so a
    # perfectly flat gray region — or a highly textured one — doesn't
    # count, which meaningfully cuts the false-positive rate without
    # requiring a trained model.
    local_mean = cv2.blur(gray.astype(np.float32), (9, 9))
    local_sq_mean = cv2.blur((gray.astype(np.float32)) ** 2, (9, 9))
    local_variance = np.clip(local_sq_mean - local_mean**2, 0, None)
    local_std = np.sqrt(local_variance)
    texture_gate = ((local_std > SMOKE_MIN_LOCAL_STD) & (local_std < SMOKE_MAX_LOCAL_STD)).astype(np.uint8) * 255

    smoke_mask = cv2.bitwise_and(smoke_mask, texture_gate)
    smoke_ratio = float(np.count_nonzero(smoke_mask)) / total_pixels

    return FrameSignal(fire_ratio=fire_ratio, smoke_ratio=smoke_ratio)


def analyze_image(image_path: str) -> list[FrameSignal]:
    """Single-image entry point. Returns a length-1 list so it shares the
    same FireDetectionResult.evaluate() code path as video."""
    if not os.path.isfile(image_path):
        raise ImageProcessingError(f"Image file not found: {image_path}")

    frame = cv2.imread(image_path)
    if frame is None:
        raise ImageProcessingError("OpenCV could not read this image (unsupported or corrupt file).")

    return [compute_frame_signal(frame)]


def analyze_video(video_path: str) -> list[FrameSignal]:
    """Samples frames evenly across the video and computes a signal for
    each. Raises ImageProcessingError if the video can't be opened."""
    if not os.path.isfile(video_path):
        raise ImageProcessingError(f"Video file not found: {video_path}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ImageProcessingError("OpenCV could not open this video file (unsupported or corrupt).")

    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total_frames <= 0:
            raise ImageProcessingError("Video has no readable frames.")

        sample_count = min(MAX_SAMPLED_FRAMES, total_frames)
        sample_indices = sorted(set(np.linspace(0, total_frames - 1, sample_count, dtype=int).tolist()))

        signals: list[FrameSignal] = []
        for idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            signals.append(compute_frame_signal(frame))

        if not signals:
            raise ImageProcessingError("Could not extract any readable frames from this video.")

        return signals
    finally:
        cap.release()
