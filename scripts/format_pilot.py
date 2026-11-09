"""Gate G2 format-mode pilot comparing supported formats on Prisma v3.0.

Evaluates 10 FLEURS Hindi clips across the 2 SDK-supported formats:
- 'verbatim': raw spoken transcription
- 'transcribe': formatted transcription with inverse text normalization (ITN)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from calllens import gnani_client, metrics
from calllens.gnani_client import accounting


def run_format_pilot(live: bool = False, dry_run: bool = False) -> dict:
    data_dir = Path(os.getenv("DATA_DIR", "../calllens-data"))
    fleurs_manifest_path = data_dir / "fleurs" / "manifest.json"

    if not fleurs_manifest_path.exists():
        raise FileNotFoundError(f"FLEURS manifest not found at {fleurs_manifest_path}")

    with open(fleurs_manifest_path, "r", encoding="utf-8") as f:
        clips = json.load(f)[:10]

    formats = ["verbatim", "transcribe"]
    total_calls = len(clips) * len(formats)

    print("=" * 60)
    print("GATE G2: PRISMA V3.0 FORMAT PILOT")
    print(f"Mode: {'DRY RUN' if dry_run else ('LIVE API' if live else 'MOCK / OFFLINE')}")
    print(f"Clips: {len(clips)} FLEURS clips")
    print(f"Formats Tested: {formats}")
    print(f"Total STT Logical Calls: {total_calls}")
    print("=" * 60)

    if dry_run:
        print("\nDry run completed. Planned calls:")
        for idx, c in enumerate(clips, 1):
            print(f"[{idx}/10] Clip {c['clip_id']} ({c['duration_sec']:.1f}s) -> formats: verbatim, transcribe")
        return {"planned_calls": total_calls, "dry_run": True}

    results = []
    for idx, c in enumerate(clips, 1):
        audio_path = Path(c["file_path"])
        ref_text = c.get("raw_transcription", "")
        clip_id = c["clip_id"]

        for fmt in formats:
            payload = {
                "audio": audio_path,
                "model": "prisma-v3.0",
                "language_code": "hi-IN",
                "format": fmt,
                "mock_transcript": ref_text,
            }
            start = time.perf_counter()
            res = gnani_client.call("stt", payload, live=live)
            elapsed = time.perf_counter() - start

            hyp = res.get("transcript", "")
            lat = res.get("end_to_end_latency", elapsed)
            wer = metrics.compute_wer(ref_text, hyp)

            results.append({
                "clip_id": clip_id,
                "format": fmt,
                "ref_text": ref_text,
                "hyp_text": hyp,
                "wer": wer,
                "latency_sec": lat,
                "from_cache": res.get("from_cache", False),
                "mock": res.get("mock", False),
            })
            print(f"[{len(results)}/{total_calls}] Clip {clip_id} | Format: {fmt:<10} | WER: {wer:.4f} | Latency: {lat:.3f}s")

    print("\n" + "=" * 60)
    print("FORMAT PILOT ANALYSIS")
    print("=" * 60)
    for fmt in formats:
        subset = [r for r in results if r["format"] == fmt]
        mean_wer = sum(r["wer"] for r in subset) / len(subset)
        mean_lat = sum(r["latency_sec"] for r in subset) / len(subset)
        print(f"Format: {fmt:<12} | Mean WER: {mean_wer:.4f} | Mean Latency: {mean_lat:.3f}s | N={len(subset)}")

    return {"results": results, "total_calls": len(results)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Format Mode Pilot")
    parser.add_argument("--live", action="store_true", help="Execute live network calls")
    parser.add_argument("--dry-run", action="store_true", help="Print call plan without executing")
    args = parser.parse_args()

    run_format_pilot(live=args.live, dry_run=args.dry_run)

