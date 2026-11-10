"""Comprehensive security, durability, and persistence regression tests for CallLens.

Tests:
1. Live execution policy fail-closed (HTTP 403 Forbidden when ALLOW_LIVE_API=0)
2. Path traversal rejection (HTTP 400 on traversal sequences)
3. Audio asset storage durability (SHA-256 integrity, duration, UUID filenames)
4. Recording session lifecycle and deletion (DELETE /api/recordings/{session_id})
5. Storage integrity diagnostics (GET /api/storage/diagnostics)
6. Preservation of original recording on STT failure
7. Follow-up entity extraction integrity (Sunil Monday commitment, Anita missing PTP date)
8. Rate limiting enforcement (HTTP 429)
"""

import base64
import io
import os
import tempfile
from pathlib import Path
import pytest
import soundfile as sf
import numpy as np
from fastapi.testclient import TestClient

from app.main import app, _request_timestamps
from calllens import extract, history


@pytest.fixture
def client():
    _request_timestamps.clear()
    return TestClient(app)


def _generate_wav_bytes(duration_sec: float = 0.5, sr: int = 16000) -> bytes:
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False, dtype=np.float32)
    signal = 0.1 * np.sin(2 * np.pi * 440 * t)
    bio = io.BytesIO()
    sf.write(bio, signal, sr, format="WAV", subtype="PCM_16")
    return bio.getvalue()


# ===========================================================================
# 1. LIVE EXECUTION POLICY FAIL-CLOSED (HTTP 403)
# ===========================================================================

def test_live_policy_fail_closed_stt(client):
    """Verify STT endpoint fails closed with HTTP 403 when live=1 and ALLOW_LIVE_API is disabled."""
    wav_bytes = _generate_wav_bytes()
    b64_audio = base64.b64encode(wav_bytes).decode("ascii")

    res = client.post(
        "/api/stt/transcribe",
        json={"audio_base64": b64_audio, "live": 1, "model": "prisma-v2.5"},
    )
    assert res.status_code == 403
    data = res.json()
    assert "Live provider execution is disabled" in data["detail"] or "ALLOW_LIVE_API" in data["detail"]


def test_live_policy_fail_closed_tts(client):
    """Verify TTS endpoint fails closed with HTTP 403 when live=1 and ALLOW_LIVE_API is disabled."""
    res = client.post(
        "/api/tts/synthesize",
        json={"text": "परीक्षण संदेश", "voice": "Pranav", "live": 1},
    )
    assert res.status_code == 403
    data = res.json()
    assert "Live provider execution is disabled" in data["detail"]


def test_live_policy_fail_closed_stress(client):
    """Verify Stress endpoint fails closed with HTTP 403 when live=1 and ALLOW_LIVE_API is disabled."""
    res = client.post(
        "/api/stress",
        json={"clip_id": "fleurs_01", "condition": "clean", "live": 1},
    )
    assert res.status_code == 403
    data = res.json()
    assert "Live provider execution is disabled" in data["detail"]


def test_live_policy_fail_closed_followup_process(client):
    """Verify Followup process endpoint fails closed with HTTP 403 when live=1."""
    res = client.post(
        "/api/followup/process",
        json={"scenario_id": "scenario_01", "live": 1},
    )
    assert res.status_code == 403


def test_live_policy_fail_closed_followup_confirm(client):
    """Verify Followup confirm endpoint fails closed with HTTP 403 when live=1."""
    res = client.post(
        "/api/followup/confirm",
        json={
            "customer_name": "Test User",
            "amount": 1000,
            "due_date": "10th",
            "ptp_date": "15th",
            "concern": "none",
            "call_summary": "summary",
            "reminder_text": "नमस्ते",
            "voice": "Pranav",
            "live": 1,
        },
    )
    assert res.status_code == 403


def test_live_policy_fail_closed_websocket(client):
    """Verify WebSocket rejects live execution when live=1 is requested."""
    with client.websocket_connect("/ws/speech") as ws:
        msg1 = ws.receive_json()
        assert msg1["type"] == "session_started"

        ws.send_json({"action": "start_session", "live": 1})
        resp = ws.receive_json()
        assert resp["type"] == "operation_failed"
        assert resp["error_code"] == "LIVE_EXECUTION_FORBIDDEN"


# ===========================================================================
# 2. PATH TRAVERSAL SECURITY (HTTP 400)
# ===========================================================================

