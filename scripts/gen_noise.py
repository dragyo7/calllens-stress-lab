"""Generate 20 five-second 16kHz mono PCM16 clips for Experiment D.

- 10 seeded white-noise clips
- 10 silence clips

Saves output outside Git repository (default: ../calllens-data/noise_silence).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def generate_noise_and_silence_dataset(output_dir: Path | None = None) -> Path:
    if output_dir is None:
        data_dir = Path(os.getenv("DATA_DIR", "../calllens-data"))
        output_dir = data_dir / "noise_silence"
    output_dir.mkdir(parents=True, exist_ok=True)

    sr = 16000
    duration_sec = 5.0
    num_samples = int(sr * duration_sec)

    manifest: list[dict] = []

    print(f"Generating 10 white-noise and 10 silence clips in: {output_dir}")

    # 1. Generate 10 seeded white noise clips
    for i in range(1, 11):
        clip_id = f"noise_{i:02d}"
        seed = 1000 + i
        rng = np.random.RandomState(seed)
        # White noise at ~ -20 dBFS RMS
        noise = (rng.standard_normal(num_samples) * 0.1).astype(np.float32)
        out_path = output_dir / f"{clip_id}.wav"
        sf.write(str(out_path), noise, sr, subtype="PCM_16")

        manifest.append({
            "clip_id": clip_id,
            "type": "noise",
            "file_path": str(out_path),
            "duration_sec": duration_sec,
            "sample_rate": sr,
            "seed": seed,
            "expected_transcript": "",
        })

    # 2. Generate 10 silence clips
    for i in range(1, 11):
        clip_id = f"silence_{i:02d}"
        silence = np.zeros(num_samples, dtype=np.float32)
        out_path = output_dir / f"{clip_id}.wav"
        sf.write(str(out_path), silence, sr, subtype="PCM_16")

        manifest.append({
            "clip_id": clip_id,
            "type": "silence",
            "file_path": str(out_path),
            "duration_sec": duration_sec,
            "sample_rate": sr,
            "expected_transcript": "",
        })

    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Generated {len(manifest)} clips. Manifest saved to: {manifest_path}")
    return manifest_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate noise and silence clips for Experiment D")
    parser.add_argument("--out-dir", type=str, default=None, help="Directory to save generated clips")
    args = parser.parse_args()

    out_p = Path(args.out_dir) if args.out_dir else None
    generate_noise_and_silence_dataset(out_p)
