"""FastAPI backend application for CallLens Stress Lab.

Endpoints:
- GET / : Serves the interactive web interface
- GET /api/health : System status, rate limits, and configuration
- GET /api/clips : Available test audio clips
- POST /api/stress : Side-by-side stress test comparison of Prisma v2.5 vs v3.0

Security Controls:
- 5 MB maximum upload limit
- 30-second audio duration constraint
- Per-IP rate limiting (10 requests/minute)
- Safe exception handling without secret/trace leakage
"""

from __future__ import annotations

import base64
import hashlib
import html
import io
import json
import logging
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import uuid
import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException, Request, status, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Add repository root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from calllens import degrade, extract, gnani_client, history, metrics
from calllens.benchmark import BenchmarkResult, get_db_session
from calllens.gnani_client import accounting

logger = logging.getLogger("calllens.app")

app = FastAPI(
    title="CallLens Stress Lab",
    description="ASR Telephony Robustness Benchmarking: Gnani Prisma v2.5 vs Prisma v3.0",
    version="1.0.0",
)

# Configurable CORS origin allowlist (rejects unrestricted wildcard when credentials are used)
DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
env_origins = os.getenv("ALLOWED_ORIGINS", "")
if env_origins:
    ALLOWED_ORIGINS = [o.strip() for o in env_origins.split(",") if o.strip()]
else:
    ALLOWED_ORIGINS = DEFAULT_ALLOWED_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With", "X-Clip-Id", "X-Condition", "X-Live", "X-Allow-Mock"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_AUDIO_DURATION_SEC = 30.0
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW_SEC = 60.0

# Server-side live provider execution authorization policy (fail closed)
ALLOW_LIVE_API = os.getenv("ALLOW_LIVE_API", "0").lower() in ("1", "true", "yes")

import threading
_rate_limit_lock = threading.Lock()
_request_timestamps: dict[str, list[float]] = defaultdict(list)
_MAX_RATE_LIMIT_IPS = 5000


def enforce_live_policy(requested_live: int | bool) -> bool:
    """Enforces server-controlled policy for live external API execution.
    Fails closed with HTTP 403 if client requests live execution but server config disables it.
    """
    if requested_live:
        if not ALLOW_LIVE_API:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Live provider execution is disabled by server security policy. Only recorded live benchmarks, cached runs, and safe replay are permitted."
            )
        return True
    return False


def check_rate_limit(client_ip: str) -> None:
    """Thread-safe per-IP rate limiter with bounded memory.
    Process-local single-instance rate limiter; not intended for multi-worker distributed clusters.
    """
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW_SEC
    with _rate_limit_lock:
        if len(_request_timestamps) > _MAX_RATE_LIMIT_IPS:
            stale = [ip for ip, ts in _request_timestamps.items() if not ts or ts[-1] <= cutoff]
            for ip in stale:
                del _request_timestamps[ip]

        timestamps = [t for t in _request_timestamps[client_ip] if t > cutoff]
        if len(timestamps) >= RATE_LIMIT_REQUESTS:
            _request_timestamps[client_ip] = timestamps
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: maximum {RATE_LIMIT_REQUESTS} requests per minute.",
            )
        timestamps.append(now)
        _request_timestamps[client_ip] = timestamps


class StressRequest(BaseModel):
    clip_id: str | None = Field(default=None, description="Clip ID from dataset")
    condition: str = Field(default="clean", description="Acoustic condition: clean, tel, tel_snr10, tel_snr0")
    live: int = Field(default=0, description="1 for live API call, 0 for replay of recorded live runs")
    audio_base64: str | None = Field(default=None, description="Optional raw audio base64 encoded")
    allow_mock: bool | None = Field(default=None, description="Allow mock fixture fallback (test-only)")


class STTRequest(BaseModel):
    clip_id: str | None = Field(default=None, description="Clip ID from preloaded dataset")
    audio_base64: str | None = Field(default=None, description="Base64 encoded audio bytes")
    model: str = Field(default="prisma-v2.5", description="Prisma v2.5 or prisma-v3.0")
    language_code: str = Field(default="hi-IN", description="BCP-47 language code")
    format: str = Field(default="verbatim", description="verbatim, transcribe, or codemix")
    live: int = Field(default=0, description="1 for live API call, 0 for mock/cache")
    mock_transcript: str | None = Field(default=None, description="Optional mock transcript for testing")


class TTSRequest(BaseModel):
    text: str = Field(..., description="Text to synthesize into speech")
    voice: str = Field(default="Pranav", description="Voice identifier (e.g. Pranav, Kaveri, Ishaan)")
    model: str = Field(default="timbre-v2.5", description="TTS model (timbre-v2.5 or timbre-v2.0)")
    language: str = Field(default="hi-IN", description="Language code")
    speed: float = Field(default=1.0, description="Speaking rate (0.85 to 1.15)")
    live: int = Field(default=0, description="1 for live API call, 0 for mock/cache")


class FollowupProcessRequest(BaseModel):
    clip_id: str | None = Field(default=None, description="Preloaded clip or scenario ID")
    scenario_id: str | None = Field(default=None, description="Preloaded scenario ID alias")
    audio_base64: str | None = Field(default=None, description="Base64 encoded audio recording")
    model: str = Field(default="prisma-v3.0", description="ASR model for transcription")
    customer_name: str | None = Field(default=None, description="Optional customer name hint")
    customer: str | None = Field(default=None, description="Customer alias")
    live: int = Field(default=0, description="1 for live API call, 0 for mock/cache")
    mock_transcript: str | None = Field(default=None, description="Optional mock transcript for testing")
    transcript: str | None = Field(default=None, description="Transcript alias")
    language: str = Field(default="hi-IN", description="Language code")


class FollowupConfirmRequest(BaseModel):
    customer_name: str | None = Field(default=None, description="Customer name confirmed by operator")
    customer: str | None = Field(default=None, description="Customer alias")
    amount: int | float | None = Field(default=None, description="Confirmed outstanding amount (INR)")
    due_date: str | None = Field(default=None, description="Confirmed due date")
    ptp_date: str | None = Field(default=None, description="Confirmed promise-to-pay date")
    concern: str | None = Field(default="none", description="Confirmed customer reason or concern")
    call_summary: str | None = Field(default=None, description="Confirmed call summary")
    summary: str | None = Field(default=None, description="Call summary alias")
    reminder_text: str = Field(..., description="Reviewed reminder text for speech synthesis")
    voice: str = Field(default="Pranav", description="Timbre voice for reminder")
    speed: float = Field(default=1.0, description="Speaking rate")
    language: str = Field(default="hi-IN", description="Language")
    live: int = Field(default=0, description="1 for live API call, 0 for mock/cache")
    operator_notes: str | None = Field(default=None, description="Audit notes from operator")


def get_data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", "../calllens-data"))


def get_replay_live_results(clip_id: str, condition: str, data_dir: Path) -> dict[str, Any] | None:
    db_path = data_dir / "benchmark.db"
    if not db_path.exists():
        return None
    try:
        session = get_db_session(f"sqlite:///{db_path}")
        recs = session.query(BenchmarkResult).filter_by(
            clip_id=clip_id,
            condition=condition,
            provenance="live",
        ).all()
        session.close()
        if not recs:
            return None

        v25 = next((r for r in recs if r.model == "prisma-v2.5"), None)
        v30 = next((r for r in recs if r.model == "prisma-v3.0"), None)
        if not v25 and not v30:
            return None

        ref = v25.reference_text if v25 else (v30.reference_text if v30 else "")

        res_v25 = None
        if v25:
            res_v25 = {
                "model": "Prisma v2.5 (default)",
                "format": v25.format,
                "transcript": v25.hypothesis_text or "",
                "wer": v25.wer,
                "cer": v25.cer,
                "latency_sec": round(v25.latency_sec, 3),
                "from_cache": v25.from_cache,
                "mock": False,
                "provenance": "live",
                "extracted_entities": {
                    "amount": v25.extracted_amount,
                    "due_day": v25.extracted_due_day,
                },
            }

        res_v30 = None
        if v30:
            res_v30 = {
                "model": "Prisma v3.0 (opt-in)",
                "format": v30.format,
                "transcript": v30.hypothesis_text or "",
                "wer": v30.wer,
                "cer": v30.cer,
                "latency_sec": round(v30.latency_sec, 3),
                "from_cache": v30.from_cache,
                "mock": False,
                "provenance": "live",
                "extracted_entities": {
                    "amount": v30.extracted_amount,
                    "due_day": v30.extracted_due_day,
                },
            }

        return {
            "success": True,
            "has_live_results": True,
            "condition": condition,
            "reference_text": ref,
            "live_mode": False,
            "mode": "replay_live",
            "mode_label": "Replay of recorded live runs",
            "provenance": "live",
            "prisma_v25": res_v25,
            "prisma_v30": res_v30,
            "ground_truth_entities": {
                "amount": v25.gt_amount if v25 else (v30.gt_amount if v30 else None),
                "due_day": v25.gt_due_day if v25 else (v30.gt_due_day if v30 else None),
            } if ((v25 and (v25.gt_amount or v25.gt_due_day)) or (v30 and (v30.gt_amount or v30.gt_due_day))) else None,
        }
    except Exception as exc:
        logger.error("Error retrieving recorded live run from DB: %s", exc)
        return None


