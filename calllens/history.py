"""Audio history management, persistent audit logging, and call recording recovery.

Maintains recording sessions, audio asset metadata, speech operations, transcripts,
and safe cleanup policies without storing private credentials or leaking sensitive data.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import soundfile as sf
from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger("calllens.history")

Base = declarative_base()


class AudioHistoryRecord(Base):
    """Backward-compatible audit trail record for STT and TTS activity."""
    __tablename__ = "audio_history"
    __table_args__ = (
        Index("idx_audio_history_kind_timestamp", "kind", "timestamp"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    kind = Column(String(16), nullable=False)  # 'stt', 'tts', 'followup'
    session_id = Column(String(64), nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    model = Column(String(64), nullable=False)
    language = Column(String(16), nullable=False)
    format = Column(String(32), nullable=True)
    duration_sec = Column(Float, nullable=True)
    latency_sec = Column(Float, nullable=False)
    status = Column(String(16), nullable=False, default="completed")  # 'completed' or 'failed'
    input_preview = Column(Text, nullable=True)
    output_preview = Column(Text, nullable=True)
    audio_filename = Column(String(256), nullable=True)
    metadata_json = Column(Text, nullable=True)


class RecordingSession(Base):
    """Captures the end-to-end lifecycle of a voice recording interaction."""
    __tablename__ = "recording_sessions"
    __table_args__ = (
        Index("idx_recording_sessions_status_created", "status", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    status = Column(String(32), nullable=False, default="active")  # 'active', 'completed', 'interrupted', 'failed'
    source = Column(String(32), nullable=False)  # 'stt_mic', 'stt_upload', 'websocket', 'followup_desk'
    language = Column(String(16), nullable=False, default="hi-IN")
    customer_name = Column(String(128), nullable=True)
    metadata_json = Column(Text, nullable=True)


class AudioAsset(Base):
    """Immutable audio file metadata persisted to storage outside git."""
    __tablename__ = "audio_assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(String(64), unique=True, index=True, nullable=False)
    session_id = Column(String(64), index=True, nullable=True)
    asset_type = Column(String(32), nullable=False)  # 'original', 'assembled', 'normalized', 'tts_generated', 'followup_reminder'
    filename = Column(String(256), nullable=False)
    storage_path = Column(String(512), nullable=False)
    mime_type = Column(String(64), default="audio/wav")
    codec = Column(String(32), default="pcm_s16le")
    sample_rate = Column(Integer, nullable=True)
    channels = Column(Integer, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    duration_estimated = Column(Integer, default=0)  # 1 if estimated, 0 if measured
    file_size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    storage_status = Column(String(32), default="persisted")  # 'persisted', 'deleted', 'missing'
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SpeechOperation(Base):
    """Tracks atomic STT or TTS engine processing executions."""
    __tablename__ = "speech_operations"
    __table_args__ = (
        Index("idx_speech_operations_type_created", "operation_type", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    operation_id = Column(String(64), unique=True, index=True, nullable=False)
    session_id = Column(String(64), index=True, nullable=True)
    asset_id = Column(String(64), index=True, nullable=True)
    operation_type = Column(String(16), nullable=False)  # 'stt' or 'tts'
    model = Column(String(64), nullable=False)
    voice = Column(String(32), nullable=True)
    language = Column(String(16), nullable=False, default="hi-IN")
    format = Column(String(32), nullable=True)
    status = Column(String(32), nullable=False)  # 'completed', 'failed', 'in_progress'
    provenance = Column(String(32), nullable=False, default="mock")  # 'live', 'cache', 'mock', 'unknown'
    latency_ms = Column(Float, nullable=False, default=0.0)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class TranscriptRecord(Base):
    """Persisted speech transcription text."""
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transcript_id = Column(String(64), unique=True, index=True, nullable=False)
    session_id = Column(String(64), index=True, nullable=True)
    operation_id = Column(String(64), index=True, nullable=True)
    text = Column(Text, nullable=False)
    word_count = Column(Integer, default=0)
    char_count = Column(Integer, default=0)
    is_final = Column(Integer, default=1)
    transcript_source = Column(String(32), default="prisma")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class FollowupRecord(Base):
    """Structured commitments and operator confirmations for Follow-up Desk."""
    __tablename__ = "followup_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    followup_id = Column(String(64), unique=True, index=True, nullable=False)
    session_id = Column(String(64), index=True, nullable=True)
    transcript_id = Column(String(64), nullable=True)
    asset_id = Column(String(64), nullable=True)
    customer_name = Column(String(128), nullable=False)
    amount = Column(Integer, nullable=True)
    due_date = Column(String(64), nullable=True)
    ptp_date = Column(String(64), nullable=True)
    concern = Column(String(256), nullable=False)
    call_summary = Column(Text, nullable=False)
    reminder_text = Column(Text, nullable=False)
    voice = Column(String(32), default="Pranav")
    verification_status = Column(String(32), default="operator_verified")
    operator_notes = Column(Text, nullable=True)
    confirmed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def _resolve_data_dir(data_dir: Path | None = None) -> Path:
    """Resolves data directory with fallback from ../calllens-data to ./data."""
    if data_dir is not None:
        return data_dir
    env_dir = os.getenv("DATA_DIR")
    if env_dir:
        return Path(env_dir)
    sibling = Path("../calllens-data")
    if sibling.exists():
        return sibling
    local = Path("data")
    local.mkdir(parents=True, exist_ok=True)
    return local


def get_storage_dirs(data_dir: Path | None = None) -> tuple[Path, Path]:
    """Returns and ensures storage directories for recordings and generated TTS audio."""
    resolved = _resolve_data_dir(data_dir)
    rec_dir = resolved / "recordings"
    tts_dir = resolved / "tts_audio"
    rec_dir.mkdir(parents=True, exist_ok=True)
    tts_dir.mkdir(parents=True, exist_ok=True)
    return rec_dir, tts_dir


def _get_db_session(db_url: str | None = None):
    if db_url is None:
        resolved = _resolve_data_dir()
        db_path = os.getenv("DATABASE_URL", f"sqlite:///{resolved}/benchmark.db")
        db_url = db_path
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

    # Ensure composite indexes exist on existing SQLite tables idempotently
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_speech_operations_type_created ON speech_operations(operation_type, created_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_recording_sessions_status_created ON recording_sessions(status, created_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audio_history_kind_timestamp ON audio_history(kind, timestamp)"))
            conn.commit()
    except Exception as exc:
        logger.debug("Composite index setup note: %s", exc)

    Session = sessionmaker(bind=engine)
    return Session()



# ---------------------------------------------------------------------------
# Recording Session & Audio Asset Persistence Functions
# ---------------------------------------------------------------------------

def create_recording_session(
    source: str,
    session_id: str | None = None,
    language: str = "hi-IN",
    customer_name: str | None = None,
    metadata: dict[str, Any] | None = None,
    db_url: str | None = None,
) -> str:
    """Creates a new recording session record."""
    sess_id = session_id or f"sess_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
    session = _get_db_session(db_url)
    try:
        rec = RecordingSession(
            session_id=sess_id,
            source=source,
            language=language,
            customer_name=customer_name,
            status="active",
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
        )
        session.add(rec)
        session.commit()
        return sess_id
    except Exception as exc:
        session.rollback()
        logger.error("Failed to create recording session: %s", exc)
        return sess_id
    finally:
        session.close()


def update_recording_session(
    session_id: str,
    status: str,
    metadata_update: dict[str, Any] | None = None,
    db_url: str | None = None,
) -> bool:
    """Updates the status and metadata of a recording session."""
    session = _get_db_session(db_url)
    try:
        rec = session.query(RecordingSession).filter_by(session_id=session_id).first()
        if rec:
            rec.status = status
            rec.updated_at = datetime.now(timezone.utc)
            if metadata_update:
                cur_meta = {}
                if rec.metadata_json:
                    try:
                        cur_meta = json.loads(rec.metadata_json)
                    except Exception:
                        pass
                cur_meta.update(metadata_update)
                rec.metadata_json = json.dumps(cur_meta, ensure_ascii=False)
            session.commit()
            return True
        return False
    except Exception as exc:
        session.rollback()
        logger.error("Failed to update recording session %s: %s", session_id, exc)
        return False
    finally:
        session.close()


def ensure_wav_bytes(audio_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Wraps raw 16-bit PCM audio bytes in a standard RIFF/WAV header if not already a container format."""
    if audio_bytes.startswith(b"RIFF") or audio_bytes.startswith(b"OggS") or audio_bytes.startswith(b"\x1aE\xdf\xa3"):
        return audio_bytes
    bio = io.BytesIO()
    import wave
    with wave.open(bio, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(sample_rate)
        wf.writeframes(audio_bytes)
    return bio.getvalue()


def save_audio_asset(
    audio_bytes: bytes,
    asset_type: str,
    *,
    session_id: str | None = None,
    preferred_filename: str | None = None,
    storage_dir: Path | None = None,
    db_url: str | None = None,
) -> dict[str, Any]:
    """Persists audio bytes to storage outside git with SHA-256 integrity and decoded metadata."""
    if not audio_bytes:
        raise ValueError("Cannot persist empty audio bytes")

    asset_id = f"ast_{uuid.uuid4().hex[:12]}"

    # Use random UUID in filename to prevent predictable filenames and information leaks
    raw_fname = preferred_filename or f"{asset_type}_{uuid.uuid4().hex[:16]}.wav"
    filename = Path(raw_fname).name  # prevent path traversal

    rec_dir, tts_dir = get_storage_dirs()
    if storage_dir is None:
        target_dir = tts_dir if ("tts" in asset_type or "reminder" in asset_type) else rec_dir
    else:
        target_dir = storage_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    # Ensure audio bytes contain valid WAV header if saved as .wav
    if filename.endswith(".wav"):
        audio_bytes = ensure_wav_bytes(audio_bytes)

    sha256 = hashlib.sha256(audio_bytes).hexdigest()
    file_path = target_dir / filename
    file_path.write_bytes(audio_bytes)
    file_size = len(audio_bytes)

    # Soundfile inspection for exact metadata
    sample_rate: int | None = None
    channels: int | None = None
    duration_sec: float | None = None
    duration_estimated = 0
    try:
        with io.BytesIO(audio_bytes) as bio:
            info = sf.info(bio)
            sample_rate = info.samplerate
            channels = info.channels
            duration_sec = round(info.duration, 3)
    except Exception:
        try:
            with io.BytesIO(audio_bytes) as bio:
                import wave
                with wave.open(bio, "rb") as wf:
                    sample_rate = wf.getframerate()
                    channels = wf.getnchannels()
                    n_frames = wf.getnframes()
                    if sample_rate > 0:
                        duration_sec = round(n_frames / float(sample_rate), 3)
        except Exception:
            duration_sec = round(len(audio_bytes) / 32000.0, 3)
            duration_estimated = 1

    session = _get_db_session(db_url)
    try:
        asset = AudioAsset(
            asset_id=asset_id,
            session_id=session_id,
            asset_type=asset_type,
            filename=filename,
            storage_path=str(file_path),
            mime_type="audio/wav",
            codec="pcm_s16le",
            sample_rate=sample_rate,
            channels=channels,
            duration_seconds=duration_sec,
            duration_estimated=duration_estimated,
            file_size_bytes=file_size,
            sha256=sha256,
            storage_status="persisted",
        )
        session.add(asset)
        session.commit()
        return {
            "asset_id": asset_id,
            "session_id": session_id,
            "filename": filename,
            "storage_path": str(file_path),
            "duration_seconds": duration_sec,
            "duration_estimated": bool(duration_estimated),
            "file_size_bytes": file_size,
            "sha256": sha256,
            "sample_rate": sample_rate,
            "channels": channels,
        }
    except Exception as exc:
        session.rollback()
        logger.error("Failed to insert audio asset: %s", exc)
        raise
    finally:
        session.close()


def record_speech_operation(
    *,
    session_id: str | None,
    asset_id: str | None,
    operation_type: str,
    model: str,
    voice: str | None = None,
    language: str = "hi-IN",
    format: str | None = None,
    status: str = "completed",
    provenance: str = "mock",
    latency_ms: float = 0.0,
    error_code: str | None = None,
    error_message: str | None = None,
    db_url: str | None = None,
) -> str:
    """Records a structured speech operation."""
    op_id = f"op_{uuid.uuid4().hex[:12]}"
    session = _get_db_session(db_url)
    try:
        rec = SpeechOperation(
            operation_id=op_id,
            session_id=session_id,
            asset_id=asset_id,
            operation_type=operation_type,
            model=model,
            voice=voice,
            language=language,
            format=format,
            status=status,
            provenance=provenance,
            latency_ms=round(latency_ms, 2),
            error_code=error_code,
            error_message=error_message[:500] if error_message else None,
        )
        session.add(rec)
        session.commit()
        return op_id
    except Exception as exc:
        session.rollback()
        logger.error("Failed to record speech operation: %s", exc)
        return op_id
    finally:
        session.close()


def record_transcript(
    *,
    text: str,
    session_id: str | None = None,
    operation_id: str | None = None,
    transcript_source: str = "prisma",
    is_final: bool = True,
    db_url: str | None = None,
) -> str:
    """Records a transcript entry."""
    tr_id = f"tr_{uuid.uuid4().hex[:12]}"
    session = _get_db_session(db_url)
    try:
        rec = TranscriptRecord(
            transcript_id=tr_id,
            session_id=session_id,
            operation_id=operation_id,
            text=text,
            word_count=len(text.strip().split()) if text.strip() else 0,
            char_count=len(text),
            is_final=1 if is_final else 0,
            transcript_source=transcript_source,
        )
        session.add(rec)
        session.commit()
        return tr_id
    except Exception as exc:
        session.rollback()
        logger.error("Failed to record transcript: %s", exc)
        return tr_id
    finally:
        session.close()


def record_followup_entry(
    *,
    customer_name: str,
    amount: int | None,
    due_date: str | None,
    ptp_date: str | None,
    concern: str,
    call_summary: str,
    reminder_text: str,
    voice: str = "Pranav",
    session_id: str | None = None,
    transcript_id: str | None = None,
    asset_id: str | None = None,
    operator_notes: str | None = None,
    db_url: str | None = None,
) -> str:
    """Records a reviewed and confirmed Follow-up Desk entry."""
    flw_id = f"flw_{uuid.uuid4().hex[:12]}"
    session = _get_db_session(db_url)
    try:
        rec = FollowupRecord(
            followup_id=flw_id,
            session_id=session_id,
            transcript_id=transcript_id,
            asset_id=asset_id,
            customer_name=customer_name,
            amount=amount,
            due_date=due_date,
            ptp_date=ptp_date,
            concern=concern,
            call_summary=call_summary,
            reminder_text=reminder_text,
            voice=voice,
            verification_status="operator_verified",
            operator_notes=operator_notes,
        )
        session.add(rec)
        session.commit()
        return flw_id
    except Exception as exc:
        session.rollback()
        logger.error("Failed to record follow-up entry: %s", exc)
        return flw_id
    finally:
        session.close()


def get_followup_records(limit: int = 50, db_url: str | None = None) -> list[dict[str, Any]]:
    """Retrieves recent operator-confirmed Follow-up Desk records from SQLite."""
    session = _get_db_session(db_url)
    try:
        recs = session.query(FollowupRecord).order_by(FollowupRecord.id.desc()).limit(limit).all()
        asset_ids = [r.asset_id for r in recs if r.asset_id]
        asset_map: dict[str, str] = {}
        if asset_ids:
            assets = session.query(AudioAsset).filter(AudioAsset.asset_id.in_(asset_ids)).all()
            for a in assets:
                asset_map[a.asset_id] = a.filename

        results = []
        for r in recs:
            fname = asset_map.get(r.asset_id) if r.asset_id else None
            audio_url = f"/api/tts/audio/{fname}" if fname else None
            results.append({
                "followup_id": r.followup_id,
                "session_id": r.session_id,
                "asset_id": r.asset_id,
                "audio_url": audio_url,
                "customer_name": r.customer_name,
                "amount": r.amount,
                "due_date": r.due_date,
                "ptp_date": r.ptp_date,
                "concern": r.concern,
                "call_summary": r.call_summary,
                "reminder_text": r.reminder_text,
                "voice": r.voice,
                "verification_status": r.verification_status,
                "operator_notes": r.operator_notes,
                "confirmed_at": r.confirmed_at.strftime("%Y-%m-%d %H:%M:%S UTC") if r.confirmed_at else "",
            })
        return results
    except Exception as exc:
        logger.error("Failed to query followup records: %s", exc)
        return []
    finally:
        session.close()



def get_recording_sessions(
    limit: int = 50,
    status: str | None = None,
    db_url: str | None = None,
) -> list[dict[str, Any]]:
    """Retrieves recording sessions with linked assets and transcripts."""
    session = _get_db_session(db_url)
    try:
        q = session.query(RecordingSession)
        if status:
            q = q.filter_by(status=status)
        sessions = q.order_by(RecordingSession.id.desc()).limit(limit).all()

        results = []
        for s in sessions:
            assets = session.query(AudioAsset).filter_by(session_id=s.session_id, storage_status="persisted").all()
            transcripts = session.query(TranscriptRecord).filter_by(session_id=s.session_id).all()
            operations = session.query(SpeechOperation).filter_by(session_id=s.session_id).all()
            followup = session.query(FollowupRecord).filter_by(session_id=s.session_id).first()

            results.append({
                "session_id": s.session_id,
                "created_at": s.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if s.created_at else "",
                "updated_at": s.updated_at.strftime("%Y-%m-%d %H:%M:%S UTC") if s.updated_at else "",
                "status": s.status,
                "source": s.source,
                "language": s.language,
                "customer_name": s.customer_name,
                "assets": [
                    {
                        "asset_id": a.asset_id,
                        "asset_type": a.asset_type,
                        "filename": a.filename,
                        "duration_seconds": a.duration_seconds,
                        "duration_estimated": bool(a.duration_estimated),
                        "file_size_bytes": a.file_size_bytes,
                        "audio_url": f"/api/audio/{a.filename}",
                    }
                    for a in assets
                ],
                "transcript": transcripts[-1].text if transcripts else None,
                "operations": [
                    {
                        "operation_id": o.operation_id,
                        "type": o.operation_type,
                        "model": o.model,
                        "status": o.status,
                        "provenance": o.provenance,
                        "latency_ms": o.latency_ms,
                        "error_code": o.error_code,
                    }
                    for o in operations
                ],
                "followup": {
                    "followup_id": followup.followup_id,
                    "customer_name": followup.customer_name,
                    "amount": followup.amount,
                    "ptp_date": followup.ptp_date,
                    "concern": followup.concern,
                } if followup else None,
            })
        return results
    except Exception as exc:
        logger.error("Failed to query recording sessions: %s", exc)
        return []
    finally:
        session.close()


def get_audio_asset_by_id_or_filename(
    identifier: str,
    db_url: str | None = None,
) -> AudioAsset | None:
    """Finds an audio asset by asset_id or filename."""
    session = _get_db_session(db_url)
    try:
        safe_name = Path(identifier).name
        asset = session.query(AudioAsset).filter(
            (AudioAsset.asset_id == identifier) | (AudioAsset.filename == safe_name)
        ).first()
        return asset
    finally:
        session.close()


def delete_recording_session(session_id: str, db_url: str | None = None) -> bool:
    """Permanently deletes a recording session, its audio assets from disk, and all DB rows."""
    session = _get_db_session(db_url)
    try:
        # Collect assets directly linked to session
        assets = session.query(AudioAsset).filter_by(session_id=session_id).all()
        # Also collect any followup-linked reminder assets
        flws = session.query(FollowupRecord).filter_by(session_id=session_id).all()
        for flw in flws:
            if flw.asset_id:
                fa = session.query(AudioAsset).filter_by(asset_id=flw.asset_id).first()
                if fa and fa not in assets:
                    assets.append(fa)

        for a in assets:
            try:
                p = Path(a.storage_path)
                if p.exists():
                    p.unlink()
            except Exception as e:
                logger.warning("Error deleting file %s: %s", a.storage_path, e)
            try:
                session.delete(a)
            except Exception:
                pass

        # Delete database records in safe sequence
        session.query(TranscriptRecord).filter_by(session_id=session_id).delete()
        session.query(SpeechOperation).filter_by(session_id=session_id).delete()
        session.query(FollowupRecord).filter_by(session_id=session_id).delete()
        session.query(AudioAsset).filter_by(session_id=session_id).delete()
        session.query(AudioHistoryRecord).filter_by(session_id=session_id).delete()
        session.query(RecordingSession).filter_by(session_id=session_id).delete()

        session.commit()
        return True
    except Exception as exc:
        session.rollback()
        logger.error("Failed to delete recording session %s: %s", session_id, exc)
        return False
    finally:
        session.close()


def get_storage_diagnostics(db_url: str | None = None) -> dict[str, Any]:
    """Inspects storage integrity: computes disk bytes, detects missing files and orphaned assets."""
    session = _get_db_session(db_url)
    try:
        rec_dir, tts_dir = get_storage_dirs()
        total_sessions = session.query(RecordingSession).count()
        total_assets = session.query(AudioAsset).filter_by(storage_status="persisted").count()

        assets = session.query(AudioAsset).filter_by(storage_status="persisted").all()
        missing_count = 0
        total_disk_bytes = 0
        known_files: set[Path] = set()

        for a in assets:
            p = Path(a.storage_path)
            if not p.exists():
                alt_rec = rec_dir / a.filename
                alt_tts = tts_dir / a.filename
                if alt_rec.exists():
                    known_files.add(alt_rec.resolve())
                    total_disk_bytes += alt_rec.stat().st_size
                elif alt_tts.exists():
                    known_files.add(alt_tts.resolve())
                    total_disk_bytes += alt_tts.stat().st_size
                else:
                    missing_count += 1
            else:
                known_files.add(p.resolve())
                total_disk_bytes += p.stat().st_size

        # Orphaned files on disk not indexed in audio_assets table
        orphaned_count = 0
        for directory in [rec_dir, tts_dir]:
            if directory.exists():
                for f in directory.glob("*.wav"):
                    if f.resolve() not in known_files:
                        orphaned_count += 1

        failed_ops = session.query(SpeechOperation).filter_by(status="failed").count()
        completed_ops = session.query(SpeechOperation).filter_by(status="completed").count()

        return {
            "total_recording_sessions": total_sessions,
            "total_audio_assets": total_assets,
            "total_storage_bytes": total_disk_bytes,
            "total_storage_mb": round(total_disk_bytes / (1024 * 1024), 2),
            "successful_operations": completed_ops,
            "failed_operations": failed_ops,
            "missing_audio_files": missing_count,
            "orphaned_files": orphaned_count,
            "integrity_status": "HEALTHY" if missing_count == 0 else "WARNING",
            "storage_directories": [str(rec_dir), str(tts_dir)],
        }
    except Exception as exc:
        logger.error("Failed to compute storage diagnostics: %s", exc)
        return {
            "total_recording_sessions": 0,
            "total_audio_assets": 0,
            "total_storage_bytes": 0,
            "missing_audio_files": 0,
            "orphaned_files": 0,
            "integrity_status": "ERROR",
            "error": str(exc),
        }
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Backward Compatible Audit Functions
# ---------------------------------------------------------------------------

def record_stt_history(
    *,
    model: str,
    language: str,
    format: str,
    duration_sec: float | None,
    latency_sec: float,
    input_name: str,
    transcript: str,
    status: str = "completed",
    session_id: str | None = None,
    audio_filename: str | None = None,
    metadata: dict[str, Any] | None = None,
    db_url: str | None = None,
) -> int:
    """Records an STT transcription operation into history."""
    session = _get_db_session(db_url)
    try:
        rec = AudioHistoryRecord(
            kind="stt",
            session_id=session_id,
            model=model,
            language=language,
            format=format,
            duration_sec=duration_sec,
            latency_sec=round(latency_sec, 3),
            status=status,
            input_preview=input_name[:200] if input_name else "Uploaded Audio",
            output_preview=transcript[:500] if transcript else "(Empty transcript)",
            audio_filename=audio_filename,
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
        )
        session.add(rec)
        session.commit()
        rec_id = rec.id
        return rec_id
    except Exception as exc:
        session.rollback()
        logger.error("Failed to record STT history: %s", exc)
        return -1
    finally:
        session.close()


def record_tts_history(
    *,
    model: str,
    language: str,
    voice: str,
    text: str,
    duration_sec: float | None,
    latency_sec: float,
    audio_filename: str | None,
    status: str = "completed",
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    db_url: str | None = None,
) -> int:
    """Records a TTS synthesis operation into history."""
    session = _get_db_session(db_url)
    try:
        rec = AudioHistoryRecord(
            kind="tts",
            session_id=session_id,
            model=f"{model} ({voice})",
            language=language,
            format="WAV 16kHz Mono",
            duration_sec=duration_sec,
            latency_sec=round(latency_sec, 3),
            status=status,
            input_preview=text[:300] if text else "(Empty text)",
            output_preview=f"Synthesized {duration_sec:.1f}s speech" if duration_sec else "Synthesized speech",
            audio_filename=audio_filename,
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
        )
        session.add(rec)
        session.commit()
        rec_id = rec.id
        return rec_id
    except Exception as exc:
        session.rollback()
        logger.error("Failed to record TTS history: %s", exc)
        return -1
    finally:
        session.close()


def record_followup_history(
    *,
    customer_name: str,
    amount: int | None,
    due_date: str | None,
    ptp_date: str | None,
    concern: str,
    reminder_text: str,
    voice: str,
    audio_filename: str | None,
    duration_sec: float | None = None,
    latency_sec: float = 0.0,
    status: str = "completed",
    confirmed_by: str = "Operator (Verified)",
    metadata: dict[str, Any] | None = None,
    db_url: str | None = None,
) -> int:
    """Records a reviewed and confirmed Follow-up Desk action into persistent history."""
    session = _get_db_session(db_url)
    try:
        combined_meta = {
            "customer_name": customer_name,
            "amount": amount,
            "due_date": due_date,
            "ptp_date": ptp_date,
            "concern": concern,
            "confirmed_by": confirmed_by,
            **(metadata or {}),
        }
        amt_str = f"₹{amount:,.0f}" if amount is not None else "Not detected"
        due_str = due_date if due_date else "None"
        ptp_str = ptp_date if ptp_date else "None"

        rec = AudioHistoryRecord(
            kind="followup",
            session_id=f"flw_{int(time.time()*1000)}",
            model=f"Prisma v3.0 + Timbre ({voice})",
            language="hi-IN",
            format="WAV 16kHz Mono",
            duration_sec=duration_sec,
            latency_sec=round(latency_sec, 3),
            status=status,
            input_preview=f"{customer_name} | {amt_str} | Due: {due_str} | PTP: {ptp_str} | Concern: {concern[:40]}",
            output_preview=reminder_text[:300] if reminder_text else "(No reminder text)",
            audio_filename=audio_filename,
            metadata_json=json.dumps(combined_meta, ensure_ascii=False),
        )
        session.add(rec)
        session.commit()
        rec_id = rec.id
        return rec_id
    except Exception as exc:
        session.rollback()
        logger.error("Failed to record follow-up history: %s", exc)
        return -1
    finally:
        session.close()


def get_recent_history(
    limit: int = 50,
    kind: str | None = None,
    db_url: str | None = None,
) -> list[dict[str, Any]]:
    """Retrieves the most recent STT and TTS activity records."""
    session = _get_db_session(db_url)
    try:
        q = session.query(AudioHistoryRecord)
        if kind:
            q = q.filter_by(kind=kind)
        records = q.order_by(AudioHistoryRecord.id.desc()).limit(limit).all()

        results = []
        for r in records:
            meta = {}
            if r.metadata_json:
                try:
                    meta = json.loads(r.metadata_json)
                except Exception:
                    meta = {}

            ts_str = r.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC") if r.timestamp else ""
            results.append({
                "id": r.id,
                "kind": r.kind,
                "session_id": r.session_id,
                "timestamp": ts_str,
                "created_at": ts_str,
                "model": r.model,
                "model_or_voice": r.model,
                "voice": meta.get("voice", ""),
                "language": r.language,
                "format": r.format,
                "duration_sec": r.duration_sec,
                "latency_sec": r.latency_sec,
                "status": r.status,
                "input_preview": r.input_preview,
                "output_preview": r.output_preview,
                "audio_filename": r.audio_filename,
                "audio_url": f"/api/audio/{r.audio_filename}" if r.audio_filename else None,
                "metadata": meta,
            })
        return results
    except Exception as exc:
        logger.error("Failed to retrieve audio history: %s", exc)
        return []
    finally:
        session.close()


def clear_history(db_url: str | None = None) -> int:
    """Clears history records (for test isolation and privacy reset)."""
    session = _get_db_session(db_url)
    try:
        count = session.query(AudioHistoryRecord).delete()
        session.commit()
        return count
    except Exception as exc:
        session.rollback()
        logger.error("Failed to clear audio history: %s", exc)
        return 0
    finally:
        session.close()


def delete_history_item(history_id: int, db_url: str | None = None) -> bool:
    """Deletes an individual history entry and any attached unreferenced audio asset."""
    session = _get_db_session(db_url)
    try:
        rec = session.query(AudioHistoryRecord).filter_by(id=history_id).first()
        if not rec:
            return False
        if rec.session_id:
            delete_recording_session(rec.session_id, db_url=db_url)
        else:
            if rec.audio_filename:
                rec_dir, tts_dir = get_storage_dirs()
                for d in (rec_dir, tts_dir):
                    f = d / rec.audio_filename
                    if f.exists():
                        try:
                            f.unlink()
                        except Exception:
                            pass
            session.delete(rec)
            session.commit()
        return True
    except Exception as exc:
        session.rollback()
        logger.error("Failed to delete history item %s: %s", history_id, exc)
        return False
    finally:
        session.close()


def cleanup_old_temp_audio(temp_dir: Path, max_age_hours: int = 24) -> int:
    """Deletes temporary audio files older than max_age_hours."""
    if not temp_dir.exists():
        return 0
    count = 0
    now = time.time()
    cutoff = now - (max_age_hours * 3600)
    for p in temp_dir.glob("*.wav"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                count += 1
        except Exception:
            pass
    return count


def cleanup_storage_assets(
    data_dir: Path | None = None,
    max_age_hours: int = 24,
    prune_temp_only: bool = False,
    db_url: str | None = None,
) -> dict[str, Any]:
    """Prunes expired temporary files and unreferenced audio assets.

    Maintains database integrity while reclaiming disk storage.
    """
    data_dir = _resolve_data_dir(data_dir)

    temp_dir = data_dir / "temp"
    rec_dir = data_dir / "recordings"
    tts_dir = data_dir / "tts_audio"

    cleaned_temp = cleanup_old_temp_audio(temp_dir, max_age_hours=max_age_hours)
    cleaned_assets = 0
    freed_bytes = 0

    if not prune_temp_only and db_url is None:
        # Check for unreferenced files in recordings and tts_audio
        session = _get_db_session(db_url)
        try:
            active_filenames = set(
                row[0] for row in session.query(AudioAsset.filename).filter(AudioAsset.storage_status == "persisted").all()
            )
            now = time.time()
            cutoff = now - (max_age_hours * 3600)

            for target_dir in [rec_dir, tts_dir]:
                if not target_dir.exists():
                    continue
                for wav_path in target_dir.glob("*.wav"):
                    try:
                        # Only clean if older than cutoff AND not in active DB filenames
                        if wav_path.stat().st_mtime < cutoff and wav_path.name not in active_filenames:
                            f_size = wav_path.stat().st_size
                            wav_path.unlink()
                            cleaned_assets += 1
                            freed_bytes += f_size
                    except Exception:
                        pass
        except Exception as exc:
            logger.warning("Asset cleanup scan warning: %s", exc)
        finally:
            session.close()

    return {
        "status": "success",
        "cleaned_temp_files": cleaned_temp,
        "cleaned_asset_files": cleaned_assets,
        "total_files_removed": cleaned_temp + cleaned_assets,
        "freed_bytes": freed_bytes,
        "freed_mb": round(freed_bytes / (1024 * 1024), 3),
        "retention_hours": max_age_hours,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
