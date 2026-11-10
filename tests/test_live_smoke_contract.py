"""Integration and Contract Tests for Live/Offline Gnani Providers and Deployment."""

import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import soundfile as sf

import calllens.gnani_client as gc
from calllens.gnani_client import CallLimitExceededError


def test_live_call_cap_strictly_enforced(tmp_path):
    """Verify that when network_attempts reaches max_live_calls, further calls are blocked."""
    state_file = tmp_path / "test_accounting.json"
    lock_file = tmp_path / "test_accounting.lock"

    state_file.write_text(json.dumps({
        "live_calls": 2,
        "cache_hits": 0,
        "retries": 0,
        "network_attempts": 2,
        "mock_calls": 0,
    }))

    with patch("calllens.gnani_client._get_accounting_paths", return_value=(state_file, lock_file)):
        acc = gc.CallAccounting()
        acc.max_live_calls = 2
        with pytest.raises(CallLimitExceededError) as exc_info:
            acc.check_and_reserve_live_call()
        assert "Persistent global network attempt cap reached" in str(exc_info.value)


def test_live_tts_audio_header_and_decoding():
    """Verify that valid live/mock TTS returns readable audio bytes with WAV headers."""
    payload = {
        "text": "परीक्षण ऑडियो",
        "voice": "Pranav",
        "model": "timbre-v2.5",
        "language": "hi-IN",
    }
    audio_bytes = gc.call("tts", payload, live=False)
    assert audio_bytes.startswith(b"RIFF"), "TTS audio must start with RIFF header"

    with io.BytesIO(audio_bytes) as bio:
        info = sf.info(bio)
        assert info.samplerate in (16000, 48000), f"Unexpected sample rate: {info.samplerate}"
        assert info.channels == 1, "Must be mono"
        assert info.duration > 0.5, "Duration must be greater than 0.5s"


def test_live_stt_payload_contract(tmp_path):
    """Verify that STT requests validate format and generate properly structured output."""
    wav_file = tmp_path / "test.wav"
    # Write a tiny valid wav file
    bio = io.BytesIO()
    import numpy as np
    sf.write(bio, np.zeros(16000, dtype=np.float32), 16000, format="WAV", subtype="PCM_16")
    wav_file.write_bytes(bio.getvalue())

    payload = {
        "audio": str(wav_file),
        "model": "prisma-v2.5",
        "language_code": "hi-IN",
        "format": "verbatim",
        "mock_transcript": "लूना को साथी पहलवानों ने भी श्रद्धांजलि दी",
    }
    res = gc.call("stt", payload, live=False)
    assert isinstance(res, dict)
    assert res.get("success") is True
    assert res.get("transcript") == "लूना को साथी पहलवानों ने भी श्रद्धांजलि दी"
    assert res.get("model") == "prisma-v2.5"


def test_accounting_persistence_integrity(tmp_path):
    """Verify that CallAccounting state safely saves to and reloads from disk."""
    state_file = tmp_path / "test_accounting.json"
    lock_file = tmp_path / "test_accounting.lock"

    with patch("calllens.gnani_client._get_accounting_paths", return_value=(state_file, lock_file)):
        acc = gc.CallAccounting()
        acc.live_calls = 2
        acc.network_attempts = 2
        acc.mock_calls = 10
        acc._save_to_disk({
            "live_calls": 2,
            "cache_hits": 4,
            "retries": 0,
            "network_attempts": 2,
            "mock_calls": 10,
        })

        assert state_file.exists()
        loaded = acc._sync_from_disk()
        assert loaded["live_calls"] == 2
        assert loaded["network_attempts"] == 2
        assert loaded["mock_calls"] == 10