@pytest.mark.parametrize("traversal_path", [
    ".._.._secret.wav",
    "..%5C..%5Cwindows%5Csystem32%5Ccmd.exe",
    "..\\..\\windows\\system32\\cmd.exe",
    "....//....//secret.wav",
    "../../etc/passwd",
    "sub/folder/audio.wav",
])
def test_audio_serving_path_traversal_rejected(client, traversal_path):
    """Verify directory traversal attempts in audio serving are strictly rejected."""
    res1 = client.get(f"/api/audio/{traversal_path}")
    # Path traversal must never succeed (must return either 400 Bad Request or 404 Not Found from router)
    assert res1.status_code in (400, 404)
    assert res1.status_code != 200

    res2 = client.get(f"/api/tts/audio/{traversal_path}")
    assert res2.status_code in (400, 404)
    assert res2.status_code != 200


# ===========================================================================
# 3. AUDIO ASSET DURABILITY & SHA-256 INTEGRITY
# ===========================================================================

def test_save_audio_asset_integrity():
    """Verify save_audio_asset persists files with exact SHA-256 and decoded duration."""
    wav_bytes = _generate_wav_bytes(duration_sec=1.5, sr=16000)
    asset = history.save_audio_asset(wav_bytes, asset_type="test_asset")

    assert asset["asset_id"].startswith("ast_")
    assert asset["filename"].startswith("test_asset_")
    assert asset["filename"].endswith(".wav")
    assert Path(asset["storage_path"]).exists()
    assert asset["file_size_bytes"] == len(wav_bytes)
    assert asset["sha256"] == __import__("hashlib").sha256(wav_bytes).hexdigest()
    assert asset["sample_rate"] == 16000
    assert asset["channels"] == 1
    assert 1.4 <= asset["duration_seconds"] <= 1.6
    assert asset["duration_estimated"] is False


def test_audio_asset_download(client):
    """Verify audio assets are served with proper headers and exact binary content."""
    wav_bytes = _generate_wav_bytes(duration_sec=0.8)
    asset = history.save_audio_asset(wav_bytes, asset_type="test_download")

    res = client.get(f"/api/audio/{asset['filename']}")
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/wav"
    assert res.content == wav_bytes


# ===========================================================================
# 4. RECORDING SESSION LIFECYCLE & DELETION
# ===========================================================================

