"""
Video processor for accident detection — real OpenCV frame extraction and
motion-magnitude computation. No fabricated output: if the video can't be
opened or has too few frames, this raises/returns explicit failure states
rather than pretending to analyze something it didn't.
"""
import logging
import os
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger("guardianai.accident_detection")

# Process at most this many sampled frames, to bound runtime on long videos.
MAX_SAMPLED_FRAMES = 150
# Resize frames before diffing — motion magnitude doesn't need full
# resolution, and this keeps processing fast on CPU-only machines.
PROCESSING_WIDTH = 320


class VideoProcessingError(Exception):
    """Raised when a video genuinely cannot be processed (corrupt, empty,
    unsupported codec, etc.) — never silently swallowed."""


@dataclass
class FrameSample:
    frame_index: int
    timestamp_seconds: float
    motion_magnitude: float


def _resize_for_processing(frame: np.ndarray) -> np.ndarray:
    height, width = frame.shape[:2]
    if width <= PROCESSING_WIDTH:
        return frame
    scale = PROCESSING_WIDTH / width
    return cv2.resize(frame, (PROCESSING_WIDTH, int(height * scale)))


def extract_motion_samples(video_path: str) -> tuple[list[FrameSample], float, int]:
    """Opens the video, samples up to MAX_SAMPLED_FRAMES evenly across it,
    and computes frame-to-frame motion magnitude (mean absolute grayscale
    difference between consecutive sampled frames).

    Returns (samples, fps, total_frame_count). Raises VideoProcessingError
    if the file can't be opened or has no usable frames.
    """
    if not os.path.isfile(video_path):
        raise VideoProcessingError(f"Video file not found: {video_path}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise VideoProcessingError("OpenCV could not open this video file (unsupported or corrupt).")

    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        if total_frames <= 1:
            raise VideoProcessingError("Video has too few frames to analyze motion.")

        sample_count = min(MAX_SAMPLED_FRAMES, total_frames)
        sample_indices = sorted(set(np.linspace(0, total_frames - 1, sample_count, dtype=int).tolist()))

        samples: list[FrameSample] = []
        prev_gray: np.ndarray | None = None

        for idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue

            frame = _resize_for_processing(frame)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (5, 5), 0)

            if prev_gray is not None:
                diff = cv2.absdiff(gray, prev_gray)
                magnitude = float(np.mean(diff))
                timestamp = idx / fps if fps > 0 else 0.0
                samples.append(FrameSample(frame_index=idx, timestamp_seconds=timestamp, motion_magnitude=magnitude))

            prev_gray = gray

        if len(samples) < 4:
            raise VideoProcessingError(
                "Could not extract enough readable frames to analyze motion (video may be too short or corrupt)."
            )

        return samples, fps, total_frames
    finally:
        cap.release()


def save_evidence_frame(video_path: str, frame_index: int, output_path: str) -> bool:
    """Extracts a single frame at frame_index and saves it as a JPEG for
    evidence. Returns False (does not raise) if the frame can't be grabbed —
    a missing evidence frame shouldn't crash the whole analysis."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return False
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = cap.read()
        if not ok or frame is None:
            return False
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        return bool(cv2.imwrite(output_path, frame))
    finally:
        cap.release()