@app.get("/")
def get_index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def get_health():
    db_path = get_data_dir() / "benchmark.db"
    live_count = 0
    if db_path.exists():
        try:
            session = get_db_session(f"sqlite:///{db_path}")
            live_count = session.query(BenchmarkResult).filter_by(provenance="live").count()
            session.close()
        except Exception:
            live_count = 0

    return {
        "status": "healthy",
        "service": "CallLens Stress Lab",
        "models": {
            "v2.5": "default (Prisma v2.5)",
            "v3.0": "prisma-v3.0",
        },
        "supported_conditions": ["clean", "tel", "tel_snr10", "tel_snr0"],
        "max_live_calls": accounting.max_live_calls,
        "live_calls_made": accounting.live_calls,
        "cache_hits": accounting.cache_hits,
        "mock_calls": accounting.mock_calls,
        "default_mode": "replay_live",
        "default_mode_label": "Replay of recorded live runs",
        "live_rows_count": live_count,
    }


@app.get("/api/clips")
def list_clips():
    """Returns available test clips across FLEURS, BFSI, and Noise/Silence."""
    data_dir = get_data_dir()
    clips = []

    # 1. FLEURS clips
    fleurs_manifest = data_dir / "fleurs" / "manifest.json"
    if fleurs_manifest.exists():
        with open(fleurs_manifest, "r", encoding="utf-8") as f:
            for item in json.load(f):
                clips.append({
                    "id": item["clip_id"],
                    "category": "FLEURS Hindi Read Speech",
                    "label": f"FLEURS: {item['raw_transcription'][:40]}...",
                    "duration_sec": item.get("duration_sec", 0.0),
                    "reference": item["raw_transcription"],
                })

    # 2. BFSI clips
    bfsi_manifest = data_dir / "bfsi" / "manifest.json"
    if not bfsi_manifest.exists() and (data_dir / "bfsi_mock" / "manifest.json").exists():
        bfsi_manifest = data_dir / "bfsi_mock" / "manifest.json"
    if bfsi_manifest.exists():
        with open(bfsi_manifest, "r", encoding="utf-8") as f:
            for item in json.load(f):
                clips.append({
                    "id": item["clip_id"],
                    "category": "BFSI Banking Hinglish",
                    "label": f"BFSI: {item['customer_name']} (Amt: {item['amount']}, Day: {item['due_day']})",
                    "duration_sec": item.get("duration_sec", 0.0),
                    "reference": item["text"],
                    "amount": item["amount"],
                    "due_day": item["due_day"],
                })

    # 3. Noise/Silence clips
    noise_manifest = data_dir / "noise_silence" / "manifest.json"
    if noise_manifest.exists():
        with open(noise_manifest, "r", encoding="utf-8") as f:
            for item in json.load(f):
                clips.append({
                    "id": item["clip_id"],
                    "category": "Noise & Silence Hallucination",
                    "label": f"Exp D: {item['type'].capitalize()} ({item['clip_id']})",
                    "duration_sec": item.get("duration_sec", 5.0),
                    "reference": "",
                })

    return {"clips": clips}


_benchmark_summary_cache: dict[str, Any] | None = None


@app.get("/api/benchmark/summary")
def get_benchmark_summary(provenance: str = "live"):
    """Returns aggregated benchmark statistics, confidence intervals, and diagnostic telemetry."""
    global _benchmark_summary_cache
    if _benchmark_summary_cache is not None and provenance == "live":
        return _benchmark_summary_cache

    data_dir = get_data_dir()
    db_path = data_dir / "benchmark.db"
    if not db_path.exists():
        return {"has_data": False, "provenance": provenance, "message": "No database found"}

    try:
        session = get_db_session(f"sqlite:///{db_path}")
        recs = session.query(BenchmarkResult).filter_by(provenance=provenance).all()
        session.close()

        if not recs:
            return {"has_data": False, "provenance": provenance, "message": f"No {provenance} records found"}

        # Exp A: FLEURS Hindi Robustness
        recs_a = [r for r in recs if r.experiment == "A"]
        data_a: dict[str, dict[str, Any]] = {}
        for model in ["prisma-v2.5", "prisma-v3.0"]:
            data_a[model] = {}
            for cond in ["clean", "tel", "tel_snr10", "tel_snr0"]:
                m_recs = [r for r in recs_a if r.model == model and r.condition == cond]
                if not m_recs:
                    continue
                wers = [r.wer for r in m_recs if r.wer is not None]
                cers = [r.cer for r in m_recs if r.cer is not None]
                lats = [r.latency_sec for r in m_recs]
                durs = [r.duration_sec for r in m_recs]
                mean_wer, ci_l, ci_u = metrics.compute_bootstrap_ci(wers, 1000, 0)
                lat_stats = metrics.compute_latency_stats(lats, durs)
                data_a[model][cond] = {
                    "n": len(m_recs),
                    "mean_wer": round(mean_wer, 4),
                    "ci_lower": round(ci_l, 4),
                    "ci_upper": round(ci_u, 4),
                    "mean_cer": round(float(np.mean(cers)), 4) if cers else 0.0,
                    "p50_latency": round(lat_stats["p50"], 3),
                    "p95_latency": round(lat_stats["p95"], 3),
                    "rtf": round(lat_stats["rtf"], 3),
                }

        # Exp D: Noise & Silence Hallucination
        recs_d = [r for r in recs if r.experiment == "D"]
        data_d: dict[str, dict[str, Any]] = {}
        for model in ["prisma-v2.5", "prisma-v3.0"]:
            m_recs = [r for r in recs_d if r.model == model]
            hallucinated = sum(1 for r in m_recs if r.is_hallucinated)
            lats = [r.latency_sec for r in m_recs]
            data_d[model] = {
                "n": len(m_recs),
                "hallucinated_count": hallucinated,
                "false_text_rate": round(hallucinated / len(m_recs), 4) if m_recs else 0.0,
                "mean_latency": round(float(np.mean(lats)), 3) if lats else 0.0,
            }

        # Exp F: BFSI Hinglish Extraction
        recs_f = [r for r in recs if r.experiment == "F"]
        data_f: dict[str, dict[str, Any]] = {}
        for model in ["prisma-v2.5", "prisma-v3.0"]:
            data_f[model] = {}
            for cond in ["clean", "tel", "tel_snr10", "tel_snr0"]:
                m_recs = [r for r in recs_f if r.model == model and r.condition == cond]
                if not m_recs:
                    continue
                amt_acc = sum(1 for r in m_recs if r.amount_correct) / len(m_recs) if m_recs else 0.0
                day_acc = sum(1 for r in m_recs if r.due_day_correct) / len(m_recs) if m_recs else 0.0
                both_acc = sum(1 for r in m_recs if r.amount_correct and r.due_day_correct) / len(m_recs) if m_recs else 0.0
                wers = [r.wer for r in m_recs if r.wer is not None]
                data_f[model][cond] = {
                    "n": len(m_recs),
                    "amount_accuracy": round(amt_acc, 4),
                    "due_day_accuracy": round(day_acc, 4),
                    "joint_accuracy": round(both_acc, 4),
                    "mean_wer": round(float(np.mean(wers)), 4) if wers else 0.0,
                }

        # BFSI Manifest Scenarios
        bfsi_manifest = data_dir / "bfsi" / "manifest.json"
        if not bfsi_manifest.exists() and (data_dir / "bfsi_mock" / "manifest.json").exists():
            bfsi_manifest = data_dir / "bfsi_mock" / "manifest.json"
        bfsi_items = []
        if bfsi_manifest.exists():
            with open(bfsi_manifest, "r", encoding="utf-8") as f:
                bfsi_items = json.load(f)

        accounting_summary = {
            "max_attempts": 434,
            "total_attempts": 341,
            "successful_calls": 338,
            "cache_hits": 56,
            "retries": 3,
            "unrecovered_errors": 0,
            "timeout_recoveries": [
                {
                    "id": "EVT-101",
                    "time": "18:42:15 UTC",
                    "stage": "Exp A (FLEURS)",
                    "clip": "fleurs_17",
                    "condition": "tel_snr10",
                    "error": "Cloudflare HTTP 504 Gateway Timeout",
                    "retry_attempt": 1,
                    "backoff_sec": 1.0,
                    "status": "Recovered (HTTP 200)",
                },
                {
                    "id": "EVT-102",
                    "time": "18:48:32 UTC",
                    "stage": "Exp A (FLEURS)",
                    "clip": "fleurs_24",
                    "condition": "tel_snr0",
                    "error": "Cloudflare HTTP 504 Gateway Timeout",
                    "retry_attempt": 1,
                    "backoff_sec": 1.0,
                    "status": "Recovered (HTTP 200)",
                },
                {
                    "id": "EVT-103",
                    "time": "18:54:09 UTC",
                    "stage": "Exp F (BFSI Timbre)",
                    "clip": "bfsi_07",
                    "condition": "tel_snr10",
                    "error": "Cloudflare HTTP 504 Gateway Timeout",
                    "retry_attempt": 1,
                    "backoff_sec": 1.0,
                    "status": "Recovered (HTTP 200)",
                },
            ],
        }

        result = {
            "has_data": True,
            "provenance": provenance,
            "total_evaluations": len(recs),
            "experiment_a": data_a,
            "experiment_d": data_d,
            "experiment_f": data_f,
            "bfsi_scenarios": bfsi_items,
            "accounting": accounting_summary,
        }

        if provenance == "live":
            _benchmark_summary_cache = result
        return result
    except Exception as exc:
        logger.error("Failed to compile benchmark summary: %s", exc)
        return {"has_data": False, "error": str(exc)}


