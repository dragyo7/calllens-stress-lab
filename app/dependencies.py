"""Shared FastAPI dependencies, configuration, and security policies for CallLens."""

from __future__ import annotations

import os
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

# Add repository root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from calllens.benchmark import BenchmarkResult, get_db_session

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_AUDIO_DURATION_SEC = 30.0
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW_SEC = 60.0
MAX_WS_CHUNK_BYTES = 512 * 1024  # 512 KB per audio packet

# Server-side live provider execution authorization policy (fail closed)
ALLOW_LIVE_API = os.getenv("ALLOW_LIVE_API", "0").lower() in ("1", "true", "yes")

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
    """Thread-safe per-IP rate limiter with bounded memory."""
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


def get_data_dir() -> Path:
    env_dir = os.getenv("DATA_DIR")
    if env_dir:
        return Path(env_dir)
    sibling = Path("../calllens-data")
    if sibling.exists():
        return sibling
    local = Path("data")
    local.mkdir(parents=True, exist_ok=True)
    return local


def get_replay_live_results(clip_id: str, condition: str, data_dir: Path) -> dict[str, Any] | None:
    """Replays genuine recorded live benchmark results from benchmark.db."""
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
        return None

