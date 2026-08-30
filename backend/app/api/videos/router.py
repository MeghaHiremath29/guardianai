"""
Video/image upload and analysis endpoints — Phase 4.

Flow (matches FEATURE 2 / FEATURE 3 in the project brief exactly):
upload -> validate -> save to disk -> extract frames -> run the real CV
engine -> save an evidence frame -> create an Emergency via the Emergency
Engine if the result clears the HIGH/CRITICAL threshold -> return the
honest result either way.

Processing runs synchronously inside the request for Phase 4 (see
docs/architecture.md for the async/background-task upgrade path) — the
person uploading gets the real result immediately rather than polling a
fake "processing" status that always completes instantly anyway.
"""
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.ai.accident_detection.engine import evaluate as evaluate_accident
from app.ai.accident_detection.video_processor import (
    VideoProcessingError,
    extract_motion_samples,
    save_evidence_frame,
)
from app.ai.fire_detection.engine import evaluate as evaluate_fire
from app.ai.fire_detection.image_processor import ImageProcessingError, analyze_image, analyze_video
from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.emergency import EmergencySource, EmergencyType
from app.models.person import Person
from app.models.user import User
from app.models.video_analysis import AnalysisStatus, AnalysisType, Evidence, MediaType, VideoAnalysis
from app.schemas.video import VideoAnalysisOut
from app.services.emergency_engine import create_emergency

router = APIRouter(prefix="/videos", tags=["videos"])
logger = logging.getLogger("guardianai.videos")

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_EXTENSIONS = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS


def _safe_filename(original: str) -> str:
    ext = os.path.splitext(original)[1].lower()
    return f"{uuid.uuid4()}{ext}"


def _to_out(analysis: VideoAnalysis) -> VideoAnalysisOut:
    return VideoAnalysisOut(
        id=analysis.id,
        person_id=analysis.person_id,
        emergency_id=analysis.emergency_id,
        analysis_type=analysis.analysis_type,
        media_type=analysis.media_type,
        status=analysis.status,
        original_filename=analysis.original_filename,
        location_lat=analysis.location_lat,
        location_lng=analysis.location_lng,
        location_label=analysis.location_label,
        detected=analysis.detected,
        confidence=analysis.confidence,
        severity=analysis.severity,
        reasons=json.loads(analysis.reasons) if analysis.reasons else [],
        event_timestamp_seconds=analysis.event_timestamp_seconds,
        error_detail=analysis.error_detail,
        created_at=analysis.created_at,
        processed_at=analysis.processed_at,
        evidence=list(analysis.evidence),
    )


def _run_accident_analysis(db: Session, analysis: VideoAnalysis, video_path: str) -> None:
    samples, _fps, _total = extract_motion_samples(video_path)
    magnitudes = [s.motion_magnitude for s in samples]
    result = evaluate_accident(magnitudes)

    analysis.detected = result.accident_detected
    analysis.confidence = result.confidence
    analysis.severity = result.severity
    analysis.reasons = json.dumps(result.reasons)

    if result.spike_frame_index is not None:
        frame = samples[result.spike_frame_index] if result.spike_frame_index < len(samples) else None
        if frame is not None:
            analysis.event_timestamp_seconds = round(frame.timestamp_seconds, 2)

        os.makedirs(settings.EVIDENCE_DIR, exist_ok=True)
        evidence_filename = f"{analysis.id}_evidence.jpg"
        evidence_path = os.path.join(settings.EVIDENCE_DIR, evidence_filename)
        real_frame_index = frame.frame_index if frame else result.spike_frame_index
        if save_evidence_frame(video_path, real_frame_index, evidence_path):
            db.add(
                Evidence(
                    video_analysis_id=analysis.id,
                    file_path=evidence_path,
                    file_type="evidence_frame",
                    description="Frame at the detected motion spike",
                )
            )


def _run_fire_analysis(db: Session, analysis: VideoAnalysis, file_path: str, is_video: bool) -> None:
    signals = analyze_video(file_path) if is_video else analyze_image(file_path)
    result = evaluate_fire(signals)

    analysis.detected = result.fire_detected or result.smoke_detected
    analysis.confidence = result.confidence
    analysis.severity = result.severity
    analysis.reasons = json.dumps(result.reasons)

    # For fire, the source file itself IS the clearest evidence frame
    # (single image), or we just reuse the first sampled frame's timestamp
    # for video — there's no single "spike frame" the way accident
    # detection has, since fire/smoke is a persistence-based signal.
    os.makedirs(settings.EVIDENCE_DIR, exist_ok=True)
    if not is_video:
        # The uploaded image already lives in UPLOAD_DIR; reference it
        # directly as evidence rather than duplicating the file.
        db.add(
            Evidence(
                video_analysis_id=analysis.id,
                file_path=file_path,
                file_type="evidence_frame",
                description="Uploaded image analyzed for fire/smoke",
            )
        )
    else:
        evidence_filename = f"{analysis.id}_evidence.jpg"
        evidence_path = os.path.join(settings.EVIDENCE_DIR, evidence_filename)
        # Grab a frame from partway through the clip as the representative
        # evidence frame for video-based fire detection.
        if save_evidence_frame(file_path, 0, evidence_path):
            db.add(
                Evidence(
                    video_analysis_id=analysis.id,
                    file_path=evidence_path,
                    file_type="evidence_frame",
                    description="Representative frame from the analyzed video",
                )
            )