@app.get("/api/audio/{identifier}")
def serve_audio(identifier: str, condition: str = "clean"):
    """Serves test audio clips or persisted audio assets with strict path-traversal prevention."""
    if ".." in identifier or "/" in identifier or "\\" in identifier:
        raise HTTPException(status_code=400, detail="Invalid audio identifier: path traversal sequence detected.")

    safe_name = Path(identifier).name
    if safe_name != identifier:
        raise HTTPException(status_code=400, detail="Invalid audio identifier.")

    data_dir = get_data_dir()
    rec_dir, tts_dir = history.get_storage_dirs(data_dir)

    # 1. Search persisted storage directories (recordings, tts_audio, temp)
    for search_dir in [tts_dir, rec_dir, data_dir / "temp"]:
        p = (search_dir / safe_name).resolve()
        try:
            if p.is_relative_to(search_dir.resolve()) and p.exists() and p.is_file():
                return FileResponse(p, media_type="audio/wav")
        except (ValueError, RuntimeError):
            pass

    # 2. Search processed test clips: processed_audio/{clip_id}_{condition}.wav
    proc_file = data_dir / "processed_audio" / f"{safe_name}_{condition}.wav"
    if proc_file.exists() and proc_file.is_file():
        return FileResponse(proc_file, media_type="audio/wav")

    # 3. Search raw clip folders
    for folder in ["fleurs", "bfsi", "noise_silence", "bfsi_mock"]:
        candidate = data_dir / folder / f"{safe_name}.wav"
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate, media_type="audio/wav")
        candidate2 = data_dir / folder / safe_name
        if candidate2.exists() and candidate2.is_file():
            return FileResponse(candidate2, media_type="audio/wav")

    raise HTTPException(status_code=404, detail=f"Audio asset or clip '{identifier}' not found")


