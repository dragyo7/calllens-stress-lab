"""Usage probe script to verify Gnani STT models (v2.5 and v3.0) and latency.

By default runs in MOCK mode.
When run with --live, performs exactly four logical STT calls:
- Clip 1 with Prisma v2.5 (model=None)
- Clip 1 with Prisma v3.0 (model="prisma-v3.0")
- Clip 2 with Prisma v2.5 (model=None)
- Clip 2 with Prisma v3.0 (model="prisma-v3.0")
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from dotenv import load_dotenv

# Ensure calllens is in Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from calllens import gnani_client
from calllens.gnani_client import accounting

load_dotenv()


def generate_probe_audio(filename: Path, freq: float, duration_sec: float = 2.0) -> Path:
    """Generates a valid 16kHz mono PCM16 audio file for probing."""
    filename.parent.mkdir(parents=True, exist_ok=True)
    sr = 16000
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False, dtype=np.float32)
    # Sine wave modulated slightly
    audio = 0.2 * np.sin(2 * np.pi * freq * t)
    # Convert to PCM16
    sf.write(str(filename), audio, sr, subtype="PCM_16")
    return filename


def run_probe(live: bool = False) -> None:
    data_dir = Path(os.getenv("DATA_DIR", "../calllens-data"))
    probe_dir = data_dir / "probe"
    probe_dir.mkdir(parents=True, exist_ok=True)

    clip1 = generate_probe_audio(probe_dir / "probe_clip_1.wav", freq=440.0, duration_sec=2.0)
    clip2 = generate_probe_audio(probe_dir / "probe_clip_2.wav", freq=880.0, duration_sec=2.5)

    calls = [
        {"name": "Probe 1: Clip 1 (440Hz 2.0s)", "clip": clip1, "model": None, "label": "Prisma v2.5", "format": "verbatim"},
        {"name": "Probe 2: Clip 1 (440Hz 2.0s)", "clip": clip1, "model": "prisma-v3.0", "label": "Prisma v3.0", "format": "verbatim"},
        {"name": "Probe 3: Clip 2 (880Hz 2.5s)", "clip": clip2, "model": None, "label": "Prisma v2.5", "format": "verbatim"},
        {"name": "Probe 4: Clip 2 (880Hz 2.5s)", "clip": clip2, "model": "prisma-v3.0", "label": "Prisma v3.0", "format": "verbatim"},
    ]

    print("=" * 60)
    print("CALLENS USAGE PROBE (Gate G1)")
    print(f"Mode: {'LIVE NETWORK' if live else 'MOCK / DRY-RUN'}")
    print(f"Planned logical calls: {len(calls)}")
    print(f"Configured MAX_LIVE_CALLS: {accounting.max_live_calls}")
    print("=" * 60)

    results = []
    for idx, c in enumerate(calls, 1):
        print(f"\n[{idx}/4] Executing: {c['name']} (model: {c['label']})...")
        payload = {
            "audio": c["clip"],
            "model": c["model"],
            "language_code": "hi-IN",
            "format": c["format"],
        }
        start = time.perf_counter()
        try:
            res = gnani_client.call("stt", payload, live=live)
            wall_time = time.perf_counter() - start
            results.append({
                "probe": c["name"],
                "model": c["label"],
                "success": res.get("success"),
                "transcript": res.get("transcript"),
                "latency_sec": res.get("end_to_end_latency", wall_time),
                "from_cache": res.get("from_cache", False),
                "mock": res.get("mock", False),
            })
            print(f"    Success: {res.get('success')}")
            print(f"    Transcript: '{res.get('transcript')}'")
            print(f"    Latency: {results[-1]['latency_sec']:.3f}s")
            print(f"    Cache Hit: {res.get('from_cache', False)}")
        except Exception as e:
            print(f"    FAILED: {e}")
            results.append({
                "probe": c["name"],
                "model": c["label"],
                "success": False,
                "error": str(e),
            })

    print("\n" + "=" * 60)
    print("PROBE SUMMARY REPORT")
    print("=" * 60)
    for r in results:
        status = "OK" if r.get("success") else "FAIL"
        print(f"- {r['model']:<15} | Status: {status:<5} | Latency: {r.get('latency_sec', 0):.3f}s | Cache: {r.get('from_cache')} | Mock: {r.get('mock')}")
        if r.get("transcript"):
            print(f"  Transcript: '{r['transcript']}'")
        if r.get("error"):
            print(f"  Error: {r['error']}")

    print("\nAccountant Statistics:")
    print(f"  Live Calls Made:     {accounting.live_calls}")
    print(f"  Network Attempts:   {accounting.network_attempts}")
    print(f"  Retries:            {accounting.retries}")
    print(f"  Cache Hits:         {accounting.cache_hits}")
    print(f"  Mock Calls:         {accounting.mock_calls}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CallLens Usage Probe")
    parser.add_argument("--live", action="store_true", help="Execute live network calls against Gnani API")
    args = parser.parse_args()

    run_probe(live=args.live)
