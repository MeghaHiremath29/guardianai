# AI/ML Methodology

This document follows the template required by the project brief for each
AI component: problem definition, dataset, preprocessing, features,
algorithm, training, validation, metrics, and limitations. **No
accuracy/precision/recall/F1 numbers are reported anywhere in this file
unless a model has actually been trained and evaluated on a real, labeled
dataset — none has, for any of the three components below.** Where a metric
would normally go, this document says so explicitly instead of inventing
a number.

All three components are currently rule-based / classical baselines, not
trained models, per the project brief's instruction to "use the simplest
reliable architecture first" and not add deep learning just to look
advanced.

---

## 1. Fall / Health Emergency Detection

**Problem definition:** given a short window of wearable-style sensor
readings (heart rate, 3-axis acceleration, orientation, inactivity
duration), estimate whether a fall or health emergency likely occurred, and
how confident/severe that estimate is.

**Dataset:** none used. The software sensor simulator (`ml/simulator/` and
`app/ai/fall_detection/scenarios.py`) generates synthetic sequences for five
scenarios (NORMAL, WALKING, FALL, FALL_HIGH_HEART_RATE,
INACTIVITY_AFTER_FALL) used for development and testing, not for training a
model. A real deployment would need a labeled dataset of actual wearable
sensor traces around real fall events (e.g. SisFall, MobiAct, or similar
public fall-detection datasets) to train and validate a classifier.

**Preprocessing:** raw readings are used directly — acceleration magnitude
is computed as `sqrt(x²+y²+z²)`. A sliding window (see `engine.py`) looks
for a spike followed by a stillness period, rather than evaluating single
readings in isolation.

**Features:** acceleration magnitude spike relative to a rolling baseline,
orientation change (upright → lying), post-spike inactivity duration, and
heart rate deviation from a configured normal range.

**Algorithm:** rule-based weighted scoring (`app/ai/fall_detection/engine.py`).
Each contributing signal adds a fixed, configurable weight toward a 0.0–1.0
confidence score:
- Acceleration spike: +0.30
- Orientation change: +0.20
- Post-impact inactivity: +0.30
- Abnormal heart rate: +0.20

Severity thresholds (also configurable): confidence ≥0.75 → CRITICAL,
≥0.55 → HIGH, ≥0.35 → WARNING, else NORMAL.

**Training:** not applicable — this is a hand-specified rule system, not a
learned model. The brief explicitly allows this as a first version, with an
optional classical ML classifier (e.g. RandomForest) as a documented
comparison — not yet built.

**Validation:** 8 unit tests (`tests/test_fall_detection.py`) verify the
*logic* behaves correctly against synthetic sequences (e.g. a spike alone
should not yet reach HIGH; spike + stillness should; spike + stillness +
abnormal heart rate should reach CRITICAL). This validates the rule
implementation, not real-world detection accuracy.

**Metrics:** not available until the model is trained and evaluated on a
real dataset. No accuracy/precision/recall/F1 numbers exist for this
component.

**Limitations:** thresholds are reasoned starting points, not tuned against
real fall data; cannot distinguish a genuine fall from, e.g., placing the
device down hard; no learned generalization — behaves identically on
scenarios not covered by disclosed test cases.

---

## 2. Traffic Accident Detection

**Problem definition:** given an uploaded video, estimate whether it likely
shows a traffic accident, with a confidence/severity estimate and the
approximate frame/timestamp of the suspected event.

**Dataset:** none used — no labeled accident-video dataset was available.
A real deployment would need one (e.g. CADP, DAD, or a similar public
accident-detection dataset) to train and validate an object-tracking or
learned classifier.

**Preprocessing (`app/ai/accident_detection/video_processor.py`, real
OpenCV):** the video is opened, up to 150 frames are evenly sampled, each
resized to 320px width for speed, converted to grayscale, and Gaussian
blurred. Frame-to-frame **motion magnitude** is computed as the mean
absolute grayscale difference between consecutive sampled frames.

**Features:** a single scalar per sampled frame — motion magnitude — is fed
to the scoring engine. No object detection or tracking is performed.