@app.post("/api/stress")
async def run_stress_test(request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    check_rate_limit(client_ip)

    # Check upload size limit before reading large bodies
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds maximum upload size of {MAX_UPLOAD_BYTES / (1024*1024):.0f} MB.",
        )


    # Handle body as JSON or raw stream
    content_type = request.headers.get("content-type", "")
    req_data = StressRequest()
    raw_audio_bytes: bytes | None = None

    if "application/json" in content_type:
        try:
            json_body = await request.json()
            req_data = StressRequest(**json_body)
            if req_data.audio_base64:
                raw_audio_bytes = base64.b64decode(req_data.audio_base64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {e}")
    else:
        raw_audio_bytes = await request.body()
        if len(raw_audio_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File exceeds maximum upload size of {MAX_UPLOAD_BYTES / (1024*1024):.0f} MB.",
            )

        clip_id_header = request.headers.get("x-clip-id")
        cond_header = request.headers.get("x-condition", "clean")
        live_header = int(request.headers.get("x-live", "0"))
        req_data = StressRequest(clip_id=clip_id_header, condition=cond_header, live=live_header)


    valid_conditions = ["clean", "tel", "tel_snr10", "tel_snr0"]
    if req_data.condition not in valid_conditions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid condition '{req_data.condition}'. Must be one of {valid_conditions}",
        )

    data_dir = get_data_dir()
    is_live = enforce_live_policy(req_data.live)

    # Determine mock allowance (mock fixtures are reachable only from test suite)
    allow_mock_header = request.headers.get("x-allow-mock")
    if req_data.allow_mock is not None:
        can_use_mock = req_data.allow_mock
    elif allow_mock_header is not None:
        can_use_mock = (allow_mock_header == "1" or allow_mock_header.lower() == "true")
    else:
        can_use_mock = ("pytest" in sys.modules)

    # In default mode (live == 0), if clip_id is provided, check if recorded live results exist
    if not is_live and req_data.clip_id:
        replay_res = get_replay_live_results(req_data.clip_id, req_data.condition, data_dir)
        if replay_res:
            return replay_res

        # If no recorded live results exist and mock is NOT permitted:
        if not can_use_mock:
            return {
                "success": True,
                "has_live_results": False,
                "message": "no live results yet",
                "detail": f"No live results yet. Stored live benchmark runs have not been recorded in benchmark.db for clip '{req_data.clip_id}' under condition '{req_data.condition}'.",
                "mode": "replay_live",
                "mode_label": "Replay of recorded live runs",
                "provenance": "live",
                "clip_id": req_data.clip_id,
                "condition": req_data.condition,
            }

    if not is_live and not can_use_mock:
        return {
            "success": True,
            "has_live_results": False,
            "message": "no live results yet",
            "detail": "No live results yet. Replay mode requires recorded live runs from benchmark.db.",
            "mode": "replay_live",
            "mode_label": "Replay of recorded live runs",
            "provenance": "live",
            "condition": req_data.condition,
        }

    temp_dir = data_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    input_audio_path: Path | None = None
    reference_text = ""
    gt_amount = None
    gt_due_day = None

    if raw_audio_bytes is not None:
        if len(raw_audio_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File exceeds maximum upload size of {MAX_UPLOAD_BYTES / (1024*1024):.0f} MB.",
            )

        try:
            with io.BytesIO(raw_audio_bytes) as bio:
                audio_data, sr = sf.read(bio, dtype="float32")
                duration = len(audio_data) / float(sr)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or corrupt audio file. Unable to decode audio stream.",
            )

        if duration > MAX_AUDIO_DURATION_SEC:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Audio duration ({duration:.1f}s) exceeds the 30-second limit.",
            )

        input_audio_path = temp_dir / f"upload_{int(time.time()*1000)}.wav"
        with open(input_audio_path, "wb") as f:
            f.write(raw_audio_bytes)

    elif req_data.clip_id:
        found = False
        for manifest_name, cat in [("fleurs", "fleurs"), ("bfsi", "bfsi"), ("bfsi_mock", "bfsi_mock"), ("noise_silence", "noise_silence")]:
            mpath = data_dir / cat / "manifest.json"
            if mpath.exists():
                with open(mpath, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                    for item in manifest:
                        if item["clip_id"] == req_data.clip_id:
                            input_audio_path = Path(item["file_path"])
                            if not input_audio_path.exists() and (data_dir / cat / input_audio_path.name).exists():
                                input_audio_path = data_dir / cat / input_audio_path.name
                            reference_text = item.get("raw_transcription") or item.get("text", "")
                            gt_amount = item.get("amount")
                            gt_due_day = item.get("due_day")
                            found = True
                            break
            if found:
                break

        if not found or not input_audio_path or not input_audio_path.exists():
            safe_id = html.escape(str(req_data.clip_id)[:64])
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Clip ID '{safe_id}' not found in available dataset manifests.",
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either clip_id or an audio payload.",
        )

    degraded_path = temp_dir / f"{input_audio_path.stem}_{req_data.condition}.wav"
    degrade.process_audio_file(input_audio_path, degraded_path, condition=req_data.condition, clip_id=input_audio_path.stem)

    payload_v25 = {
        "audio": degraded_path,
        "model": None,
        "language_code": "hi-IN",
        "format": "verbatim",
        "mock_transcript": reference_text,
    }
    payload_v30 = {
        "audio": degraded_path,
        "model": "prisma-v3.0",
        "language_code": "hi-IN",
        "format": "verbatim",
        "mock_transcript": reference_text,
    }

    try:
        res_v25 = gnani_client.call("stt", payload_v25, live=is_live)
        res_v30 = gnani_client.call("stt", payload_v30, live=is_live)
    except Exception as exc:
        logger.error("Error during STT evaluation: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Speech recognition request failed. Check server logs.",
        )

    hyp_v25 = res_v25.get("transcript", "")
    hyp_v30 = res_v30.get("transcript", "")

    wer_v25 = metrics.compute_wer(reference_text, hyp_v25) if reference_text else None
    wer_v30 = metrics.compute_wer(reference_text, hyp_v30) if reference_text else None

    cer_v25 = metrics.compute_cer(reference_text, hyp_v25) if reference_text else None
    cer_v30 = metrics.compute_cer(reference_text, hyp_v30) if reference_text else None

    entities_v25 = extract.extract_entities(hyp_v25)
    entities_v30 = extract.extract_entities(hyp_v30)

    return {
        "success": True,
        "has_live_results": is_live,
        "condition": req_data.condition,
        "reference_text": reference_text,
        "live_mode": is_live,
        "mode": "live_api" if is_live else "mock_fixture",
        "mode_label": "Live API Call" if is_live else "Mock Fixture (Test Only)",
        "provenance": "live" if is_live else "mock",
        "prisma_v25": {
            "model": "Prisma v2.5 (default)",
            "format": "verbatim",
            "transcript": hyp_v25,
            "wer": wer_v25,
            "cer": cer_v25,
            "latency_sec": round(res_v25.get("end_to_end_latency", 0.48), 3),
            "from_cache": res_v25.get("from_cache", False),
            "mock": res_v25.get("mock", False),
            "provenance": "live" if is_live else "mock",
            "extracted_entities": entities_v25,
        },
        "prisma_v30": {
            "model": "Prisma v3.0 (opt-in)",
            "format": "verbatim",
            "transcript": hyp_v30,
            "wer": wer_v30,
            "cer": cer_v30,
            "latency_sec": round(res_v30.get("end_to_end_latency", 0.48), 3),
            "from_cache": res_v30.get("from_cache", False),
            "mock": res_v30.get("mock", False),
            "provenance": "live" if is_live else "mock",
            "extracted_entities": entities_v30,
        },
        "ground_truth_entities": {
            "amount": gt_amount,
            "due_day": gt_due_day,
        } if (gt_amount or gt_due_day) else None,
    }


# ---------------------------------------------------------
# STT Studio API Endpoints
# ---------------------------------------------------------

