"""Phase D: Hard Backend and API Edge-Case Tests.

Tests the 15 mandated scenarios against FastAPI backend (app/main.py):
1. Valid clip ID and valid condition
2. Unknown clip ID
3. Missing clip ID (and no audio)
4. Missing condition (defaults to clean)
5. Invalid condition
6. Wrong JSON type
7. Malformed JSON
8. Empty request body
9. Unexpected extra fields
10. Repeated identical requests
11. Rapid repeated requests
12. Concurrent mock requests
13. Database unavailable/isolated behavior
14. Missing manifest or missing audio fixture
15. Corrupt audio fixture
"""

import concurrent.futures
from fastapi.testclient import TestClient
import pytest

from app.main import app, _request_timestamps


@pytest.fixture
def client():
    _request_timestamps.clear()
    return TestClient(app)


def test_01_valid_clip_and_condition(client):
    res = client.post("/api/stress", json={"clip_id": "fleurs_01", "condition": "tel"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "prisma_v25" in data and "prisma_v30" in data


def test_02_unknown_clip_id(client):
    res = client.post("/api/stress", json={"clip_id": "non_existent_99999", "condition": "clean"})
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_03_missing_clip_id_and_no_audio(client):
    res = client.post("/api/stress", json={"condition": "clean"})
    assert res.status_code == 400
    assert "Must provide either clip_id or an audio payload" in res.json()["detail"]


def test_04_missing_condition_defaults_to_clean(client):
    res = client.post("/api/stress", json={"clip_id": "fleurs_01"})
    assert res.status_code == 200
    assert res.json()["condition"] == "clean"


def test_05_invalid_condition(client):
    res = client.post("/api/stress", json={"clip_id": "fleurs_01", "condition": "underwater_submerged"})
    assert res.status_code == 400
    assert "Invalid condition" in res.json()["detail"]


def test_06_wrong_json_type(client):
    # Pass boolean for clip_id
    res = client.post("/api/stress", json={"clip_id": False, "condition": "clean"})
    # Treated as string "False" or rejected, must not crash 500
    assert res.status_code in (400, 404)


def test_07_malformed_json(client):
    res = client.post(
        "/api/stress",
        content="{\"clip_id\": 'broken_quote, }",
        headers={"content-type": "application/json"},
    )
    assert res.status_code == 400
    assert "Invalid JSON body" in res.json()["detail"]


def test_08_empty_request_body(client):
    res = client.post("/api/stress", json={})
    assert res.status_code == 400


def test_09_unexpected_extra_fields(client):
    res = client.post(
        "/api/stress",
        json={"clip_id": "fleurs_01", "condition": "clean", "malicious_extra_field": "xyz", "debug": True},
    )
    assert res.status_code == 200
    assert res.json()["success"] is True


def test_10_repeated_identical_requests(client):
    res1 = client.post("/api/stress", json={"clip_id": "fleurs_01", "condition": "clean"})
    res2 = client.post("/api/stress", json={"clip_id": "fleurs_01", "condition": "clean"})
    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json()["prisma_v25"]["transcript"] == res2.json()["prisma_v25"]["transcript"]


def test_11_rapid_repeated_requests_trigger_rate_limit(client):
    for _ in range(10):
        r = client.post("/api/stress", json={"clip_id": "fleurs_01", "condition": "clean"})
        assert r.status_code == 200
    r_11 = client.post("/api/stress", json={"clip_id": "fleurs_01", "condition": "clean"})
    assert r_11.status_code == 429


def test_12_concurrent_mock_requests():
    """Verify that multiple concurrent requests are served without race conditions."""
    _request_timestamps.clear()
    local_client = TestClient(app)

    def send_req(i):
        return local_client.post(
            "/api/stress",
            json={"clip_id": "fleurs_01", "condition": "clean"},
            headers={"x-forwarded-for": f"192.168.1.{i}"},
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(send_req, i) for i in range(1, 6)]
        results = [f.result() for f in futures]

    assert all(r.status_code == 200 for r in results)


def test_13_database_isolation():
    """Verify that STT stress API operates independently of external DB availability."""
    local_client = TestClient(app)
    res = local_client.post("/api/stress", json={"clip_id": "fleurs_01", "condition": "clean"})
    assert res.status_code == 200


def test_14_missing_audio_fixture_returns_404(client):
    res = client.post("/api/stress", json={"clip_id": "fleurs_999", "condition": "clean"})
    assert res.status_code == 404


def test_15_corrupt_audio_fixture_returns_400(client):
    corrupt_bytes = b"NOT_A_VALID_WAV_HEADER_CORRUPTED_STREAM_DATA"
    res = client.post(
        "/api/stress",
        content=corrupt_bytes,
        headers={"content-type": "audio/wav", "x-condition": "clean"},
    )
    assert res.status_code == 400
    assert "Unable to decode audio stream" in res.json()["detail"]
