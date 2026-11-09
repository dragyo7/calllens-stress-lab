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
    live: int = Field(default=0, description="1 for live API call, 0 for mock/cached")
    audio_base64: str | None = Field(default=None, description="Optional raw audio base64 encoded")


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


@app.get("/")
def get_index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def get_health():
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
        "default_mode": "mock",
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
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
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
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
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
    temp_dir = data_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    input_audio_path: Path | None = None
    reference_text = ""
    gt_amount = None
    gt_due_day = None

    if raw_audio_bytes is not None:
        if len(raw_audio_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
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
        for manifest_name, cat in [("fleurs", "fleurs"), ("bfsi", "bfsi"), ("noise_silence", "noise_silence")]:
            mpath = data_dir / cat / "manifest.json"
            if mpath.exists():
                with open(mpath, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                    for item in manifest:
                        if item["clip_id"] == req_data.clip_id:
                            input_audio_path = Path(item["file_path"])
                            reference_text = item.get("raw_transcription") or item.get("text", "")
                            gt_amount = item.get("amount")
                            gt_due_day = item.get("due_day")
                            found = True
                            break
            if found:
                break

        if not found or not input_audio_path or not input_audio_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Clip ID '{req_data.clip_id}' not found in available dataset manifests.",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either clip_id or an audio payload.",
        )

    degraded_path = temp_dir / f"{input_audio_path.stem}_{req_data.condition}.wav"
    degrade.process_audio_file(input_audio_path, degraded_path, condition=req_data.condition, clip_id=input_audio_path.stem)

    is_live = bool(req_data.live)

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
        "condition": req_data.condition,
        "reference_text": reference_text,
        "live_mode": is_live,
        "prisma_v25": {
            "model": "Prisma v2.5 (default)",
            "format": "verbatim",
            "transcript": hyp_v25,
            "wer": wer_v25,
            "cer": cer_v25,
            "latency_sec": round(res_v25.get("end_to_end_latency", 0.48), 3),
            "from_cache": res_v25.get("from_cache", False),
            "mock": res_v25.get("mock", False),
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
            "extracted_entities": entities_v30,
        },
        "ground_truth_entities": {
            "amount": gt_amount,
            "due_day": gt_due_day,
        } if (gt_amount or gt_due_day) else None,
    }