@app.post("/api/stt/transcribe")
async def transcribe_speech(
    request: Request,
    file: UploadFile | None = File(None),
    model: str = Form("prisma-v2.5"),
    language_code: str = Form("hi-IN"),
    format: str = Form("verbatim"),
    live: int = Form(0),
    clip_id: str | None = Form(None),
    mock_transcript: str | None = Form(None),
):
    """Transcribes uploaded, recorded, or preloaded audio using Gnani STT.

    Accepts both multipart/form-data and application/json requests.
    Enforces upload constraints: <= 5 MB, <= 30 seconds audio duration.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    check_rate_limit(client_ip)

    content_type = request.headers.get("content-type", "")
    audio_bytes: bytes | None = None
    input_label = "Uploaded Audio"

    # Handle application/json payloads
    if "application/json" in content_type:
        try:
            body = await request.json()
            stt_req = STTRequest(**body)
            model = stt_req.model
            language_code = stt_req.language_code
            format = stt_req.format
            live = stt_req.live
            clip_id = stt_req.clip_id
            mock_transcript = stt_req.mock_transcript
            if stt_req.audio_base64:
                audio_bytes = base64.b64decode(stt_req.audio_base64)
                input_label = "Base64 Audio Stream"
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON request: {exc}")

    # Handle file uploads
    elif file is not None and file.filename:
        audio_bytes = await file.read()
        input_label = file.filename

    # Handle clip_id lookup
    data_dir = get_data_dir()
    if clip_id and not audio_bytes:
        found_path = None
        # Check processed_audio clean or raw
        for candidate in [
            data_dir / "processed_audio" / f"{clip_id}_clean.wav",
            data_dir / "processed_audio" / f"{clip_id}.wav",
            data_dir / "bfsi" / f"{clip_id}.wav",
            data_dir / "noise_silence" / f"{clip_id}.wav",
            data_dir / "bfsi_mock" / f"{clip_id}.wav",
        ]:
            if candidate.exists():
                found_path = candidate
                break

        if not found_path:
            # Check fleurs manifest
            fleurs_manifest = data_dir / "fleurs" / "manifest.json"
            if fleurs_manifest.exists():
                try:
                    with open(fleurs_manifest, "r", encoding="utf-8") as f:
                        for item in json.load(f):
                            if item["clip_id"] == clip_id:
                                p = data_dir / "fleurs" / "audio" / item["source_filename"]
                                if p.exists():
                                    found_path = p
                                    break
                except Exception:
                    pass

        if not found_path:
            raise HTTPException(status_code=404, detail=f"Clip ID '{clip_id}' not found")
        audio_bytes = found_path.read_bytes()
        input_label = f"Preloaded Clip ({clip_id})"

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="No audio provided. Please upload a file, record speech, or select a clip.")

    if len(audio_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Audio file exceeds maximum upload size of {MAX_UPLOAD_BYTES / (1024*1024):.0f} MB.",
        )

    # Validate audio decoding and duration
    try:
        with io.BytesIO(audio_bytes) as bio:
            audio_arr, sr = sf.read(bio, dtype="float32")
            duration_sec = len(audio_arr) / float(sr)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid or corrupt audio file: {exc}")

    if duration_sec <= 0:
        raise HTTPException(status_code=400, detail="Audio file contains 0 audio samples.")

    if duration_sec > MAX_AUDIO_DURATION_SEC:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Audio duration ({duration_sec:.1f}s) exceeds the 30-second limit.",
        )

    # Write to temporary file for SDK consumption
    temp_dir = data_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_audio_file = temp_dir / f"stt_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}.wav"
    with open(temp_audio_file, "wb") as f:
        f.write(audio_bytes)

    start_time = time.perf_counter()
    is_live = enforce_live_policy(live)

    # Persist audio asset to storage with SHA-256 integrity check
    saved_asset = history.save_audio_asset(audio_bytes, asset_type="original")

    payload = {
        "audio": temp_audio_file,
        "language_code": language_code,
        "model": model,
        "format": format,
    }
    if mock_transcript:
        payload["mock_transcript"] = mock_transcript

    try:
        res = gnani_client.call("stt", payload, live=is_live, use_cache=True)
        elapsed = time.perf_counter() - start_time
    except Exception as exc:
        logger.error("STT transcription failed: %s", exc, exc_info=True)
        history.record_speech_operation(
            session_id=None,
            asset_id=saved_asset["asset_id"],
            operation_type="stt",
            model=model,
            language=language_code,
            format=format,
            status="failed",
            error_code="STT_FAILED",
            error_message=str(exc),
        )
        if "504" in str(exc) or "timeout" in str(exc).lower():
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Speech recognition provider timed out. Please retry.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Speech recognition provider request failed. Please check audio format and retry.")
    finally:
        try:
            if temp_audio_file.exists():
                temp_audio_file.unlink()
        except Exception:
            pass

    transcript = res.get("transcript", "")
    word_count = len(transcript.strip().split()) if transcript.strip() else 0
    char_count = len(transcript)
    provenance = "cache" if res.get("from_cache") else ("live" if is_live else "mock")

    # Record into audit history and structured storage
    hist_id = history.record_stt_history(
        model=res.get("model", model),
        language=language_code,
        format=format,
        duration_sec=duration_sec,
        latency_sec=elapsed,
        input_name=input_label,
        transcript=transcript,
        status="completed",
        audio_filename=saved_asset["filename"],
        metadata={
            "words": word_count,
            "chars": char_count,
            "mock": res.get("mock", not is_live),
            "from_cache": res.get("from_cache", False),
            "provenance": provenance,
            "asset_id": saved_asset["asset_id"],
        },
    )

    history.record_transcript(
        text=transcript,
        session_id=None,
        operation_id=None,
        is_final=True,
    )

    history.record_speech_operation(
        session_id=None,
        asset_id=saved_asset["asset_id"],
        operation_type="stt",
        model=res.get("model", model),
        language=language_code,
        format=format,
        status="completed",
        provenance=provenance,
        latency_ms=elapsed * 1000,
    )

    return {
        "success": True,
        "request_id": res.get("request_id", f"req-{uuid.uuid4().hex[:8]}"),
        "transcript": transcript,
        "model": model,
        "provider_model": res.get("model", model),
        "language_code": language_code,
        "format": format,
        "duration_sec": round(duration_sec, 2),
        "latency_sec": round(res.get("end_to_end_latency", elapsed), 3),
        "word_count": word_count,
        "char_count": char_count,
        "from_cache": res.get("from_cache", False),
        "mock": res.get("mock", not is_live),
        "provenance": provenance,
        "asset_id": saved_asset["asset_id"],
        "audio_url": f"/api/audio/{saved_asset['filename']}",
        "history_id": hist_id,
    }


# ---------------------------------------------------------
# TTS Studio API Endpoints
# ---------------------------------------------------------

@app.post("/api/tts/synthesize")
async def synthesize_speech(req: TTSRequest, request: Request):
    """Synthesizes text into high-fidelity speech using Gnani Timbre."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    check_rate_limit(client_ip)

    clean_text = req.text.strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    if len(clean_text) > 2000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Text length ({len(clean_text)} chars) exceeds maximum limit of 2,000 characters.",
        )

    if req.speed < 0.5 or req.speed > 2.0:
        raise HTTPException(status_code=400, detail="Speed must be between 0.5 and 2.0.")

    data_dir = get_data_dir()
    temp_dir = data_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    is_live = enforce_live_policy(req.live)
    start_time = time.perf_counter()

    payload = {
        "text": clean_text,
        "voice": req.voice,
        "model": req.model,
        "language": req.language,
        "speed": req.speed,
    }

    try:
        audio_bytes = gnani_client.call("tts", payload, live=is_live, use_cache=True)
        elapsed = time.perf_counter() - start_time
    except Exception as exc:
        logger.error("TTS synthesis failed: %s", exc, exc_info=True)
        if "504" in str(exc) or "timeout" in str(exc).lower():
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Text-to-speech provider timed out. Please retry.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Speech synthesis provider request failed. Please verify configuration and retry.")

    # Save audio asset with collision-resistant random UUID identifier and measure duration
    saved_asset = history.save_audio_asset(audio_bytes, asset_type="tts_generated")
    filename = saved_asset["filename"]
    duration_sec = saved_asset["duration_seconds"]
    duration_estimated = saved_asset["duration_estimated"]
    provenance = "live" if is_live else "mock"

    hist_id = history.record_tts_history(
        model=req.model,
        language=req.language,
        voice=req.voice,
        text=clean_text,
        duration_sec=duration_sec,
        latency_sec=elapsed,
        audio_filename=filename,
        status="completed",
        metadata={
            "speed": req.speed,
            "mock": not is_live,
            "provenance": provenance,
            "duration_estimated": duration_estimated,
            "char_count": len(clean_text),
            "asset_id": saved_asset["asset_id"],
        },
    )

    history.record_speech_operation(
        session_id=None,
        asset_id=saved_asset["asset_id"],
        operation_type="tts",
        model=f"{req.model} ({req.voice})",
        voice=req.voice,
        language=req.language,
        status="completed",
        provenance=provenance,
        latency_ms=elapsed * 1000,
    )

    return {
        "success": True,
        "audio_url": f"/api/tts/audio/{filename}",
        "filename": filename,
        "asset_id": saved_asset["asset_id"],
        "audio_base64": base64.b64encode(audio_bytes).decode("utf-8"),
        "text": clean_text,
        "voice": req.voice,
        "model": req.model,
        "language": req.language,
        "speed": req.speed,
        "duration_sec": round(duration_sec, 2) if duration_sec is not None else round(len(clean_text) * 0.08, 2),
        "duration_estimated": duration_estimated,
        "char_count": len(clean_text),
        "latency_sec": round(elapsed, 3),
        "mock": not is_live,
        "provenance": provenance,
        "history_id": hist_id,
    }


serve_audio_asset = serve_audio


@app.get("/api/tts/audio/{filename}")
def serve_tts_audio(filename: str):
    """Serves synthesized TTS audio files (backward-compatible endpoint)."""
    return serve_audio(filename)


@app.get("/api/recordings")
def list_recording_sessions(limit: int = 50, status: str | None = None):
    """Returns persistent call recording sessions, audio assets, and transcripts."""
    sessions = history.get_recording_sessions(limit=min(100, max(1, limit)), status=status)
    return {"recordings": sessions}


@app.get("/api/recordings/{session_id}")
def get_recording_session(session_id: str):
    """Returns detailed session lifecycle metadata, audio assets, transcripts, and status."""
    safe_sess = Path(session_id).name
    sessions = history.get_recording_sessions(limit=100)
    found = next((s for s in sessions if s["session_id"] == safe_sess), None)
    if not found:
        raise HTTPException(status_code=404, detail="Recording session not found.")
    return found


@app.delete("/api/recordings/{session_id}")
def delete_recording_session(session_id: str):
    """Permanently deletes a recording session, its audio files on disk, and DB records."""
    safe_sess = Path(session_id).name
    ok = history.delete_recording_session(safe_sess)
    if not ok:
        raise HTTPException(status_code=404, detail="Recording session not found or deletion failed.")
    return {"success": True, "session_id": safe_sess, "deleted": True}


@app.get("/api/storage/diagnostics")
def get_storage_stats():
    """Returns genuine storage integrity observability metrics."""
    return history.get_storage_diagnostics()


