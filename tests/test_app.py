"""Unit and integration tests for FastAPI application (app/main.py)."""

import io
import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from app.main import app, _request_timestamps


@pytest.fixture
def client():
    _request_timestamps.clear()
    return TestClient(app)


def test_get_index(client):
    """Verify GET / returns 200 and HTML index."""
    res = client.get("/")
    assert res.status_code == 200
    assert "CallLens Stress Lab" in res.text


def test_get_health(client):
    """Verify GET /api/health status and configuration."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["default_mode"] == "replay_live"
    assert data["default_mode_label"] == "Replay of recorded live runs"
    assert "clean" in data["supported_conditions"]


def test_default_mode_replays_live_and_reports_no_live_results_yet(client):
    """Verify default mode replays live runs and returns 'no live results yet' when DB has no live rows."""
    clips_res = client.get("/api/clips").json()["clips"]
    clip_id = clips_res[0]["id"]
    res = client.post(
        "/api/stress",
        json={"clip_id": clip_id, "condition": "clean", "live": 0, "allow_mock": False},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["has_live_results"] is False
    assert "no live results yet" in data["message"].lower()
    assert data["mode"] == "replay_live"
    assert data["mode_label"] == "Replay of recorded live runs"


def test_default_mode_replays_live_rows_when_present(client, tmp_path, monkeypatch):
    """Verify default mode successfully replays recorded live rows when present in DB."""
    from calllens.benchmark import BenchmarkResult, get_db_session

    db_file = tmp_path / "benchmark.db"
    session = get_db_session(f"sqlite:///{db_file}")

    rec_v25 = BenchmarkResult(
        experiment="A",
        clip_id="fleurs_test_clip",
        condition="clean",
        model="prisma-v2.5",
        format="verbatim",
        reference_text="नमस्ते भारत",
        hypothesis_text="नमस्ते भारत",
        wer=0.0,
        cer=0.0,
        latency_sec=0.75,
        duration_sec=3.2,
        rtf=0.23,
        from_cache=False,
        mock=False,
        provenance="live",
    )
    rec_v30 = BenchmarkResult(
        experiment="A",
        clip_id="fleurs_test_clip",
        condition="clean",
        model="prisma-v3.0",
        format="verbatim",
        reference_text="नमस्ते भारत",
        hypothesis_text="नमस्ते भारत",
        wer=0.0,
        cer=0.0,
        latency_sec=0.62,
        duration_sec=3.2,
        rtf=0.19,
        from_cache=False,
        mock=False,
        provenance="live",
    )
    session.add(rec_v25)
    session.add(rec_v30)
    session.commit()
    session.close()

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    res = client.post(
        "/api/stress",
        json={"clip_id": "fleurs_test_clip", "condition": "clean", "live": 0, "allow_mock": False},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["has_live_results"] is True
    assert data["mode"] == "replay_live"
    assert data["mode_label"] == "Replay of recorded live runs"
    assert data["provenance"] == "live"
    assert data["prisma_v25"]["transcript"] == "नमस्ते भारत"
    assert data["prisma_v30"]["transcript"] == "नमस्ते भारत"


def test_get_clips(client):
    """Verify GET /api/clips returns available test clips."""
    res = client.get("/api/clips")
    assert res.status_code == 200
    data = res.json()
    assert "clips" in data
    assert len(data["clips"]) > 0


def test_stress_endpoint_valid_clip(client):
    """Verify POST /api/stress returns evaluation comparison for a valid clip."""
    clips_res = client.get("/api/clips").json()["clips"]
    clip_id = clips_res[0]["id"]

    res = client.post(
        "/api/stress",
        json={"clip_id": clip_id, "condition": "tel", "live": 0},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "prisma_v25" in data
    assert "prisma_v30" in data
    assert data["prisma_v25"]["format"] == "verbatim"
    assert data["prisma_v30"]["format"] == "verbatim"


def test_stress_endpoint_invalid_clip(client):
    """Verify POST /api/stress returns 404 for non-existent clip ID."""
    res = client.post(
        "/api/stress",
        json={"clip_id": "non_existent_clip_12345", "condition": "clean"},
    )
    assert res.status_code == 404


def test_stress_endpoint_invalid_condition(client):
    """Verify POST /api/stress returns 400 for unknown condition."""
    res = client.post(
        "/api/stress",
        json={"clip_id": "fleurs_01", "condition": "underwater_noise"},
    )
    assert res.status_code == 400
    assert "Invalid condition" in res.json()["detail"]


def test_stress_endpoint_rejects_oversized_upload(client):
    """Verify upload exceeding 5 MB returns 413 Payload Too Large."""
    oversized_data = b"0" * (5 * 1024 * 1024 + 1024)
    res = client.post(
        "/api/stress",
        content=oversized_data,
        headers={"content-type": "audio/wav", "x-condition": "clean"},
    )
    assert res.status_code == 413
    assert "exceeds maximum upload size" in res.json()["detail"]


def test_stress_endpoint_rejects_audio_over_30_seconds(client):
    """Verify audio longer than 30 seconds is rejected with 400."""
    sr = 16000
    audio = np.zeros(int(sr * 32.0), dtype=np.float32)
    bio = io.BytesIO()
    sf.write(bio, audio, sr, format="WAV", subtype="PCM_16")

    res = client.post(
        "/api/stress",
        content=bio.getvalue(),
        headers={"content-type": "audio/wav", "x-condition": "clean"},
    )
    assert res.status_code == 400
    assert "exceeds the 30-second limit" in res.json()["detail"]


def test_stress_endpoint_rejects_corrupt_audio(client):
    """Verify corrupt/non-audio upload is rejected with 400."""
    fake_data = b"This is plain text, not a valid WAV or audio file."
    res = client.post(
        "/api/stress",
        content=fake_data,
        headers={"content-type": "audio/wav", "x-condition": "clean"},
    )
    assert res.status_code == 400
    assert "Unable to decode audio stream" in res.json()["detail"]


def test_rate_limiting(client):
    """Verify rate limiter blocks request 11 within 60 seconds (returns 429)."""
    for _ in range(10):
        res = client.post(
            "/api/stress",
            json={"clip_id": "fleurs_01", "condition": "clean"},
        )
        assert res.status_code in (200, 404)

    res_11 = client.post(
        "/api/stress",
        json={"clip_id": "fleurs_01", "condition": "clean"},
    )
    assert res_11.status_code == 429
    assert "Rate limit exceeded" in res_11.json()["detail"]