**Algorithm (`app/ai/accident_detection/engine.py`, pure function, no CV
dependency, independently unit-tested):** scans the motion-magnitude
sequence for a frame where motion spikes sharply above a rolling baseline
(driving/ambient motion), followed within a bounded lookahead window by a
sustained drop to near-stillness (a stop). This mirrors the same
spike-then-stillness pattern the fall-detection engine looks for in
accelerometer data. A weighted score combines spike strength (45%),
stillness strength (35%), and how promptly the stillness follows the spike
(20%). Confidence is capped at 0.97 — the system never claims near-certainty.

**Alternative considered:** the original brief allows using a pretrained
detector (e.g. YOLOv8n) for vehicle detection/tracking if one is actually
integrated and explained. This was **not** done for Phase 4 — no trained or
pretrained object-detection model is used anywhere in this pipeline. This
is documented honestly rather than claiming YOLO integration that doesn't
exist. It remains a documented upgrade path (see `docs/architecture.md`).

**Training:** not applicable — classical signal-processing heuristic, not
a learned model.

**Validation:** 6 pure unit tests (`tests/test_video_detection_engines.py`)
against synthetic motion-magnitude arrays (steady driving, spike-that-never-settles,
spike-then-stillness, empty/too-short sequences, static-camera edge case).
Additionally, 2 integration tests upload genuinely synthetic video files
(written with OpenCV in the test itself, not pre-recorded fixtures) through
the real endpoint and real pipeline.

**Metrics:** not available until the model is evaluated on a real, labeled
accident-video dataset.

**Limitations (documented in code, repeated here):**
- Cannot distinguish hard braking from an actual collision
- Cannot distinguish a camera cut/shake from a collision
- No object tracking — doesn't know how many vehicles are in frame, only
  that pixel motion changed sharply
- Threshold-based, not learned — thresholds are configurable but not tuned
  against a labeled dataset

---

## 3. Fire / Smoke Detection

**Problem definition:** given an uploaded image or video, estimate whether
it likely shows fire and/or smoke, with a confidence/severity estimate.

**Dataset:** none used. A real deployment would need a labeled fire/smoke
image dataset (e.g. FIRE dataset variants on Kaggle, or a similar public
corpus) to train and validate a CNN classifier.

**Preprocessing (`app/ai/fire_detection/image_processor.py`, real OpenCV):**
each frame (or the single uploaded image) is resized to 320px width,
converted to HSV color space. A **fire mask** is computed via HSV
thresholding tuned to the red-orange-yellow, high-saturation/value band
typical of flame color, with morphological opening to remove isolated noise
pixels. A **smoke mask** is computed via a broader low-saturation gray-blue
HSV band, additionally gated by a **local intensity-variance filter**
(computed via box-blur of the grayscale image and its square) so flat
painted surfaces and heavily textured scenes are excluded — real smoke has
a distinctive soft, non-uniform texture that this filter targets.

**Features:** per-frame fire-pixel ratio and smoke-pixel ratio (fraction of
total pixels matching each color+texture profile).

**Algorithm (`app/ai/fire_detection/engine.py`, pure function, independently
unit-tested):** for video, a fire/smoke signal must persist across a
minimum fraction of sampled frames (guards against a single red car or
orange jacket triggering a false positive in one frame); for a single
image, no persistence check is needed. Confidence combines fire and smoke
components, weighted toward fire as the stronger, less noisy signal;
capped at 0.9 (fire) / 0.85 (smoke-only) — never near-certain.

**Training:** not applicable — classical color/texture heuristic, not a
learned model.

**Validation:** 6 pure unit tests against synthetic frame-signal arrays
(no fire/smoke color present, single-frame flash that doesn't persist,
persistent fire across frames, persistent heavy smoke alone reaching
HIGH/CRITICAL, single-image detection, empty input). Additionally, 4
integration tests upload genuinely synthetic images/videos (an
orange-red-dominated JPEG generated with OpenCV, and a plain gray control
image) through the real endpoint and pipeline, confirming both true and
false-positive-avoidance behavior end-to-end.

**Metrics:** not available until the model is evaluated on a real, labeled
fire/smoke dataset.

**Limitations (documented in code, repeated here):**
- Will false-positive on sunsets, orange/red clothing or objects, warm
  indoor lighting, brake lights
- Cannot distinguish an intentional, contained fire (campfire, candle,
  stove) from a hazardous fire
- Smoke detection is inherently weaker than fire detection — gray/hazy
  scenes (fog, overcast sky, dust) can still trigger it despite the
  texture gate
- Not trained or validated against a labeled fire dataset — thresholds are
  reasoned starting points, not tuned values