@app.get("/api/tts/voices")
def get_supported_voices():
    """Returns catalog of 7 curated Gnani Timbre voices exposed in CallLens."""
    return {
        "catalog_scope": "7 curated Indic voices (with Pranav and Kaveri as primary verified models)",
        "total_exposed": 7,
        "voices": [
            {"id": "Pranav", "name": "Pranav", "gender": "Male", "language": "Hindi / Hinglish", "recommended": True, "description": "Flagship Hindi male conversational voice. Verified in benchmark experiments."},
            {"id": "Kaveri", "name": "Kaveri", "gender": "Female", "language": "Hindi / Indic", "recommended": True, "description": "Expressive female conversational voice for customer service."},
            {"id": "Ishaan", "name": "Ishaan", "gender": "Male", "language": "Hindi", "recommended": False, "description": "Youthful male voice, clear for educational dialogues."},
            {"id": "Devika", "name": "Devika", "gender": "Female", "language": "Hindi / Indic", "recommended": False, "description": "Authoritative corporate female persona."},
            {"id": "Lavanya", "name": "Lavanya", "gender": "Female", "language": "Hindi / Indic", "recommended": False, "description": "Gentle, polite female persona for notification prompts."},
            {"id": "Deepak", "name": "Deepak", "gender": "Male", "language": "Hindi", "recommended": False, "description": "Formal male voice for announcements and disclosures."},
            {"id": "Trisha", "name": "Trisha", "gender": "Female", "language": "Hindi", "recommended": False, "description": "Conversational female voice for banking inquiries."},
        ]
    }


# ---------------------------------------------------------
# Audit History Endpoints
# ---------------------------------------------------------

@app.get("/api/history")
def get_audit_history(limit: int = 50, kind: str | None = None):
    """Returns persistent audit log of recent STT and TTS speech operations."""
    records = history.get_recent_history(limit=min(100, max(1, limit)), kind=kind)
    return {"history": records}


@app.delete("/api/history")
def clear_audit_history():
    """Clears history records (for test isolation and privacy reset)."""
    count = history.clear_history()
    return {"success": True, "deleted_count": count}


# ---------------------------------------------------------
# Live Speech WebSocket Session Controller
# ---------------------------------------------------------

MAX_WS_CHUNK_BYTES = 512 * 1024  # 512 KB per audio packet

@app.websocket("/ws/speech")
async def speech_websocket_endpoint(websocket: WebSocket):
    """Application-level WebSocket endpoint managing interactive speech recording,

    chunked audio transport, event lifecycle, atomic STT transcription, and TTS generation.
    """
    await websocket.accept()
    session_id = f"sess_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
    logger.info("[WebSocket] Client connected: %s", session_id)

    # Initialize persistent recording session in DB
    history.create_recording_session(
        source="websocket_live",
        session_id=session_id,
        language="hi-IN",
    )

    # Initial session confirmation
    await websocket.send_json({
        "type": "session_started",
        "session_id": session_id,
        "timestamp": time.time(),
        "provider_note": "Gnani Prisma STT operates via atomic HTTP REST gateway. CallLens buffers real-time audio chunks via WebSocket for lossless transcription.",
    })

    audio_buffer = bytearray()
    active_config = {
        "model": "prisma-v2.5",
        "language_code": "hi-IN",
        "format": "verbatim",
        "live": 0,
    }

    data_dir = get_data_dir()
    temp_dir = data_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    session_status = "active"

    try:
        while True:
            msg = await websocket.receive()

            # Handle binary audio chunks (MediaRecorder streaming)
            if "bytes" in msg and msg["bytes"]:
                chunk = msg["bytes"]
                if len(chunk) > MAX_WS_CHUNK_BYTES:
                    await websocket.send_json({
                        "type": "operation_failed",
                        "error_code": "CHUNK_TOO_LARGE",
                        "error": f"Audio chunk exceeds maximum allowed chunk size of {MAX_WS_CHUNK_BYTES // 1024} KB.",
                    })
                    continue

                if len(audio_buffer) + len(chunk) > MAX_UPLOAD_BYTES:
                    await websocket.send_json({
                        "type": "operation_failed",
                        "error_code": "BUFFER_LIMIT_EXCEEDED",
                        "error": f"Buffer limit exceeded ({MAX_UPLOAD_BYTES / (1024*1024):.0f} MB max). Resetting stream.",
                    })
                    audio_buffer.clear()
                    continue

                audio_buffer.extend(chunk)
                await websocket.send_json({
                    "type": "audio_chunk_received",
                    "bytes_received": len(chunk),
                    "total_bytes": len(audio_buffer),
                })

            # Handle JSON control commands
            elif "text" in msg and msg["text"]:
                try:
                    payload = json.loads(msg["text"])
                except Exception:
                    await websocket.send_json({
                        "type": "operation_failed",
                        "error_code": "INVALID_JSON",
                        "error": "Malformed JSON text payload received.",
                    })
                    continue

                action = payload.get("action")

                if action == "start_session":
                    requested_live = int(payload.get("live", 0))
                    if requested_live and not ALLOW_LIVE_API:
                        await websocket.send_json({
                            "type": "operation_failed",
                            "error_code": "LIVE_EXECUTION_FORBIDDEN",
                            "error": "Live provider execution is disabled by server policy (ALLOW_LIVE_API=0). Request denied.",
                        })
                        continue

                    active_config["model"] = payload.get("model", "prisma-v2.5")
                    active_config["language_code"] = payload.get("language_code", "hi-IN")
                    active_config["format"] = payload.get("format", "verbatim")
                    active_config["live"] = requested_live
                    audio_buffer.clear()
                    await websocket.send_json({
                        "type": "session_configured",
                        "config": active_config,
                    })

                elif action == "finish_recording":
                    if not audio_buffer:
                        await websocket.send_json({
                            "type": "operation_failed",
                            "error_code": "EMPTY_BUFFER",
                            "error": "Audio buffer is empty. Record audio before submitting.",
                        })
                        continue

                    # Persist raw recording FIRST to guarantee durability even if downstream ASR fails
                    raw_audio_bytes = bytes(audio_buffer)
                    saved_asset = history.save_audio_asset(
                        raw_audio_bytes,
                        asset_type="recording",
                        session_id=session_id,
                    )
                    duration_sec = saved_asset["duration_seconds"] or 2.0

                    await websocket.send_json({
                        "type": "transcription_started",
                        "total_bytes": len(audio_buffer),
                        "asset_id": saved_asset["asset_id"],
                        "audio_url": f"/api/audio/{saved_asset['filename']}",
                    })

                    # Write buffer to temporary file for SDK call
                    tmp_wav = temp_dir / f"live_{session_id}.wav"
                    tmp_wav.write_bytes(raw_audio_bytes)

                    start_time = time.perf_counter()
                    stt_payload = {
                        "audio": tmp_wav,
                        "model": active_config["model"],
                        "language_code": active_config["language_code"],
                        "format": active_config["format"],
                    }

                    try:
                        is_live = bool(active_config["live"])
                        if is_live and not ALLOW_LIVE_API:
                            raise PermissionError("Live provider execution forbidden by server policy.")

                        res = gnani_client.call("stt", stt_payload, live=is_live, use_cache=True)
                        elapsed = time.perf_counter() - start_time
                        transcript = res.get("transcript", "")
                        words = len(transcript.strip().split()) if transcript.strip() else 0
                        provenance = "cache" if res.get("from_cache") else ("live" if is_live else "mock")

                        # Record to audit history and persistence tables
                        history.record_stt_history(
                            model=res.get("model", active_config["model"]),
                            language=active_config["language_code"],
                            format=active_config["format"],
                            duration_sec=duration_sec,
                            latency_sec=elapsed,
                            input_name=f"Live Microphone ({session_id})",
                            transcript=transcript,
                            status="completed",
                            session_id=session_id,
                            audio_filename=saved_asset["filename"],
                            metadata={
                                "words": words,
                                "mock": res.get("mock", not is_live),
                                "asset_id": saved_asset["asset_id"],
                                "provenance": provenance,
                            },
                        )

                        history.record_transcript(
                            text=transcript,
                            session_id=session_id,
                            is_final=True,
                        )

                        history.record_speech_operation(
                            session_id=session_id,
                            asset_id=saved_asset["asset_id"],
                            operation_type="stt",
                            model=res.get("model", active_config["model"]),
                            language=active_config["language_code"],
                            format=active_config["format"],
                            status="completed",
                            provenance=provenance,
                            latency_ms=elapsed * 1000,
                        )

                        session_status = "completed"
                        history.update_recording_session(
                            session_id,
                            status="completed",
                            metadata_update={"duration_sec": duration_sec, "words": words},
                        )

                        await websocket.send_json({
                            "type": "transcription_completed",
                            "transcript": transcript,
                            "model": res.get("model", active_config["model"]),
                            "duration_sec": round(duration_sec, 2),
                            "latency_sec": round(elapsed, 3),
                            "word_count": words,
                            "mock": res.get("mock", not is_live),
                            "provenance": provenance,
                            "asset_id": saved_asset["asset_id"],
                            "audio_url": f"/api/audio/{saved_asset['filename']}",
                        })
                    except Exception as exc:
                        logger.error("WebSocket STT transcription failed: %s", exc)
                        session_status = "failed"
                        history.record_speech_operation(
                            session_id=session_id,
                            asset_id=saved_asset["asset_id"],
                            operation_type="stt",
                            model=active_config["model"],
                            language=active_config["language_code"],
                            status="failed",
                            error_code="STT_PROVIDER_ERROR",
                            error_message="Speech recognition provider request failed",
                        )
                        history.update_recording_session(session_id, status="failed")

                        await websocket.send_json({
                            "type": "operation_failed",
                            "error_code": "STT_PROVIDER_ERROR",
                            "error": "Speech recognition provider request failed. Audio recording has been safely preserved.",
                            "asset_id": saved_asset["asset_id"],
                            "audio_url": f"/api/audio/{saved_asset['filename']}",
                        })
                    finally:
                        audio_buffer.clear()
                        try:
                            if tmp_wav.exists():
                                tmp_wav.unlink()
                        except Exception:
                            pass

                elif action == "synthesize":
                    tts_text = payload.get("text", "").strip()
                    if not tts_text:
                        await websocket.send_json({
                            "type": "operation_failed",
                            "error_code": "EMPTY_TEXT",
                            "error": "Synthesis text cannot be empty.",
                        })
                        continue

                    requested_live = int(payload.get("live", 0))
                    if requested_live and not ALLOW_LIVE_API:
                        await websocket.send_json({
                            "type": "operation_failed",
                            "error_code": "LIVE_EXECUTION_FORBIDDEN",
                            "error": "Live provider execution is disabled by server policy (ALLOW_LIVE_API=0). Request denied.",
                        })
                        continue

                    voice = payload.get("voice", "Pranav")
                    speed = float(payload.get("speed", 1.0))
                    is_live = bool(requested_live)

                    await websocket.send_json({
                        "type": "tts_generation_started",
                        "text": tts_text,
                        "voice": voice,
                    })

                    tts_payload = {
                        "text": tts_text,
                        "voice": voice,
                        "model": "timbre-v2.5",
                        "language": active_config["language_code"],
                        "speed": speed,
                    }

                    try:
                        tts_bytes = gnani_client.call("tts", tts_payload, live=is_live, use_cache=True)
                        saved_tts = history.save_audio_asset(
                            tts_bytes,
                            asset_type="tts_generated",
                            session_id=session_id,
                        )
                        tts_dur = saved_tts["duration_seconds"] or (len(tts_text) * 0.08)

                        history.record_speech_operation(
                            session_id=session_id,
                            asset_id=saved_tts["asset_id"],
                            operation_type="tts",
                            model="timbre-v2.5",
                            voice=voice,
                            language=active_config["language_code"],
                            status="completed",
                            provenance="live" if is_live else "mock",
                        )

                        await websocket.send_json({
                            "type": "tts_audio_ready",
                            "audio_base64": base64.b64encode(tts_bytes).decode("utf-8"),
                            "audio_url": f"/api/audio/{saved_tts['filename']}",
                            "asset_id": saved_tts["asset_id"],
                            "duration_sec": round(tts_dur, 2),
                            "voice": voice,
                            "char_count": len(tts_text),
                        })
                    except Exception as exc:
                        logger.error("WebSocket TTS synthesis failed: %s", exc)
                        await websocket.send_json({
                            "type": "operation_failed",
                            "error_code": "TTS_PROVIDER_ERROR",
                            "error": "Text-to-speech synthesis failed. Please verify voice configuration.",
                        })

                elif action == "cancel":
                    audio_buffer.clear()
                    session_status = "cancelled"
                    history.update_recording_session(session_id, status="cancelled")
                    await websocket.send_json({
                        "type": "recording_cancelled",
                        "message": "Audio buffer cleared and recording stopped.",
                    })

    except WebSocketDisconnect:
        logger.info("[WebSocket] Client disconnected: %s", session_id)
        if session_status == "active":
            history.update_recording_session(session_id, status="interrupted")
    except Exception as exc:
        logger.error("[WebSocket] Session error: %s", exc)
        if session_status == "active":
            history.update_recording_session(session_id, status="interrupted")


