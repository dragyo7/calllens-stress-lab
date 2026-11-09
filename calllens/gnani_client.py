"""Centralized client for Gnani STT and TTS services.

All requests to Gnani APIs MUST pass through this module's `call` function.
Provides:
- Deterministic SHA-256 caching (successes only)
- Live call cap protection (MAX_LIVE_CALLS)
- Concurrency limit (max 2 concurrent requests)
- Bounded exponential backoff for 429/5xx errors
- Strict secrets redaction in logs
- Mock mode for offline development and testing
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Literal, Union

from dotenv import load_dotenv

# Ensure environment is loaded from .env if present
load_dotenv()

logger = logging.getLogger("calllens.client")

# Defaults and limits
DEFAULT_MAX_LIVE_CALLS = 10
DEFAULT_TIMEOUT = 30
MAX_CONCURRENT_CALLS = 2
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0
BACKOFF_FACTOR = 2.0
MAX_BACKOFF = 8.0

_semaphore = threading.Semaphore(MAX_CONCURRENT_CALLS)


class CallLimitExceededError(RuntimeError):
    """Raised when live call count reaches or exceeds MAX_LIVE_CALLS."""


class GnaniClientError(Exception):
    """Base exception for Gnani client errors."""


class RedactingFilter(logging.Filter):
    """Filters out API keys and auth tokens from log records."""

    _SECRET_PATTERN = re.compile(r"(api[_-]?key|token|auth[a-z]*)\s*[:=]\s*['\"]?([^'\"\s]+)", re.IGNORECASE)

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._SECRET_PATTERN.sub(r"\1: [REDACTED]", record.msg)
            # Also redact raw key if loaded in env
            api_key = os.getenv("GNANI_API_KEY", "")
            if api_key and len(api_key) > 4:
                record.msg = record.msg.replace(api_key, "[REDACTED_API_KEY]")
        return True


# Configure logger with redaction filter
_handler = logging.StreamHandler()
_handler.addFilter(RedactingFilter())
logger.addHandler(_handler)
logger.setLevel(logging.INFO)


@dataclass
class CallAccounting:
    """Thread-safe accounting of calls, retries, attempts, and cache hits."""

    live_calls: int = 0
    cache_hits: int = 0
    retries: int = 0
    network_attempts: int = 0
    mock_calls: int = 0
    max_live_calls: int = int(os.getenv("MAX_LIVE_CALLS", str(DEFAULT_MAX_LIVE_CALLS)))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record_cache_hit(self) -> None:
        with self._lock:
            self.cache_hits += 1

    def record_mock_call(self) -> None:
        with self._lock:
            self.mock_calls += 1

    def can_make_live_call(self) -> bool:
        with self._lock:
            return self.network_attempts < self.max_live_calls

    def check_and_reserve_live_call(self) -> None:
        with self._lock:
            if self.network_attempts >= self.max_live_calls:
                raise CallLimitExceededError(
                    f"Live network attempt cap reached: {self.network_attempts}/{self.max_live_calls}. "
                    f"Set MAX_LIVE_CALLS to increase budget."
                )

    def check_and_reserve_network_attempt(self) -> None:
        with self._lock:
            if self.network_attempts >= self.max_live_calls:
                raise CallLimitExceededError(
                    f"Live network attempt cap reached: {self.network_attempts}/{self.max_live_calls}. "
                    f"Set MAX_LIVE_CALLS to increase budget."
                )
            self.network_attempts += 1

    def record_network_attempt(self) -> None:
        # Kept for backward compatibility if called directly
        pass

    def record_retry(self) -> None:
        with self._lock:
            self.retries += 1

    def record_live_success(self) -> None:
        with self._lock:
            self.live_calls += 1

    def reset(self, new_max_live_calls: int | None = None) -> None:
        with self._lock:
            self.live_calls = 0
            self.cache_hits = 0
            self.retries = 0
            self.network_attempts = 0
            self.mock_calls = 0
            if new_max_live_calls is not None:
                self.max_live_calls = new_max_live_calls


# Global accounting instance
accounting = CallAccounting()


def get_cache_dir() -> Path:
    """Returns directory for response caching."""
    custom_dir = os.getenv("CALLENS_CACHE_DIR")
    if custom_dir:
        p = Path(custom_dir)
    else:
        # Default to sibling calllens-data or local .cache
        data_dir = os.getenv("DATA_DIR", "../calllens-data")
        p = Path(data_dir) / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def compute_cache_key(kind: Literal["stt", "tts"], payload: dict[str, Any]) -> str:
    """Computes a deterministic SHA-256 hash for the request payload."""
    hasher = hashlib.sha256()
    hasher.update(kind.encode("utf-8"))

    if kind == "stt":
        # Hash audio bytes or file content
        audio = payload.get("audio")
        if isinstance(audio, (str, Path)):
            with open(audio, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
        elif isinstance(audio, bytes):
            hasher.update(audio)
        elif hasattr(audio, "read"):
            pos = audio.tell() if hasattr(audio, "tell") else None
            audio.seek(0)
            while chunk := audio.read(65536):
                hasher.update(chunk)
            if pos is not None:
                audio.seek(pos)
        else:
            hasher.update(b"no_audio")

        # Include model, language, format, and context
        norm_model = (payload.get("model") or "prisma-v2.5").strip().lower()
        hasher.update(norm_model.encode("utf-8"))
        hasher.update((payload.get("language_code") or "hi-IN").encode("utf-8"))
        hasher.update((payload.get("format") or "verbatim").encode("utf-8"))
        hasher.update(str(payload.get("itn_native_numerals", False)).encode("utf-8"))
        for k in sorted(["keywords", "topic", "previous_text", "speaker_names"]):
            val = payload.get(k)
            if val is not None:
                hasher.update(f"{k}:{val}".encode("utf-8"))

    elif kind == "tts":
        hasher.update(str(payload.get("text", "")).encode("utf-8"))
        hasher.update(str(payload.get("voice", "Pranav")).encode("utf-8"))
        hasher.update(str(payload.get("model", "timbre-v2.5")).encode("utf-8"))
        hasher.update(str(payload.get("language", "hi-IN")).encode("utf-8"))
        hasher.update(str(payload.get("speed", 1.0)).encode("utf-8"))

    return hasher.hexdigest()


def _get_from_cache(cache_key: str, kind: str) -> dict[str, Any] | bytes | None:
    cache_file = get_cache_dir() / f"{cache_key}.json"
    if not cache_file.exists():
        return None
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if kind == "tts":
            # TTS audio stored as base64 in json
            return base64.b64decode(data["audio_base64"])
        return data
    except Exception as exc:
        logger.warning("Failed to read cache entry %s: %s", cache_key, exc)
        return None


def _save_to_cache(cache_key: str, kind: str, result: Any) -> None:
    cache_file = get_cache_dir() / f"{cache_key}.json"
    try:
        if kind == "tts":
            data = {
                "kind": "tts",
                "audio_base64": base64.b64encode(result).decode("utf-8"),
                "timestamp": time.time(),
            }
        else:
            data = result
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("Failed to write cache entry %s: %s", cache_key, exc)


def _generate_mock_stt(payload: dict[str, Any]) -> dict[str, Any]:
    """Generates a realistic deterministic mock STT response."""
    audio = payload.get("audio")
    model = payload.get("model") or "prisma-v2.5"
    fmt = payload.get("format", "verbatim")

    # If mock transcript hint is passed in payload (useful for tests and synthetic data)
    hint = payload.get("mock_transcript")
    if hint:
        transcript = hint
    else:
        # Generate predictable mock text from audio path or content
        name = Path(audio).stem if isinstance(audio, (str, Path)) else "sample"
        if "silence" in name.lower():
            transcript = ""
        elif "noise" in name.lower():
            # Noise might hallucinate or be empty
            transcript = ""
        else:
            transcript = f"नमस्ते यह मॉडल {model} का परीक्षण ऑडियो है"

    return {
        "success": True,
        "request_id": f"mock-{hashlib.md5(str(audio).encode()).hexdigest()[:12]}",
        "transcript": transcript,
        "model": model,
        "format": fmt,
        "processing_time": 0.35,
        "end_to_end_latency": 0.48,
        "mock": True,
    }


def _generate_mock_tts(payload: dict[str, Any]) -> bytes:
    """Generates valid 16kHz mono PCM16 WAV bytes for mock TTS."""
    import io
    import numpy as np
    import soundfile as sf

    text = payload.get("text", "")
    # Generate 1.5 seconds of soft tone/silence as realistic audio
    sr = 16000
    duration = max(1.0, min(5.0, len(text) * 0.1))
    t = np.linspace(0, duration, int(sr * duration), endpoint=False, dtype=np.float32)
    # 440 Hz gentle sine wave at -20 dBFS
    signal = 0.1 * np.sin(2 * np.pi * 440 * t)
    bio = io.BytesIO()
    sf.write(bio, signal, sr, format="WAV", subtype="PCM_16")
    return bio.getvalue()


def call(
    kind: Literal["stt", "tts"],
    payload: dict[str, Any],
    *,
    live: bool = False,
    use_cache: bool = True,
) -> dict[str, Any] | bytes:
    """Central entry point for all Gnani STT and TTS requests.

    Parameters
    ----------
    kind : "stt" or "tts"
        Type of service requested.
    payload : dict
        Parameters for STT (`audio`, `language_code`, `model`, `format`, etc.)
        or TTS (`text`, `voice`, `model`, `language`, `speed`, etc.).
    live : bool, default False
        Whether to perform a live network call if not in cache.
        If False, returns a mock response when not in cache.
    use_cache : bool, default True
        Whether to check and store results in SHA-256 cache.

    Returns
    -------
    dict for STT, bytes for TTS.
    """
    cache_key = compute_cache_key(kind, payload)

    # 1. Check cache first
    if use_cache:
        cached = _get_from_cache(cache_key, kind)
        if cached is not None:
            accounting.record_cache_hit()
            logger.info("[GnaniClient] Cache HIT for key %s... (%s)", cache_key[:12], kind)
            if isinstance(cached, dict):
                cached["from_cache"] = True
            return cached

    # 2. Check if live call is permitted
    if not live:
        accounting.record_mock_call()
        logger.info("[GnaniClient] MOCK call generated for %s (live=False)", kind)
        if kind == "stt":
            return _generate_mock_stt(payload)
        else:
            return _generate_mock_tts(payload)

    # 3. Live call path: Check cap and API key
    accounting.check_and_reserve_live_call()

    api_key = os.getenv("GNANI_API_KEY")
    if not api_key:
        raise GnaniClientError("GNANI_API_KEY environment variable is not set. Cannot execute live call.")

    # 4. Concurrency control and bounded retry loop
    from gnani.stt.client import GnaniSTTClient
    from gnani.tts.client import GnaniTTSClient

    timeout = int(os.getenv("GNANI_TIMEOUT", str(DEFAULT_TIMEOUT)))

    with _semaphore:
        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            accounting.check_and_reserve_network_attempt()
            try:
                start_time = time.perf_counter()
                if kind == "stt":
                    client = GnaniSTTClient(api_key=api_key, timeout=timeout)
                    # Model parameter: None for v2.5, "prisma-v3.0" for v3.0
                    model_param = payload.get("model")
                    if model_param and model_param.strip().lower() in ("prisma-v2.5", "v2.5", "default"):
                        model_param = None

                    res = client.transcribe(
                        audio=payload["audio"],
                        language_code=payload.get("language_code", "hi-IN"),
                        model=model_param,
                        format=payload.get("format", "verbatim"),
                        itn_native_numerals=payload.get("itn_native_numerals", False),
                        language_candidates=payload.get("language_candidates"),
                        keywords=payload.get("keywords"),
                        topic=payload.get("topic"),
                        previous_text=payload.get("previous_text"),
                        speaker_names=payload.get("speaker_names"),
                        request_id=payload.get("request_id"),
                    )
                    elapsed = time.perf_counter() - start_time
                    if "end_to_end_latency" not in res:
                        res["end_to_end_latency"] = elapsed
                    res["from_cache"] = False

                    # Success: record and cache
                    accounting.record_live_success()
                    if use_cache:
                        _save_to_cache(cache_key, kind, res)
                    return res

                elif kind == "tts":
                    client = GnaniTTSClient(api_key=api_key, timeout=timeout)
                    res_bytes = client.synthesize(
                        text=payload["text"],
                        voice=payload.get("voice", "Pranav"),
                        model=payload.get("model", "timbre-v2.5"),
                        language=payload.get("language", "hi-IN"),
                        speed=payload.get("speed", 1.0),
                        output_file=payload.get("output_file"),
                        request_id=payload.get("request_id"),
                    )
                    accounting.record_live_success()
                    if use_cache:
                        _save_to_cache(cache_key, kind, res_bytes)
                    return res_bytes

            except Exception as exc:
                last_error = exc
                err_str = str(exc)
                status_code = getattr(exc, "status_code", None)
                # Check if retryable (429 or 5xx)
                is_retryable = False
                if status_code and (status_code == 429 or status_code >= 500):
                    is_retryable = True
                elif any(term in err_str for term in ["429", "500", "502", "503", "504", "Rate limit", "timed out"]):
                    is_retryable = True

                if is_retryable and attempt < MAX_RETRIES:
                    accounting.record_retry()
                    backoff = min(MAX_BACKOFF, INITIAL_BACKOFF * (BACKOFF_FACTOR ** (attempt - 1)))
                    logger.warning(
                        "[GnaniClient] Retryable error on attempt %d/%d (%s). Backing off %.1fs...",
                        attempt,
                        MAX_RETRIES,
                        exc,
                        backoff,
                    )
                    time.sleep(backoff)
                else:
                    logger.error("[GnaniClient] Non-retryable error or max retries reached: %s", exc)
                    raise GnaniClientError(f"Request failed: {exc}") from exc


        raise GnaniClientError(f"Request failed after {MAX_RETRIES} attempts: {last_error}") from last_error
