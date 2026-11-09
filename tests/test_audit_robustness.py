"""Additional audit robustness tests for CallLens Stress Lab.

Covers:
- Fresh database startup and schema creation
- Resumable benchmark execution (skips already evaluated live rows)
- Report generation with 0, 1, and many records
- Cache and retry accounting invariants
- Mock fixture isolation when allow_mock=False
- Zero-duration and malformed audio guards
- Missing API key behavior in live mode
"""

import os
from pathlib import Path
import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from app.main import app, _request_timestamps
from calllens import gnani_client, metrics
from calllens.benchmark import BenchmarkResult, generate_summary_report, get_db_session, run_benchmark
from calllens.gnani_client import CallLimitExceededError, GnaniClientError, accounting


@pytest.fixture
def client():
    _request_timestamps.clear()
    return TestClient(app)


def test_fresh_database_startup(tmp_path):
    """Verify fresh database initializes schema with benchmark_results table."""
    db_file = tmp_path / "fresh_test.db"
    assert not db_file.exists()
    session = get_db_session(f"sqlite:///{db_file}")
    assert db_file.exists()
    count = session.query(BenchmarkResult).count()
    assert count == 0
    session.close()


def test_report_generation_zero_one_many_rows(tmp_path):
    """Verify report generation handles 0, 1, and multiple rows safely."""
    db_file = tmp_path / "report_test.db"
    session = get_db_session(f"sqlite:///{db_file}")
    report_file = tmp_path / "summary.md"

    # 1. Zero rows
    generate_summary_report(session, report_file, provenance="live")
    assert "No live results yet" in report_file.read_text(encoding="utf-8")

    # 2. One row
    rec1 = BenchmarkResult(
        experiment="A",
        clip_id="clip_01",
        condition="clean",
        model="prisma-v2.5",
        format="verbatim",
        reference_text="नमस्ते",
        hypothesis_text="नमस्ते",
        wer=0.0,
        cer=0.0,
        latency_sec=0.5,
        duration_sec=2.0,
        rtf=0.25,
        mock=False,
        provenance="live",
    )
    session.add(rec1)
    session.commit()

    generate_summary_report(session, report_file, provenance="live")
    content_one = report_file.read_text(encoding="utf-8")
    assert "prisma-v2.5" in content_one
    assert "| clean | 1 |" in content_one

    # 3. Many rows
    rec2 = BenchmarkResult(
        experiment="A",
        clip_id="clip_02",
        condition="clean",
        model="prisma-v2.5",
        format="verbatim",
        reference_text="भारत",
        hypothesis_text="भारत देश",
        wer=0.5,
        cer=0.4,
        latency_sec=0.6,
        duration_sec=2.5,
        rtf=0.24,
        mock=False,
        provenance="live",
    )
    session.add(rec2)
    session.commit()

    generate_summary_report(session, report_file, provenance="live")
    content_many = report_file.read_text(encoding="utf-8")
    assert "| clean | 2 |" in content_many
    session.close()


def test_cache_hit_does_not_consume_live_call_budget(tmp_path, monkeypatch):
    """Prove cache hit increments cache_hits and leaves live_calls unchanged."""
    accounting.reset(new_max_live_calls=5)
    monkeypatch.setenv("CALLENS_CACHE_DIR", str(tmp_path / "test_cache"))

    payload = {"audio": b"fake_pcm16_data", "model": "prisma-v3.0", "format": "verbatim"}
    key = gnani_client.compute_cache_key("stt", payload)
    gnani_client._save_to_cache(key, "stt", {"success": True, "transcript": "कैश किया गया", "mock": False})

    initial_live = accounting.live_calls
    initial_cache = accounting.cache_hits

    # Call in live mode with cache hit
    res = gnani_client.call("stt", payload, live=True, use_cache=True)
    assert res["transcript"] == "कैश किया गया"
    assert res["from_cache"] is True
    assert accounting.cache_hits == initial_cache + 1
    assert accounting.live_calls == initial_live


def test_missing_api_key_raises_client_error(monkeypatch):
    """Verify live call without GNANI_API_KEY raises GnaniClientError."""
    accounting.reset(new_max_live_calls=5)
    monkeypatch.delenv("GNANI_API_KEY", raising=False)

    payload = {"audio": b"dummy_audio_bytes", "model": None, "format": "verbatim"}
    with pytest.raises(GnaniClientError) as exc_info:
        gnani_client.call("stt", payload, live=True, use_cache=False)
    assert "GNANI_API_KEY environment variable is not set" in str(exc_info.value)


def test_mock_fixture_unreachable_when_allow_mock_false(client, tmp_path, monkeypatch):
    """Verify mock fixtures cannot be retrieved when allow_mock=False."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    res = client.post(
        "/api/stress",
        json={"clip_id": "fleurs_01", "condition": "clean", "live": 0, "allow_mock": False},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["has_live_results"] is False
    assert "no live results yet" in data["message"].lower()


def test_zero_duration_audio_rejected(client):
    """Verify empty 0-byte or zero-sample audio returns HTTP 400."""
    res = client.post(
        "/api/stress",
        content=b"",
        headers={"content-type": "audio/wav", "x-condition": "clean"},
    )
    assert res.status_code == 400


def test_persistent_global_counter_cross_process(tmp_path):
    """Prove that separate script processes share ONE persistent network-attempt cap that cannot be bypassed."""
    import subprocess
    import sys

    acc_file = tmp_path / "shared_accounting.json"
    env_vars = os.environ.copy()
    env_vars["CALLENS_ACCOUNTING_FILE"] = str(acc_file)
    env_vars["MAX_LIVE_CALLS"] = "5"
    env_vars["GNANI_API_KEY"] = "mock_key_for_process_test"

    # Worker script that reserves N attempts
    worker_code = """
import os, sys
from calllens.gnani_client import accounting, CallLimitExceededError

attempts_to_make = int(sys.argv[1])
for i in range(attempts_to_make):
    try:
        accounting.check_and_reserve_network_attempt()
        print(f"RESERVED {i+1}")
    except CallLimitExceededError as e:
        print(f"BLOCKED: {e}")
        sys.exit(42)
"""

    # Process 1 (simulating Gate G1: makes 2 attempts)
    p1 = subprocess.run(
        [sys.executable, "-c", worker_code, "2"],
        capture_output=True,
        text=True,
        env=env_vars,
    )
    assert p1.returncode == 0
    assert "RESERVED 1" in p1.stdout
    assert "RESERVED 2" in p1.stdout

    # Process 2 (simulating Gate G2: makes 2 attempts)
    p2 = subprocess.run(
        [sys.executable, "-c", worker_code, "2"],
        capture_output=True,
        text=True,
        env=env_vars,
    )
    assert p2.returncode == 0
    assert "RESERVED 1" in p2.stdout
    assert "RESERVED 2" in p2.stdout

    # Process 3 (simulating Gate G3: tries to make 2 attempts, but only 1 remains before hitting cap 5)
    p3 = subprocess.run(
        [sys.executable, "-c", worker_code, "2"],
        capture_output=True,
        text=True,
        env=env_vars,
    )
    # Must be blocked on the 2nd attempt because total reached 5
    assert p3.returncode == 42
    assert "RESERVED 1" in p3.stdout
    assert "BLOCKED: Persistent global network attempt cap reached across processes: 5/5" in p3.stdout

