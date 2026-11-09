"""Phase E: Security and Adversarial Injection Tests."""

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


def test_zero_byte_audio_rejected(client):
    """Verify zero-byte audio payload is rejected with 400."""
    res = client.post(
        "/api/stress",
        content=b"",
        headers={"content-type": "audio/wav", "x-condition": "clean"},
    )
    assert res.status_code == 400
    assert "Unable to decode audio stream" in res.json()["detail"]


def test_misleading_extension_rejected(client):
    """Verify file with .wav extension containing plain text is rejected with 400."""
    res = client.post(
        "/api/stress",
        content=b"MZ\x90\x00\x03\x00\x00\x00WindowsExecutableContent",
        headers={"content-type": "audio/wav", "x-condition": "clean"},
    )
    assert res.status_code == 400
    assert "Unable to decode audio stream" in res.json()["detail"]


def test_upload_exact_5mb_boundary(client):
    """Verify file just above 5 MB returns 413, just below 5 MB passes size check."""
    # 5MB + 1 byte
    above_limit = b"0" * (5 * 1024 * 1024 + 1)
    res_above = client.post(
        "/api/stress",
        content=above_limit,
        headers={"content-type": "audio/wav", "x-condition": "clean"},
    )
    assert res_above.status_code == 413

    # Below limit (4.9 MB) but invalid audio -> should get 400 (rejected by audio decoder, not 413)
    below_limit = b"0" * (4 * 1024 * 1024)
    res_below = client.post(
        "/api/stress",
        content=below_limit,
        headers={"content-type": "audio/wav", "x-condition": "clean"},
    )
    assert res_below.status_code == 400
    assert "Unable to decode audio stream" in res_below.json()["detail"]


def test_xss_injection_payloads_do_not_cause_unhandled_errors(client):
    """Verify XSS strings in clip_id or parameters return clean 404/400 without crashing."""
    xss_payloads = [
        "<script>alert(1)</script>",
        "<img src=x onerror=alert('xss')>",
        "javascript:alert(document.cookie)",
    ]
    for p in xss_payloads:
        res = client.post("/api/stress", json={"clip_id": p, "condition": "clean"})
        assert res.status_code == 404
        assert "<script>" not in res.text or "&lt;script&gt;" in res.text


def test_path_traversal_payloads_rejected(client):
    """Verify path traversal in clip_id cannot escape directory."""
    traversal_payloads = [
        "../../.env",
        "..\\..\\.env",
        "/etc/passwd",
        "....//....//calllens.db",
    ]
    for p in traversal_payloads:
        res = client.post("/api/stress", json={"clip_id": p, "condition": "clean"})
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()


def test_sql_injection_payloads_handled_safely(client):
    """Verify SQL injection strings are safely escaped by ORM."""
    sql_payloads = [
        "' OR '1'='1",
        "'; DROP TABLE benchmark_results; --",
        "admin'--",
    ]
    for p in sql_payloads:
        res = client.post("/api/stress", json={"clip_id": p, "condition": "clean"})
        assert res.status_code == 404


def test_unusual_unicode_and_null_bytes(client):
    """Verify null bytes and unusual Unicode characters do not cause unhandled crashes."""
    res = client.post("/api/stress", json={"clip_id": "clip\x00injection", "condition": "clean"})
    assert res.status_code in (400, 404)
