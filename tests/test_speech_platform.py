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


def test_followup_scenarios_catalog(client):
    """Verify GET /api/followup/scenarios returns curated banking scenarios."""
    res = client.get("/api/followup/scenarios")
    assert res.status_code == 200
    data = res.json()
    assert "scenarios" in data
    assert len(data["scenarios"]) >= 5
    first = data["scenarios"][0]
    assert "id" in first
    assert "customer_name" in first
    assert "dialogue_text" in first
    assert "reference_amount" in first


def test_followup_process_scenario(client):
    """Verify POST /api/followup/process accurately extracts fields from a scenario."""
    res = client.post(
        "/api/followup/process",
        json={"clip_id": "scenario_01", "model": "prisma-v3.0", "live": 0},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "transcript" in data
    extracted = data["extracted"]
    assert extracted["amount"] == 50000
    assert extracted["due_day"] == 5
    assert "10" in extracted["ptp_date"]
    assert "Salary delay" in extracted["concern"]
    assert "राहुल शर्मा" in extracted["suggested_reminder"]
    assert extracted["is_complete"] is True


def test_followup_process_missing_fields_not_assumed(client):
    """Verify POST /api/followup/process never invents missing dates or amounts."""
    res = client.post(
        "/api/followup/process",
        json={
            "mock_transcript": "नमस्ते, मैं केवल अपने खाते के बारे में बात करना चाहता हूँ।",
            "model": "prisma-v3.0",
            "live": 0,
        },
    )
    assert res.status_code == 200
    data = res.json()
    extracted = data["extracted"]
    assert extracted["amount"] is None
    assert extracted["amount_formatted"] == "Not detected"
    assert extracted["due_day"] is None
    assert extracted["due_date_formatted"] == "Not detected"
    assert extracted["ptp_date"] is None
    assert extracted["ptp_date_formatted"] == "Not detected"
    assert extracted["is_complete"] is False


def test_followup_confirm_and_synthesize(client):
    """Verify POST /api/followup/confirm synthesizes verified reminder and logs to history."""
    payload = {
        "customer_name": "राहुल शर्मा",
        "amount": 50000,
        "due_date": "5 तारीख",
        "ptp_date": "10 तारीख",
        "concern": "Salary delay (वेतन में देरी)",
        "call_summary": "बकाया राशि ₹50,000 • देय तिथि 5 तारीख • वेतन में देरी • वचनबद्ध तिथि 10 तारीख।",
        "reminder_text": "नमस्ते राहुल शर्मा जी, आपके खाते का ₹50,000 का भुगतान 10 तारीख तक करने का आपका वादा था। धन्यवाद।",
        "voice": "Pranav",
        "speed": 1.0,
        "live": 0,
    }
    res = client.post("/api/followup/confirm", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "audio_url" in data
    assert data["audio_url"].startswith("/api/tts/audio/")
    assert data["history_id"] > 0
    assert data["confirmed_record"]["customer_name"] == "राहुल शर्मा"

    # Verify history persistence
    hist_res = client.get("/api/history?kind=followup")
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    records = hist_data["history"]
    assert len(records) > 0
    latest = records[0]
    assert latest["kind"] == "followup"
    assert "राहुल शर्मा" in latest["input_preview"]
    assert latest["metadata"]["amount"] == 50000
    assert latest["metadata"]["ptp_date"] == "10 तारीख"


# -------------------------------------------------------------
# Forensic End-to-End Bugfix Regression Tests
# -------------------------------------------------------------

def test_tts_response_structure_and_duration_fields(client):
    """Verify TTS response contains both duration_sec and audio_duration_sec,

    both char_count and character_count, and normalizes voice casing.
    """
    res = client.post(
        "/api/tts/synthesize",
        json={"text": "नमस्ते कॉललेंस", "voice": "pranav", "speed": 1.0, "live": 0},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "audio_duration_sec" in data
    assert "duration_sec" in data
    assert data["audio_duration_sec"] == data["duration_sec"]
    assert "character_count" in data
    assert "char_count" in data
    assert data["character_count"] == data["char_count"] == len("नमस्ते कॉललेंस")
    assert data["voice"] == "Pranav"
    assert "audio_url" in data


def test_stt_response_structure_and_alias_fields(client):
    """Verify STT response contains both audio_duration_sec and duration_sec,

    both lang and language_code, both char_count and character_count.
    """
    res = client.post(
        "/api/stt/transcribe",
        json={"clip_id": "fleurs_01", "model": "prisma-v2.5", "format": "verbatim", "live": 0},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "audio_duration_sec" in data
    assert "duration_sec" in data
    assert data["audio_duration_sec"] == data["duration_sec"]
    assert "lang" in data
    assert "language_code" in data
    assert data["lang"] == data["language_code"]
    assert "character_count" in data
    assert "char_count" in data
    assert data["character_count"] == data["char_count"]


def test_history_response_format_and_fields(client):
    """Verify /api/history returns both 'history' and 'records' arrays,

    'total_count' integer, and records contain created_at, model_or_voice, and audio_url.
    """
    res = client.get("/api/history?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert "history" in data
    assert "records" in data
    assert "total_count" in data
    assert isinstance(data["records"], list)
    assert data["records"] == data["history"]
    assert data["total_count"] == len(data["records"])

    if len(data["records"]) > 0:
        rec = data["records"][0]
        assert "created_at" in rec
        assert "timestamp" in rec
        assert "model_or_voice" in rec
        assert "audio_filename" in rec


def test_tts_voices_catalog_aliases(client):
    """Verify /api/tts/voices includes aliases for voice, lang, and is_recommended."""
    res = client.get("/api/tts/voices")
    assert res.status_code == 200
    data = res.json()
    assert "voices" in data
    assert len(data["voices"]) >= 2
    for v in data["voices"]:
        assert "voice" in v
        assert "name" in v
        assert "id" in v
        assert "lang" in v
        assert "language" in v
        assert "recommended" in v
        assert "is_recommended" in v


def test_followup_lowercase_voice_handled(client):
    """Verify POST /api/followup/confirm handles lowercase voice names gracefully."""
    res = client.post(
        "/api/followup/confirm",
        json={
            "customer_name": "सुनील कुमार",
            "amount": 12000,
            "reminder_text": "नमस्ते सुनील जी, आपका भुगतान बकाया है।",
            "voice": "kaveri",
            "live": 0,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["voice"] == "Kaveri"
    assert "audio_url" in data
    assert "duration_s" in data
    assert "duration_sec" in data


def test_websocket_stop_event_lifecycle(client):
    """Verify WebSocket /ws/speech accepts {'type': 'stop'} signal."""
    with client.websocket_connect("/ws/speech") as ws:
        msg1 = ws.receive_json()
        assert msg1["type"] == "session_started"

        # Send raw chunk
        ws.send_bytes(b"\x00\x00" * 800)
        msg2 = ws.receive_json()
        assert msg2["type"] == "audio_chunk_received"
        assert msg2["total_bytes"] == 1600

        # Send stop event
        ws.send_json({"type": "stop"})
        msg3 = ws.receive_json()
        assert msg3["type"] == "transcription_started"
        assert "audio_url" in msg3

        msg4 = ws.receive_json()
        assert msg4["type"] == "transcription_completed"
        assert "transcript" in msg4
        assert "latency_sec" in msg4


def test_noise_suppression_algorithm():
    """Verify spectral subtraction noise suppression algorithm in degrade.py."""
    import numpy as np
    from calllens import degrade

    sr = 16000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    pure_tone = (0.5 * np.sin(2 * np.pi * 500 * t)).astype(np.float32)
    noise = np.random.normal(0, 0.15, sr).astype(np.float32)
    noisy_signal = pure_tone + noise

    cleaned = degrade.suppress_noise(noisy_signal, sr=sr, alpha=1.8, beta=0.05)
    assert len(cleaned) == len(noisy_signal)
    assert isinstance(cleaned, np.ndarray)
    assert cleaned.dtype == np.float32
    # Check that peak amplitude remains bounded
    assert np.max(np.abs(cleaned)) <= 1.0


def test_stress_api_with_denoise_option(client):
    """Verify POST /api/stress accepts denoise=True and returns denoised results."""
    # Read sample clip or small WAV
    sample_wav = b"RIFF" + (36 + 1600).to_bytes(4, "little") + b"WAVEfmt " + (16).to_bytes(4, "little") + (1).to_bytes(2, "little") + (1).to_bytes(2, "little") + (16000).to_bytes(4, "little") + (32000).to_bytes(4, "little") + (2).to_bytes(2, "little") + (16).to_bytes(2, "little") + b"data" + (1600).to_bytes(4, "little") + (b"\x00\x00" * 800)

    import base64
    payload = {
        "condition": "tel_snr10",
        "live": 0,
        "allow_mock": True,
        "audio_base64": base64.b64encode(sample_wav).decode("ascii"),
        "denoise": True,
    }
    res = client.post("/api/stress", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "denoise" in data
    assert data["denoise"]["applied"] is True
    assert "denoised_audio_url" in data["denoise"]
    assert data["denoise"]["denoised_audio_url"] is not None


def test_websocket_incremental_partial_transcription(client):
    """Verify WebSocket emits transcript_partial interim hypotheses during streaming."""
    with client.websocket_connect("/ws/speech") as ws:
        msg1 = ws.receive_json()
        assert msg1["type"] == "session_started"

        # Stream enough audio bytes to cross the 32 KB threshold (32,000 bytes)
        chunk = b"\x00\x00" * 8500  # 17,000 bytes per chunk
        ws.send_bytes(chunk)
        msg2 = ws.receive_json()
        assert msg2["type"] == "audio_chunk_received"

        ws.send_bytes(chunk)  # Now 34,000 bytes total (triggers partial hypothesis)
        msg3 = ws.receive_json()
        assert msg3["type"] == "audio_chunk_received"

        # Should receive transcript_partial message
        msg_partial = ws.receive_json()
        assert msg_partial["type"] == "transcript_partial"
        assert "transcript" in msg_partial
        assert msg_partial["is_final"] is False
        assert msg_partial["audio_seconds"] > 0

        # Also test explicit partial request
        ws.send_json({"action": "request_partial"})
        msg_req = ws.receive_json()
        assert msg_req["type"] == "transcript_partial"

        # Complete session
        ws.send_json({"action": "stop"})
        msg_start = ws.receive_json()
        assert msg_start["type"] == "transcription_started"
        msg_done = ws.receive_json()
        assert msg_done["type"] == "transcription_completed"


def test_storage_cleanup_endpoint(client):
    """Verify POST /api/storage/cleanup safely executes and returns telemetry."""
    res = client.post("/api/storage/cleanup?max_age_hours=0&prune_temp_only=true")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "cleaned_temp_files" in data
    assert "freed_mb" in data


def test_multilingual_followup_scenarios_and_extraction(client):
    """Verify multilingual scenarios exist and extract English/Indic entities accurately."""
    from calllens import extract

    res = client.get("/api/followup/scenarios")
    assert res.status_code == 200
    scenarios = res.json()["scenarios"]
    assert len(scenarios) >= 7

    # Find scenario 06 (Karthik Subramanian)
    s06 = next((s for s in scenarios if s["id"] == "scenario_06"), None)
    assert s06 is not None
    assert s06["customer_name"] == "Karthik Subramanian"
    assert s06["reference_amount"] == 85000

    # Test extraction
    details = extract.extract_followup_details(s06["dialogue_text"])
    assert details["amount"] == 85000
    assert details["due_day"] == 10
    assert details["ptp_date"] is not None


def test_database_composite_indexes():
    """Verify composite indexes exist on historical and session tables."""
    from calllens import history
    session = history._get_db_session()
    try:
        from sqlalchemy import text
        # Inspect indexes on speech_operations
        rows = session.execute(text("PRAGMA index_list(speech_operations)")).fetchall()
        index_names = [r[1] for r in rows]
        assert "idx_speech_operations_type_created" in index_names

        # Inspect indexes on recording_sessions
        rows2 = session.execute(text("PRAGMA index_list(recording_sessions)")).fetchall()
        index_names2 = [r[1] for r in rows2]
        assert "idx_recording_sessions_status_created" in index_names2

        # Inspect indexes on audio_history
        rows3 = session.execute(text("PRAGMA index_list(audio_history)")).fetchall()
        index_names3 = [r[1] for r in rows3]
        assert "idx_audio_history_kind_timestamp" in index_names3
    finally:
        session.close()


def test_followup_records_endpoint(client):
    """Verify GET /api/followup/records returns persisted operator records."""
    post_res = client.post(
        "/api/followup/confirm",
        json={
            "customer_name": "विक्रम साराभाई",
            "amount": 45000,
            "reminder_text": "नमस्ते विक्रम जी, यह आपकी बकाया राशि की सूचना है।",
            "voice": "pranav",
            "live": 0,
        },
    )
    assert post_res.status_code == 200

    res = client.get("/api/followup/records?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "records" in data
    assert isinstance(data["records"], list)
    assert len(data["records"]) >= 1

    rec = data["records"][0]
    assert "followup_id" in rec
    assert "customer_name" in rec
    assert "amount" in rec
    assert "verification_status" in rec
    assert "confirmed_at" in rec


def test_history_csv_export_endpoint(client):
    """Verify GET /api/history?format=csv returns downloadable CSV with proper headers and UTF-8 BOM."""
    res = client.get("/api/history?format=csv&limit=20")
    assert res.status_code == 200
    assert "text/csv" in res.headers.get("content-type", "")
    assert "calllens_audit_history.csv" in res.headers.get("content-disposition", "")
    assert res.content.startswith(b"\xef\xbb\xbf")
    content = res.text
    assert "ID,Kind,Timestamp,Model/Voice,Language,Latency_s,Duration_s,Status,Input_Preview,Output_Preview,Audio_Filename" in content


def test_delete_history_item_endpoint(client):
    """Verify DELETE /api/history/{id} deletes the item from database."""
    from calllens import history
    hist_id = history.record_tts_history(
        model="Gnani Timbre",
        voice="Pranav",
        language="hi-IN",
        text="परीक्षण ऑडियो",
        duration_sec=1.5,
        latency_sec=0.25,
        audio_filename="test_delete_temp.wav",
    )
    assert hist_id > 0

    res = client.delete(f"/api/history/{hist_id}")
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.json()["deleted_id"] == hist_id

    res2 = client.delete(f"/api/history/{hist_id}")
    assert res2.status_code == 404


def test_ensure_wav_bytes_utility():
    """Verify ensure_wav_bytes wraps raw PCM in valid RIFF/WAV header."""
    from calllens.history import ensure_wav_bytes
    import wave

    raw_pcm = b"\x00\x00" * 16000  # 1.0 second of 16kHz 16-bit mono PCM (32000 bytes)
    wav_bytes = ensure_wav_bytes(raw_pcm, sample_rate=16000, channels=1)

    assert wav_bytes.startswith(b"RIFF")
    with io.BytesIO(wav_bytes) as bio:
        with wave.open(bio, "rb") as wf:
            assert wf.getframerate() == 16000
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getnframes() == 16000


def test_websocket_audio_duration_against_wav_and_pcm_headers(client):
    """Regression test: verify WebSocket calculates duration accurately from headers and raw PCM."""
    import soundfile as sf
    import numpy as np

    # Test A: Send 2.5 seconds of valid WAV audio
    t = np.linspace(0, 2.5, int(16000 * 2.5), endpoint=False, dtype=np.float32)
    sig = 0.2 * np.sin(2 * np.pi * 440 * t)
    bio = io.BytesIO()
    sf.write(bio, sig, 16000, format="WAV", subtype="PCM_16")
    wav_data = bio.getvalue()

    with client.websocket_connect("/ws/speech") as ws:
        msg_init = ws.receive_json()
        assert msg_init["type"] == "session_started"

        ws.send_bytes(wav_data)
        res_chunk = ws.receive_json()
        assert res_chunk["type"] == "audio_chunk_received"

        ws.send_json({"type": "stop"})
        msg_next = ws.receive_json()
        if msg_next["type"] == "transcript_partial":
            msg_start = ws.receive_json()
        else:
            msg_start = msg_next
        assert msg_start["type"] == "transcription_started"

        msg_done = ws.receive_json()
        assert msg_done["type"] == "transcription_completed"
        # Duration must match 2.5s within 0.05s
        assert abs(msg_done["duration_sec"] - 2.5) < 0.05
        assert abs(msg_done["audio_duration_sec"] - 2.5) < 0.05

    # Test B: Send 1.0 second of raw PCM bytes (32,000 bytes) without WAV header
    raw_pcm = b"\x00\x00" * 16000  # 32,000 bytes
    with client.websocket_connect("/ws/speech") as ws:
        msg_init = ws.receive_json()
        assert msg_init["type"] == "session_started"

        ws.send_bytes(raw_pcm)
        res_chunk = ws.receive_json()
        assert res_chunk["type"] == "audio_chunk_received"

        ws.send_json({"type": "stop"})
        msg_next2 = ws.receive_json()
        if msg_next2["type"] == "transcript_partial":
            msg_start2 = ws.receive_json()
        else:
            msg_start2 = msg_next2
        assert msg_start2["type"] == "transcription_started"

        msg_done = ws.receive_json()
        assert msg_done["type"] == "transcription_completed"
        # Must calculate exact 1.0s, NOT the old hardcoded 2.0s fallback!
        assert abs(msg_done["duration_sec"] - 1.0) < 0.05
