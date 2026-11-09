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
import json
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

    # Prefer verified short FLEURS speech clips if present, otherwise fall back to synthetic audio
    fleurs_manifest_path = data_dir / "fleurs" / "manifest.json"
    if fleurs_manifest_path.exists():
        with open(fleurs_manifest_path, "r", encoding="utf-8") as f:
            fleurs_data = json.load(f)
        if len(fleurs_data) >= 2 and Path(fleurs_data[0]["file_path"]).exists() and Path(fleurs_data[1]["file_path"]).exists():
            clip1 = Path(fleurs_data[0]["file_path"])
            clip2 = Path(fleurs_data[1]["file_path"])
            label1 = f"{fleurs_data[0]['clip_id']} ({fleurs_data[0]['duration_sec']:.1f}s Hindi)"
            label2 = f"{fleurs_data[1]['clip_id']} ({fleurs_data[1]['duration_sec']:.1f}s Hindi)"
        else:
            clip1 = generate_probe_audio(probe_dir / "probe_clip_1.wav", freq=440.0, duration_sec=2.0)
            clip2 = generate_probe_audio(probe_dir / "probe_clip_2.wav", freq=880.0, duration_sec=2.5)
            label1 = "probe_clip_1 (440Hz 2.0s)"
            label2 = "probe_clip_2 (880Hz 2.5s)"
    else:
        clip1 = generate_probe_audio(probe_dir / "probe_clip_1.wav", freq=440.0, duration_sec=2.0)
        clip2 = generate_probe_audio(probe_dir / "probe_clip_2.wav", freq=880.0, duration_sec=2.5)
        label1 = "probe_clip_1 (440Hz 2.0s)"
        label2 = "probe_clip_2 (880Hz 2.5s)"

    calls = [
        {"name": f"Probe 1: {label1}", "clip": clip1, "model": None, "label": "Prisma v2.5", "format": "verbatim"},
        {"name": f"Probe 2: {label1}", "clip": clip1, "model": "prisma-v3.0", "label": "Prisma v3.0", "format": "verbatim"},
        {"name": f"Probe 3: {label2}", "clip": clip2, "model": None, "label": "Prisma v2.5", "format": "verbatim"},
        {"name": f"Probe 4: {label2}", "clip": clip2, "model": "prisma-v3.0", "label": "Prisma v3.0", "format": "verbatim"},
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

    if len(results) == 4 and all(r.get("success") for r in results):
        print("\nComparative Analysis (v2.5 vs v3.0):")
        c1_v25 = results[0].get("transcript", "")
        c1_v30 = results[1].get("transcript", "")
        print(f"  Clip 1 - Prisma v2.5 Latency: {results[0].get('latency_sec', 0):.3f}s | Transcript: '{c1_v25}'")
        print(f"  Clip 1 - Prisma v3.0 Latency: {results[1].get('latency_sec', 0):.3f}s | Transcript: '{c1_v30}'")
        print(f"  Clip 1 - Outputs differ:     {c1_v25 != c1_v30}")
        c2_v25 = results[2].get("transcript", "")
        c2_v30 = results[3].get("transcript", "")
        print(f"  Clip 2 - Prisma v2.5 Latency: {results[2].get('latency_sec', 0):.3f}s | Transcript: '{c2_v25}'")
        print(f"  Clip 2 - Prisma v3.0 Latency: {results[3].get('latency_sec', 0):.3f}s | Transcript: '{c2_v30}'")
        print(f"  Clip 2 - Outputs differ:     {c2_v25 != c2_v30}")
        print(f"  Prisma v2.5 accepted explicit format 'verbatim': {bool(results[0].get('success') and results[2].get('success'))}")
        print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CallLens Usage Probe")
    parser.add_argument("--live", action="store_true", help="Execute live network calls against Gnani API")
    args = parser.parse_args()

    run_probe(live=args.live)
