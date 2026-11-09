"""Unit tests for calllens/gnani_client.py."""

import io
import json
import logging
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

from calllens import gnani_client
from calllens.gnani_client import (
    CallAccounting,
    CallLimitExceededError,
    GnaniClientError,
    RedactingFilter,
    accounting,
    compute_cache_key,
)


@pytest.fixture(autouse=True)
def reset_accounting(tmp_path, monkeypatch):
    """Reset accounting stats and point cache to temp directory for clean test isolation."""
    cache_dir = tmp_path / "test_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CALLENS_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("GNANI_API_KEY", "test-secret-key-12345")
    accounting.reset(new_max_live_calls=3)


@pytest.fixture
def sample_wav(tmp_path) -> Path:
    """Creates a sample 16kHz mono PCM16 wav file."""
    p = tmp_path / "sample.wav"
    data = np.zeros(16000, dtype=np.float32)
    sf.write(str(p), data, 16000, subtype="PCM_16")
    return p


def test_cache_hit_does_not_trigger_network(sample_wav):
    """Test that a cache hit returns cached data without calling the network."""
    payload = {"audio": sample_wav, "model": None, "format": "verbatim", "language_code": "hi-IN"}
    key = compute_cache_key("stt", payload)

    # Pre-populate cache directly
    cache_file = gnani_client.get_cache_dir() / f"{key}.json"
    cache_data = {
        "success": True,
        "transcript": "पहलवान",
        "request_id": "test-cached-id",
        "model": "prisma-v2.5",
    }
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache_data, f)

    with patch("gnani.stt.client.GnaniSTTClient.transcribe") as mock_transcribe:
        res = gnani_client.call("stt", payload, live=True)
        assert res["transcript"] == "पहलवान"
        assert res["from_cache"] is True
        mock_transcribe.assert_not_called()
        assert accounting.cache_hits == 1
        assert accounting.live_calls == 0


def test_live_cap_blocks_n_plus_one(sample_wav):
    """Test that calls exceeding MAX_LIVE_CALLS raise CallLimitExceededError."""
    accounting.reset(new_max_live_calls=2)

    payload = {"audio": sample_wav, "model": "prisma-v3.0", "format": "verbatim", "language_code": "hi-IN"}

    with patch("gnani.stt.client.GnaniSTTClient.transcribe") as mock_transcribe:
        mock_transcribe.return_value = {"success": True, "transcript": "परीक्षण 1"}

        # Call 1: Success (use_cache=False to test cap without hitting cache)
        gnani_client.call("stt", payload, live=True, use_cache=False)
        assert accounting.live_calls == 1

        # Call 2: Success
        gnani_client.call("stt", payload, live=True, use_cache=False)
        assert accounting.live_calls == 2

        # Call 3 (N+1): Must be blocked
        with pytest.raises(CallLimitExceededError):
            gnani_client.call("stt", payload, live=True, use_cache=False)

        assert accounting.live_calls == 2
        assert mock_transcribe.call_count == 2


def test_failed_calls_are_not_cached(sample_wav):
    """Verify that failed API calls do not get stored in the cache."""
    payload = {"audio": sample_wav, "model": None, "format": "verbatim"}
    key = compute_cache_key("stt", payload)
    cache_file = gnani_client.get_cache_dir() / f"{key}.json"

    with patch("gnani.stt.client.GnaniSTTClient.transcribe") as mock_transcribe:
        mock_transcribe.side_effect = RuntimeError("500 Internal Server Error")

        with pytest.raises(Exception):
            gnani_client.call("stt", payload, live=True)

        assert not cache_file.exists(), "Cache file must not be written on failure"
        assert accounting.live_calls == 0


def test_bounded_retry_behavior(sample_wav):
    """Test that retryable errors (429/500) trigger up to MAX_RETRIES then stop."""
    payload = {"audio": sample_wav, "model": None, "format": "verbatim"}

    with patch("gnani.stt.client.GnaniSTTClient.transcribe") as mock_transcribe, \
         patch("time.sleep") as mock_sleep:
        mock_transcribe.side_effect = RuntimeError("429 Too Many Requests")

        with pytest.raises(GnaniClientError):
            gnani_client.call("stt", payload, live=True)

        # 1 initial + 2 retries = 3 attempts total
        assert mock_transcribe.call_count == 3
        assert accounting.network_attempts == 3
        assert accounting.retries == 2
        assert mock_sleep.call_count == 2


def test_retries_respect_and_cannot_bypass_cap(sample_wav):
    """Prove that retries count against the global network-attempt cap and are blocked when cap is hit."""
    # Cap set to 2 attempts only
    accounting.reset(new_max_live_calls=2)
    payload = {"audio": sample_wav, "model": None, "format": "verbatim"}

    with patch("gnani.stt.client.GnaniSTTClient.transcribe") as mock_transcribe, \
         patch("time.sleep"):
        mock_transcribe.side_effect = RuntimeError("503 Service Unavailable")

        # Attempt 1: Network attempt 1 -> 503
        # Attempt 2: Network attempt 2 -> 503
        # Attempt 3: Cap is 2 -> CallLimitExceededError raised before dispatch
        with pytest.raises(CallLimitExceededError) as exc_info:
            gnani_client.call("stt", payload, live=True, use_cache=False)

        assert "Live network attempt cap reached: 2/2" in str(exc_info.value)
        assert accounting.network_attempts == 2
        assert mock_transcribe.call_count == 2
        assert accounting.live_calls == 0


def test_secrets_redacted_in_logs():
    """Verify that secret keys never appear in log records."""
    log_filter = RedactingFilter()
    secret_key = "very-secret-gnani-api-token-9988"

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=f"Request dispatched with api_key: {secret_key}",
        args=(),
        exc_info=None,
    )
    log_filter.filter(record)
    assert secret_key not in record.msg
    assert "[REDACTED]" in record.msg


def test_mock_mode_default(sample_wav):
    """Verify that mock mode is default and returns valid structured output without network."""
    payload = {"audio": sample_wav, "model": "prisma-v3.0", "format": "verbatim"}

    with patch("gnani.stt.client.GnaniSTTClient.transcribe") as mock_transcribe:
        res = gnani_client.call("stt", payload, live=False)
        assert res["success"] is True
        assert res["mock"] is True
        assert "transcript" in res
        assert accounting.mock_calls == 1
        assert accounting.live_calls == 0
        mock_transcribe.assert_not_called()


def test_tts_mock_and_cache(tmp_path):
    """Verify TTS mock synthesis and SHA-256 caching."""
    payload = {"text": "नमस्ते", "voice": "Pranav", "model": "timbre-v2.5", "language": "hi-IN"}
    # Mock call
    audio_bytes = gnani_client.call("tts", payload, live=False)
    assert isinstance(audio_bytes, bytes)
    assert len(audio_bytes) > 0
    assert accounting.mock_calls == 1


def test_concurrency_semaphore():
    """Verify semaphore enforces MAX_CONCURRENT_CALLS limit."""
    assert gnani_client._semaphore._value == gnani_client.MAX_CONCURRENT_CALLS