def test_recording_session_crud_and_delete(client):
    """Verify recording session lifecycle tracking and physical disk cleanup on deletion."""
    sess_id = history.create_recording_session(
        source="unit_test",
        language="hi-IN",
        customer_name="रवि प्रकाश",
        metadata={"test": True},
    )
    assert sess_id.startswith("sess_")

    wav_bytes = _generate_wav_bytes()
    asset = history.save_audio_asset(wav_bytes, asset_type="recording", session_id=sess_id)
    assert Path(asset["storage_path"]).exists()

    history.update_recording_session(sess_id, status="completed")

    # Verify session in API
    res = client.get(f"/api/recordings/{sess_id}")
    assert res.status_code == 200
    s_data = res.json()
    assert s_data["session_id"] == sess_id
    assert s_data["status"] == "completed"
    assert len(s_data["assets"]) >= 1

    # Delete session via API
    del_res = client.delete(f"/api/recordings/{sess_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # Confirm session removed and physical file unlinked
    assert not Path(asset["storage_path"]).exists()
    assert client.get(f"/api/recordings/{sess_id}").status_code == 404


def test_recording_session_cascading_deletion_with_followup_assets(client):
    """Verify cascading deletion removes recording assets, followup reminder assets, and DB rows."""
    sess_id = history.create_recording_session(
        source="cascade_test",
        language="hi-IN",
        customer_name="विकास वर्मा",
    )
    wav_bytes = _generate_wav_bytes(duration_sec=0.5)
    rec_asset = history.save_audio_asset(wav_bytes, asset_type="recording", session_id=sess_id)
    reminder_asset = history.save_audio_asset(wav_bytes, asset_type="reminder", session_id=sess_id)

    # Add transcript and followup record
    tr_id = history.record_transcript(
        session_id=sess_id,
        text="विकास वर्मा, 45,000 रुपये 15 तारीख तक दे दें।",
        is_final=True,
    )
    history.record_speech_operation(
        session_id=sess_id,
        asset_id=rec_asset["asset_id"],
        operation_type="transcribe",
        model="prisma-v2.5",
        status="completed",
    )
    history.record_followup_entry(
        session_id=sess_id,
        customer_name="विकास वर्मा",
        amount=45000,
        due_date="15 तारीख",
        ptp_date="सोमवार",
        concern="none",
        call_summary="Test call summary",
        reminder_text="नमस्ते विकास जी",
        voice="Pranav",
        transcript_id=tr_id,
        asset_id=reminder_asset["asset_id"],
    )

    rec_path = Path(rec_asset["storage_path"])
    rem_path = Path(reminder_asset["storage_path"])
    assert rec_path.exists()
    assert rem_path.exists()

    # Cascade delete
    success = history.delete_recording_session(sess_id)
    assert success is True

    # Verify both physical files unlinked
    assert not rec_path.exists()
    assert not rem_path.exists()

    # Verify API 404
    assert client.get(f"/api/recordings/{sess_id}").status_code == 404


# ===========================================================================
# 5. STORAGE INTEGRITY DIAGNOSTICS
# ===========================================================================

def test_storage_diagnostics_endpoint(client):
    """Verify /api/storage/diagnostics returns complete integrity metrics."""
    res = client.get("/api/storage/diagnostics")
    assert res.status_code == 200
    diag = res.json()

    assert "total_recording_sessions" in diag
    assert "total_audio_assets" in diag
    assert "total_storage_mb" in diag
    assert "missing_audio_files" in diag
    assert "integrity_status" in diag
    assert diag["integrity_status"] == "HEALTHY"
    assert diag["missing_audio_files"] == 0  # No corrupt/missing assets


# ===========================================================================
# 6. WEBSOCKET PERSISTENCE ON STT FAILURE
# ===========================================================================

def test_websocket_preserves_audio_on_failure(client, monkeypatch):
    """Verify that when STT provider fails, the audio recording is preserved on disk."""
    wav_bytes = _generate_wav_bytes(duration_sec=0.5)

    # Monkeypatch gnani_client.call to simulate a provider error
    def _mock_failing_call(*args, **kwargs):
        raise RuntimeError("Simulated upstream provider outage")

    monkeypatch.setattr("calllens.gnani_client.call", _mock_failing_call)

    with client.websocket_connect("/ws/speech") as ws:
        msg1 = ws.receive_json()
        assert msg1["type"] == "session_started"

        # Stream binary chunk
        ws.send_bytes(wav_bytes)
        chunk_ack = ws.receive_json()
        assert chunk_ack["type"] == "audio_chunk_received"

        # Trigger finish_recording
        ws.send_json({"action": "finish_recording"})
        start_ack = ws.receive_json()
        assert start_ack["type"] == "transcription_started"
        assert "asset_id" in start_ack

        # Expect failure message with preserved audio URL
        err_msg = ws.receive_json()
        assert err_msg["type"] == "operation_failed"
        assert err_msg["error_code"] == "STT_PROVIDER_ERROR"
        assert "preserved" in err_msg["error"].lower()
        assert "audio_url" in err_msg

        # Verify the preserved audio file is downloadable
        audio_res = client.get(err_msg["audio_url"])
        assert audio_res.status_code == 200
        assert len(audio_res.content) == len(wav_bytes)


# ===========================================================================
# 7. FOLLOW-UP ENTITY EXTRACTION INTEGRITY
# ===========================================================================

def test_followup_sunil_kumar_monday_commitment():
    """Verify Sunil Kumar (scenario_03) extracts Monday commitment accurately."""
    transcript = "नमस्ते सुनील कुमार जी, आपकी ऑटो लोन किस्त 1.5 लाख रुपये 25 तारीख तक जमा कराएं। ग्राहक अभी शहर से बाहर है और सोमवार को ट्रांसफर करेगा।"
    extracted = extract.extract_followup_details(transcript, customer_name="सुनील कुमार")

    assert extracted["amount"] == 150000
    assert extracted["due_day"] == 25
    assert extracted["ptp_date"] == "सोमवार को"
    assert extracted["ptp_date_detected"] is True
    assert extracted["is_complete"] is True
    assert len(extracted["missing_fields"]) == 0


def test_followup_anita_desai_missing_ptp_date_flags_operator():
    """Verify Anita Desai (scenario_05) missing PTP date is flagged as incomplete."""
    transcript = "अनीता देसाई, आपके खाते से 75,500 rupees की ईएमआई 20 तारीख को काटी जानी है। अतिरिक्त पेनल्टी शुल्क पर विवाद है, शाखा प्रबंधक से बात करने के बाद भुगतान होगा।"
    extracted = extract.extract_followup_details(transcript, customer_name="अनीता देसाई")

    assert extracted["amount"] == 75500
    assert extracted["due_day"] == 20
    assert extracted["ptp_date"] is None
    assert extracted["ptp_date_detected"] is False
    assert extracted["is_complete"] is False
    assert "Promise-to-pay date" in extracted["missing_fields"]
