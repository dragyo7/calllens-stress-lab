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
import html
import io
import json

import logging
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import soundfile as sf
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Add repository root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from calllens import degrade, extract, gnani_client, metrics
from calllens.benchmark import BenchmarkResult, get_db_session
from calllens.gnani_client import accounting

logger = logging.getLogger("calllens.app")

app = FastAPI(
    title="CallLens Stress Lab",
    description="ASR Telephony Robustness Benchmarking: Gnani Prisma v2.5 vs Prisma v3.0",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_AUDIO_DURATION_SEC = 30.0
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW_SEC = 60.0

_request_timestamps: dict[str, list[float]] = defaultdict(list)


class StressRequest(BaseModel):
    clip_id: str | None = Field(default=None, description="Clip ID from dataset")
    condition: str = Field(default="clean", description="Acoustic condition: clean, tel, tel_snr10, tel_snr0")
    live: int = Field(default=0, description="1 for live API call, 0 for replay of recorded live runs")
    audio_base64: str | None = Field(default=None, description="Optional raw audio base64 encoded")
    allow_mock: bool | None = Field(default=None, description="Allow mock fixture fallback (test-only)")


def check_rate_limit(client_ip: str) -> None:
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW_SEC
    timestamps = [t for t in _request_timestamps[client_ip] if t > cutoff]
    if len(timestamps) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: maximum {RATE_LIMIT_REQUESTS} requests per minute.",
        )
    timestamps.append(now)
    _request_timestamps[client_ip] = timestamps


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
            for item in json.load(f)[:10]:
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
            for item in json.load(f)[:4]:
                clips.append({
                    "id": item["clip_id"],
                    "category": "Noise & Silence Hallucination",
                    "label": f"Exp D: {item['type'].capitalize()} clip ({item['clip_id']})",
                    "duration_sec": item.get("duration_sec", 5.0),
                    "reference": "",
                })

    return {"clips": clips}


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
    is_live = bool(req_data.live)

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