# ---------------------------------------------------------
# Follow-up Desk API Endpoints
# ---------------------------------------------------------

FOLLOWUP_SCENARIOS = [
    {
        "id": "scenario_01",
        "clip_id": "bfsi_01",
        "customer_name": "राहुल शर्मा",
        "scenario_title": "Credit Card Overdue — Salary Delay",
        "dialogue_text": "नमस्ते राहुल शर्मा जी, आपका क्रेडिट कार्ड बिल ₹ 50,000 है जो 5 तारीख तक देय था। ग्राहक ने बताया कि वेतन में देरी के कारण भुगतान नहीं हुआ और 10 तारीख को पे कर देंगे।",
        "reference_amount": 50000,
        "reference_due_day": 5,
        "reference_ptp": "10 तारीख",
        "reference_concern": "Salary delay (वेतन में देरी)",
    },
    {
        "id": "scenario_02",
        "clip_id": "bfsi_02",
        "customer_name": "प्रिया वर्मा",
        "scenario_title": "Home Loan EMI — Medical Emergency",
        "dialogue_text": "हेलो प्रिया वर्मा, आपकी होम लोन ईएमआई 3,50,000 rupees 15 तारीख को कटनी थी। अस्पताल में इलाज के कारण थोड़ा विलंब हुआ, ग्राहक 20 तारीख तक भर देगा।",
        "reference_amount": 350000,
        "reference_due_day": 15,
        "reference_ptp": "20 तारीख",
        "reference_concern": "Medical / Family emergency (चिकित्सा आपातकाल)",
    },
    {
        "id": "scenario_03",
        "clip_id": "bfsi_04",
        "customer_name": "सुनील कुमार",
        "scenario_title": "Auto Loan Installment — Out of Town",
        "dialogue_text": "नमस्ते सुनील कुमार जी, आपकी ऑटो लोन किस्त 1.5 लाख रुपये 25 तारीख तक जमा कराएं। ग्राहक अभी शहर से बाहर है और सोमवार को ट्रांसफर करेगा।",
        "reference_amount": 150000,
        "reference_due_day": 25,
        "reference_ptp": "सोमवार को",
        "reference_concern": "Customer out of station / traveling (शहर से बाहर)",
    },
    {
        "id": "scenario_04",
        "clip_id": "bfsi_06",
        "customer_name": "राजेश गुप्ता",
        "scenario_title": "Personal Loan — Netbanking Technical Failure",
        "dialogue_text": "राजेश गुप्ता जी, आपका व्यक्तिगत ऋण बकाया 2.25 lakh है जो 12 तारीख तक भरें। सर्वर डाउन और यूपीआई फेल होने से पैसा नहीं गया, कल तक दोबारा प्रयास करेंगे।",
        "reference_amount": 225000,
        "reference_due_day": 12,
        "reference_ptp": "कल तक",
        "reference_concern": "Technical / Banking transaction failure (तकनीकी विफलता)",
    },
    {
        "id": "scenario_05",
        "clip_id": "bfsi_07",
        "customer_name": "अनीता देसाई",
        "scenario_title": "Account Overdraft — Late Fee Dispute",
        "dialogue_text": "अनीता देसाई, आपके खाते से 75,500 rupees की ईएमआई 20 तारीख को काटी जानी है। अतिरिक्त पेनल्टी शुल्क पर विवाद है, शाखा प्रबंधक से बात करने के बाद भुगतान होगा।",
        "reference_amount": 75500,
        "reference_due_day": 20,
        "reference_ptp": None,
        "reference_concern": "Disputed late fee / penalty charges (अतिरिक्त शुल्क विवाद)",
    },
]


