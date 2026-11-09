"""Audio history management and persistent audit logging for STT and TTS operations.

Maintains session logs, metadata, processing metrics, and safe cleanup policies
without storing private credentials or unbounded raw audio.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger("calllens.history")

Base = declarative_base()


class AudioHistoryRecord(Base):
    __tablename__ = "audio_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    kind = Column(String(16), nullable=False)  # 'stt' or 'tts'
    session_id = Column(String(64), nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    model = Column(String(32), nullable=False)
    language = Column(String(16), nullable=False)
    format = Column(String(32), nullable=True)
    duration_sec = Column(Float, nullable=True)
    latency_sec = Column(Float, nullable=False)
    status = Column(String(16), nullable=False, default="completed")  # 'completed' or 'failed'
    input_preview = Column(Text, nullable=True)
    output_preview = Column(Text, nullable=True)
    audio_filename = Column(String(256), nullable=True)
    metadata_json = Column(Text, nullable=True)


def _get_db_session(db_url: str | None = None):
    if db_url is None:
        data_dir = Path(os.getenv("DATA_DIR", "../calllens-data"))
        db_path = os.getenv("DATABASE_URL", f"sqlite:///{data_dir}/benchmark.db")
        db_url = db_path
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


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

            results.append({
                "id": r.id,
                "kind": r.kind,
                "session_id": r.session_id,
                "timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC") if r.timestamp else "",
                "model": r.model,
                "language": r.language,
                "format": r.format,
                "duration_sec": r.duration_sec,
                "latency_sec": r.latency_sec,
                "status": r.status,
                "input_preview": r.input_preview,
                "output_preview": r.output_preview,
                "audio_filename": r.audio_filename,
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
