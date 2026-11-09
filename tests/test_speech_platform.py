"""Tests for the complete CallLens Speech Intelligence Platform:
- STT Studio API (transcription, validation, formats)
- TTS Studio API (synthesis, voices, audio serving)
- Audit History API
- Live Speech WebSocket lifecycle
"""

import base64
import io
import pytest
import soundfile as sf
import numpy as np
from fastapi.testclient import TestClient

from app.main import app, _request_timestamps
from calllens import history


@pytest.fixture
def client():
    _request_timestamps.clear()
    return TestClient(app)


def _generate_test_wav_bytes(duration_sec: float = 1.0, sr: int = 16000) -> bytes:
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False, dtype=np.float32)
    signal = 0.1 * np.sin(2 * np.pi * 440 * t)
    bio = io.BytesIO()
    sf.write(bio, signal, sr, format="WAV", subtype="PCM_16")
    return bio.getvalue()


# -------------------------------------------------------------
# STT Studio API Tests
# -------------------------------------------------------------

def test_stt_transcribe_preloaded_clip(client):
    """Verify STT transcription on preloaded benchmark clip."""
    res = client.post(
        "/api/stt/transcribe",
        data={"clip_id": "fleurs_01", "model": "prisma-v2.5", "format": "verbatim", "live": 0},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "transcript" in data
    assert len(data["transcript"]) > 0
    assert data["model"] == "prisma-v2.5"
    assert data["word_count"] > 0
    assert data["duration_sec"] > 0


def test_stt_transcribe_uploaded_wav(client):
    """Verify STT transcription on uploaded WAV file."""
    wav_bytes = _generate_test_wav_bytes(duration_sec=1.5)
    files = {"file": ("test_mic.wav", wav_bytes, "audio/wav")}
    res = client.post(
        "/api/stt/transcribe",
        files=files,
        data={"model": "prisma-v3.0", "language_code": "hi-IN", "live": 0, "mock_transcript": "नमस्ते कॉललेंस"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["transcript"] == "नमस्ते कॉललेंस"
    assert data["model"] == "prisma-v3.0"
    assert data["word_count"] == 2


def test_stt_transcribe_base64_json(client):
    """Verify STT transcription with base64 encoded audio in JSON."""
    wav_bytes = _generate_test_wav_bytes(duration_sec=1.0)
    b64 = base64.b64encode(wav_bytes).decode("utf-8")
    res = client.post(
        "/api/stt/transcribe",
        json={"audio_base64": b64, "model": "prisma-v2.5", "live": 0, "mock_transcript": "ऑडियो परीक्षण"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["transcript"] == "ऑडियो परीक्षण"


def test_stt_transcribe_empty_audio_rejected(client):
    """Verify empty 0-byte upload is rejected with HTTP 400."""
    files = {"file": ("empty.wav", b"", "audio/wav")}
    res = client.post("/api/stt/transcribe", files=files)
    assert res.status_code == 400
    assert "No audio provided" in res.json()["detail"]


def test_stt_transcribe_exceeds_duration_limit(client):
    """Verify audio exceeding 30-second duration is rejected with HTTP 400."""
    long_wav = _generate_test_wav_bytes(duration_sec=32.0)
    files = {"file": ("long.wav", long_wav, "audio/wav")}
    res = client.post("/api/stt/transcribe", files=files)
    assert res.status_code == 400
    assert "exceeds the 30-second limit" in res.json()["detail"]


def test_stt_transcribe_unknown_clip_id_returns_404(client):
    """Verify unknown clip ID returns HTTP 404."""
    res = client.post("/api/stt/transcribe", data={"clip_id": "nonexistent_clip_9999"})
    assert res.status_code == 404
    assert "not found" in res.json()["detail"]


# -------------------------------------------------------------
# TTS Studio API Tests
# -------------------------------------------------------------

def test_tts_voices_catalog(client):
    """Verify TTS voices endpoint returns supported catalog with recommendations."""
    res = client.get("/api/tts/voices")
    assert res.status_code == 200
    data = res.json()
    assert "voices" in data
    assert len(data["voices"]) > 0
    pranav = next((v for v in data["voices"] if v["id"] == "Pranav"), None)
    assert pranav is not None
    assert pranav["recommended"] is True


def test_tts_synthesize_valid_text(client):
    """Verify TTS synthesis returns valid audio metadata and URL."""
    res = client.post(
        "/api/tts/synthesize",
        json={"text": "नमस्ते आपका ऋण भुगतान दिनांक 15 को देय है", "voice": "Pranav", "speed": 1.0, "live": 0},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "audio_url" in data
    assert data["voice"] == "Pranav"
    assert data["duration_sec"] > 0
    assert data["char_count"] > 0

    # Verify audio file is downloadable
    audio_res = client.get(data["audio_url"])
    assert audio_res.status_code == 200
    assert audio_res.headers["content-type"] == "audio/wav"
    assert len(audio_res.content) > 1000


def test_tts_synthesize_empty_text_rejected(client):
    """Verify empty text returns HTTP 400."""
    res = client.post("/api/tts/synthesize", json={"text": "   ", "voice": "Pranav"})
    assert res.status_code == 400
    assert "cannot be empty" in res.json()["detail"]


def test_tts_synthesize_excessive_text_rejected(client):
    """Verify text exceeding 2000 chars is rejected."""
    long_text = "क" * 2050
    res = client.post("/api/tts/synthesize", json={"text": long_text})
    assert res.status_code == 400
    assert "exceeds maximum limit" in res.json()["detail"]


def test_tts_audio_path_traversal_rejected(client):
    """Verify directory traversal in audio filename returns HTTP 400."""
    res = client.get("/api/tts/audio/.._.._secret.wav")
    assert res.status_code == 400


# -------------------------------------------------------------
# History API Tests
# -------------------------------------------------------------

def test_history_crud(client):
    """Verify audit history recording, listing, and clearing."""
    # Clear initial history
    del_res = client.delete("/api/history")
    assert del_res.status_code == 200

    # Make 1 STT request and 1 TTS request
    client.post("/api/stt/transcribe", data={"clip_id": "fleurs_01", "live": 0})
    client.post("/api/tts/synthesize", json={"text": "परीक्षण इतिहास", "voice": "Pranav", "live": 0})

    # Retrieve history
    hist_res = client.get("/api/history?limit=10")
    assert hist_res.status_code == 200
    records = hist_res.json()["history"]
    assert len(records) >= 2
    assert any(r["kind"] == "stt" for r in records)
    assert any(r["kind"] == "tts" for r in records)


# -------------------------------------------------------------
# WebSocket Lifecycle Tests
# -------------------------------------------------------------

def test_websocket_speech_session(client):
    """Verify full interactive speech WebSocket lifecycle."""
    with client.websocket_connect("/ws/speech") as ws:
        # 1. Connect
        msg1 = ws.receive_json()
        assert msg1["type"] == "session_started"
        assert "session_id" in msg1

        # 2. Configure session
        ws.send_json({"action": "start_session", "model": "prisma-v3.0", "language_code": "hi-IN", "format": "transcribe"})
        msg2 = ws.receive_json()
        assert msg2["type"] == "session_configured"
        assert msg2["config"]["model"] == "prisma-v3.0"

        # 3. Stream binary chunks
        chunk = _generate_test_wav_bytes(duration_sec=0.5)
        ws.send_bytes(chunk)
        msg3 = ws.receive_json()
        assert msg3["type"] == "audio_chunk_received"
        assert msg3["total_bytes"] == len(chunk)

        # 4. Finish recording
        ws.send_json({"action": "finish_recording"})
        msg4 = ws.receive_json()
        assert msg4["type"] == "transcription_started"

        msg5 = ws.receive_json()
        assert msg5["type"] == "transcription_completed"
        assert "transcript" in msg5
        assert msg5["model"] == "prisma-v3.0"

        # 5. Interactive synthesis
        ws.send_json({"action": "synthesize", "text": "लाइव प्लेग्राउंड", "voice": "Pranav", "live": 0})
        msg6 = ws.receive_json()
        assert msg6["type"] == "tts_generation_started"

        msg7 = ws.receive_json()
        assert msg7["type"] == "tts_audio_ready"
        assert "audio_base64" in msg7
        assert msg7["duration_sec"] > 0