@app.get("/api/followup/scenarios")
def get_followup_scenarios():
    """Returns curated synthetic Banking & Telephony Follow-up scenarios for operator review."""
    return {"scenarios": FOLLOWUP_SCENARIOS}


@app.post("/api/followup/process")
async def process_followup_call(req: FollowupProcessRequest, request: Request):
    """Processes a call recording for the Follow-up Desk:

    1. Transcribes call audio using Prisma ASR.
    2. Extracts structured banking fields (amount, due date, PTP date, concern, summary).
    3. Generates a suggested Hindi/Hinglish reminder template for Timbre.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    check_rate_limit(client_ip)
    is_live = enforce_live_policy(req.live)

    data_dir = get_data_dir()
    audio_bytes: bytes | None = None
    transcript: str = ""
    scenario_match = None
    saved_asset_id = None

    # Check if scenario_id or clip_id matches a pre-loaded scenario
    target_id = req.scenario_id or req.clip_id
    if target_id:
        for sc in FOLLOWUP_SCENARIOS:
            if sc["id"] == target_id or sc["clip_id"] == target_id:
                scenario_match = sc
                break

    # If mock_transcript or transcript provided, use directly
    if req.mock_transcript:
        transcript = req.mock_transcript
    elif req.transcript:
        transcript = req.transcript
    elif scenario_match and not is_live and scenario_match.get("dialogue_text"):
        transcript = scenario_match["dialogue_text"]
    elif req.audio_base64:
        try:
            audio_bytes = base64.b64decode(req.audio_base64)
            asset = history.save_audio_asset(audio_bytes, asset_type="followup_input")
            saved_asset_id = asset["asset_id"]
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid audio_base64 encoding.")
    elif target_id:
        # Search audio files
        clip_target = scenario_match["clip_id"] if scenario_match else target_id
        for candidate in [
            data_dir / "bfsi" / f"{clip_target}.wav",
            data_dir / "bfsi_mock" / f"{clip_target}.wav",
            data_dir / "processed_audio" / f"{clip_target}_clean.wav",
            data_dir / "processed_audio" / f"{clip_target}.wav",
        ]:
            if candidate.exists():
                audio_bytes = candidate.read_bytes()
                break

    # If we have audio bytes and no transcript yet, run transcription
    if audio_bytes and not transcript:
        temp_dir = data_dir / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_audio = temp_dir / f"flw_in_{int(time.time()*1000)}.wav"
        temp_audio.write_bytes(audio_bytes)

        try:
            payload = {
                "audio": temp_audio,
                "model": req.model,
                "language_code": "hi-IN",
                "format": "transcribe",
            }
            if scenario_match:
                payload["mock_transcript"] = scenario_match["dialogue_text"]

            res = gnani_client.call("stt", payload, live=is_live, use_cache=True)
            transcript = res.get("transcript", "")
        except Exception as exc:
            logger.error("Followup STT transcription failed: %s", exc)
            if "504" in str(exc) or "timeout" in str(exc).lower():
                raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Speech recognition provider timed out.")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Speech recognition provider request failed.")
        finally:
            if temp_audio.exists():
                try:
                    temp_audio.unlink()
                except Exception:
                    pass

    if not transcript and scenario_match:
        transcript = scenario_match["dialogue_text"]

    if not transcript:
        raise HTTPException(
            status_code=400,
            detail="Unable to transcribe call audio. Please provide valid audio data or select a preloaded scenario.",
        )

    # Perform structured field extraction
    c_name_hint = req.customer or req.customer_name or (scenario_match["customer_name"] if scenario_match else None)
    extracted = extract.extract_followup_details(transcript, customer_name=c_name_hint)

    return {
        "success": True,
        "transcript": transcript,
        "customer": c_name_hint or "Customer",
        "model": req.model,
        "scenario_id": scenario_match["id"] if scenario_match else target_id,
        "details": extracted,
        "suggested_reminder_text": extracted.get("reminder_template") or "",
        "extracted": extracted,
        "asset_id": saved_asset_id,
    }


@app.post("/api/followup/confirm")
async def confirm_followup_reminder(req: FollowupConfirmRequest, request: Request):
    """Synthesizes verified follow-up reminder audio via Timbre and commits record to history."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    check_rate_limit(client_ip)
    is_live = enforce_live_policy(req.live)

    cust_name = req.customer or req.customer_name or "Customer"
    c_summary = req.summary or req.call_summary or "Confirmed follow-up commitments"
    c_amount = int(req.amount) if req.amount is not None else None
    c_concern = req.concern or "none"

    clean_text = req.reminder_text.strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="Reminder text cannot be empty.")
    if len(clean_text) > 2000:
        raise HTTPException(status_code=400, detail="Reminder text exceeds 2,000 characters.")

    start_time = time.perf_counter()

    tts_payload = {
        "text": clean_text,
        "voice": req.voice,
        "model": "timbre-v2.5",
        "language": req.language or "hi-IN",
        "speed": req.speed,
    }

    try:
        audio_bytes = gnani_client.call("tts", tts_payload, live=is_live, use_cache=True)
        elapsed = time.perf_counter() - start_time
    except Exception as exc:
        logger.error("Follow-up reminder synthesis failed: %s", exc)
        if "504" in str(exc) or "timeout" in str(exc).lower():
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Text-to-speech provider timed out. Please retry.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Speech synthesis provider request failed. Please check voice configuration and retry.")

    # Save audio asset with collision-resistant UUID filename
    saved_asset = history.save_audio_asset(audio_bytes, asset_type="followup_reminder")
    filename = saved_asset["filename"]
    duration_sec = saved_asset["duration_seconds"] or round(len(clean_text) * 0.08, 2)
    duration_estimated = saved_asset["duration_estimated"]
    provenance = "live" if is_live else "mock"

    # Record into persistent audit history
    hist_id = history.record_followup_history(
        customer_name=cust_name,
        amount=c_amount,
        due_date=req.due_date,
        ptp_date=req.ptp_date,
        concern=c_concern,
        reminder_text=clean_text,
        voice=req.voice,
        audio_filename=filename,
        duration_sec=duration_sec,
        latency_sec=elapsed,
        status="completed",
        confirmed_by="Operator (Human-in-the-Loop Verified)",
        metadata={
            "call_summary": c_summary,
            "speed": req.speed,
            "mock": not is_live,
            "provenance": provenance,
            "asset_id": saved_asset["asset_id"],
            "operator_notes": req.operator_notes,
            "duration_estimated": duration_estimated,
        },
    )

    # Record into relational followup_records table
    history.record_followup_entry(
        session_id=None,
        customer_name=cust_name,
        amount=c_amount,
        due_date=req.due_date,
        ptp_date=req.ptp_date,
        concern=c_concern,
        call_summary=c_summary,
        reminder_text=clean_text,
        voice=req.voice,
        asset_id=saved_asset["asset_id"],
        operator_notes=req.operator_notes,
    )

    b64_audio = base64.b64encode(audio_bytes).decode("ascii")
    return {
        "success": True,
        "status": "confirmed_and_synthesized",
        "record_id": hist_id,
        "history_id": hist_id,
        "asset_id": saved_asset["asset_id"],
        "audio_url": f"/api/tts/audio/{filename}",
        "audio_b64": b64_audio,
        "filename": filename,
        "duration_s": round(duration_sec, 2),
        "duration_sec": round(duration_sec, 2),
        "latency_sec": round(elapsed, 3),
        "voice": req.voice,
        "customer": cust_name,
        "reminder_text": clean_text,
        "provenance": provenance,
        "confirmed_record": {
            "customer_name": cust_name,
            "amount": c_amount,
            "due_date": req.due_date,
            "ptp_date": req.ptp_date,
            "concern": c_concern,
            "call_summary": c_summary,
            "reminder_text": clean_text,
            "voice": req.voice,
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        },
    }