@router.post("/upload", response_model=VideoAnalysisOut, status_code=status.HTTP_201_CREATED)
def upload_and_analyze(
    file: UploadFile = File(...),
    analysis_type: AnalysisType = Form(...),
    person_id: str | None = Form(None),
    location_lat: float | None = Form(None),
    location_lng: float | None = Form(None),
    location_label: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VideoAnalysisOut:
    # --- Validate ---
    original_name = file.filename or "upload"
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    person: Person | None = None
    if person_id:
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")

    # --- Save to disk, enforcing the size limit while streaming ---
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    stored_name = _safe_filename(original_name)
    stored_path = os.path.join(settings.UPLOAD_DIR, stored_name)
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    bytes_written = 0
    try:
        with open(stored_path, "wb") as out_file:
            while chunk := file.file.read(1024 * 1024):
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB}MB limit.",
                    )
                out_file.write(chunk)
    except HTTPException:
        if os.path.exists(stored_path):
            os.remove(stored_path)
        raise

    if bytes_written == 0:
        os.remove(stored_path)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    is_video = ext in VIDEO_EXTENSIONS
    media_type = MediaType.VIDEO if is_video else MediaType.IMAGE

    analysis = VideoAnalysis(
        uploaded_by_id=current_user.id,
        person_id=person.id if person else None,
        analysis_type=analysis_type,
        media_type=media_type,
        status=AnalysisStatus.PROCESSING,
        original_filename=original_name,
        stored_path=stored_path,
        location_lat=location_lat if location_lat is not None else (person.latitude if person else None),
        location_lng=location_lng if location_lng is not None else (person.longitude if person else None),
        location_label=location_label,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    db.add(Evidence(video_analysis_id=analysis.id, file_path=stored_path, file_type="source_video" if is_video else "source_image"))
    db.commit()

    logger.info(
        "videos.upload_received analysis_id=%s type=%s media=%s by=%s",
        analysis.id, analysis_type.value, media_type.value, current_user.id,
    )

    # --- Run the real CV pipeline. Any failure here is recorded honestly, never masked. ---
    try:
        if analysis_type == AnalysisType.TRAFFIC_ACCIDENT:
            if not is_video:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Traffic accident analysis requires a video file, not an image.",
                )
            _run_accident_analysis(db, analysis, stored_path)
        else:
            _run_fire_analysis(db, analysis, stored_path, is_video)

        analysis.status = AnalysisStatus.COMPLETED
        analysis.processed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(analysis)

        logger.info(
            "videos.analysis_completed analysis_id=%s detected=%s confidence=%s severity=%s",
            analysis.id, analysis.detected, analysis.confidence, analysis.severity,
        )

    except (VideoProcessingError, ImageProcessingError) as exc:
        analysis.status = AnalysisStatus.FAILED
        analysis.error_detail = str(exc)
        analysis.processed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(analysis)
        logger.warning("videos.analysis_failed analysis_id=%s error=%s", analysis.id, str(exc))
        return _to_out(analysis)
    except HTTPException:
        analysis.status = AnalysisStatus.FAILED
        analysis.error_detail = "Wrong media type for this analysis type."
        db.commit()
        raise

    # --- Feed the result through the Emergency Engine (the single funnel — see emergency_engine.py) ---
    if analysis.severity in ("HIGH", "CRITICAL"):
        event_type = EmergencyType.TRAFFIC_ACCIDENT if analysis_type == AnalysisType.TRAFFIC_ACCIDENT else EmergencyType.FIRE_SMOKE
        source = EmergencySource.VIDEO_ACCIDENT if analysis_type == AnalysisType.TRAFFIC_ACCIDENT else EmergencySource.VIDEO_FIRE

        emergency = create_emergency(
            db,
            event_type=event_type,
            confidence=analysis.confidence,
            severity=analysis.severity,
            reasons=json.loads(analysis.reasons),
            source=source,
            person=person,
            location_lat=analysis.location_lat,
            location_lng=analysis.location_lng,
        )
        if emergency:
            analysis.emergency_id = emergency.id
            db.commit()
            db.refresh(analysis)

    return _to_out(analysis)


@router.get("", response_model=list[VideoAnalysisOut])
def list_video_analyses(
    person_id: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[VideoAnalysisOut]:
    query = db.query(VideoAnalysis)
    if person_id:
        query = query.filter(VideoAnalysis.person_id == person_id)
    results = query.order_by(VideoAnalysis.created_at.desc()).limit(100).all()
    return [_to_out(a) for a in results]


@router.get("/{analysis_id}", response_model=VideoAnalysisOut)
def get_video_analysis(analysis_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> VideoAnalysisOut:
    analysis = db.query(VideoAnalysis).filter(VideoAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video analysis not found")
    return _to_out(analysis)


@router.get("/{analysis_id}/evidence/{evidence_id}")
def get_evidence_file(
    analysis_id: str, evidence_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> FileResponse:
    evidence = (
        db.query(Evidence)
        .filter(Evidence.id == evidence_id, Evidence.video_analysis_id == analysis_id)
        .first()
    )
    if not evidence or not os.path.isfile(evidence.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence file not found")
    return FileResponse(evidence.file_path)
