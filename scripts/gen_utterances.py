"""Generate 10 synthetic Hinglish BFSI utterances for Experiment F.

Each utterance contains:
- Customer name
- Target amount in Rupees (with various representations: lakh, crore, comma digits, rupees)
- Due date / day of month

Voices are generated via gnani_client.call("tts", ...) using timbre-v2.5 (e.g. voice "Pranav", language="hi-IN").
By default runs in MOCK mode or DRY-RUN.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from pathlib import Path

import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from calllens import gnani_client


BFSI_TEMPLATES = [
    {
        "id": "bfsi_01",
        "customer_name": "राहुल शर्मा",
        "text": "नमस्ते राहुल शर्मा जी, आपका क्रेडिट कार्ड बिल ₹ 50,000 है जो 5 तारीख तक देय है।",
        "amount": 50000,
        "due_day": 5,
    },
    {
        "id": "bfsi_02",
        "customer_name": "प्रिया वर्मा",
        "text": "हेलो प्रिया वर्मा, आपकी होम लोन ईएमआई 3,50,000 rupees 15 तारीख को कटनी है।",
        "amount": 350000,
        "due_day": 15,
    },
    {
        "id": "bfsi_03",
        "customer_name": "अमित सिंह",
        "text": "अमित सिंह जी, आपके व्यवसाय के लिए ₹2.25 crore का ऋण 10 तारीख को स्वीकृत होगा।",
        "amount": 22500000,
        "due_day": 10,
    },
    {
        "id": "bfsi_04",
        "customer_name": "सुनील कुमार",
        "text": "नमस्ते सुनील कुमार जी, आपकी ऑटो लोन किस्त 1.5 लाख रुपये 25 तारीख तक जमा कराएं।",
        "amount": 150000,
        "due_day": 25,
    },
    {
        "id": "bfsi_05",
        "customer_name": "कविता पटेल",
        "text": "प्रिय कविता पटेल, आपका न्यूनतम भुगतान 10 हजार रुपये 1 तारीख को देय है।",
        "amount": 10000,
        "due_day": 1,
    },
    {
        "id": "bfsi_06",
        "customer_name": "राजेश गुप्ता",
        "text": "राजेश गुप्ता जी, आपका व्यक्तिगत ऋण बकाया 2.25 lakh है जो 12 तारीख तक भरें।",
        "amount": 225000,
        "due_day": 12,
    },
    {
        "id": "bfsi_07",
        "customer_name": "अनीता देसाई",
        "text": "अनीता देसाई, आपके खाते से 75,500 rupees की ईएमआई 20 तारीख को काटी जाएगी।",
        "amount": 75500,
        "due_day": 20,
    },
    {
        "id": "bfsi_08",
        "customer_name": "विकास मेहता",
        "text": "विकास मेहता जी, आपका बिल राशि ₹ 1,20,000 दिनांक 28 तक देय है।",
        "amount": 120000,
        "due_day": 28,
    },
    {
        "id": "bfsi_09",
        "customer_name": "दीपक जोशी",
        "text": "दीपक जोशी, आपकी प्रीमियम राशि 25,000 रुपये 7 तारीख से पहले जमा करें।",
        "amount": 25000,
        "due_day": 7,
    },
    {
        "id": "bfsi_10",
        "customer_name": "नेहा कपूर",
        "text": "नमस्ते नेहा कपूर जी, आपके म्यूच्यूअल फंड एसआईपी ₹ 15,000 18 तारीख को देय है।",
        "amount": 15000,
        "due_day": 18,
    },
]


def generate_bfsi_utterances(output_dir: Path | None = None, live: bool = False, dry_run: bool = False) -> Path:
    if output_dir is None:
        data_dir = Path(os.getenv("DATA_DIR", "../calllens-data"))
        output_dir = data_dir / "bfsi"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("EXPERIMENT F: BFSI UTTERANCE GENERATION")
    print(f"Mode: {'DRY RUN' if dry_run else ('LIVE TTS' if live else 'MOCK TTS')}")
    print(f"Target Directory: {output_dir}")
    print(f"Planned TTS Calls: {len(BFSI_TEMPLATES)}")
    print(f"TTS Model: timbre-v2.5 | Voice: Pranav | Language: hi-IN")
    print("=" * 60)

    if dry_run:
        print("\nPlanned Utterance Syntheses (DRY RUN):")
        for item in BFSI_TEMPLATES:
            print(f"- [{item['id']}] {item['customer_name']}: Amount={item['amount']}, DueDay={item['due_day']}")
            print(f"  Text: '{item['text']}'")
        return output_dir / "manifest.json"

    manifest: list[dict] = []
    ground_truth: list[dict] = []

    for idx, item in enumerate(BFSI_TEMPLATES, 1):
        print(f"[{idx}/{len(BFSI_TEMPLATES)}] Synthesizing {item['id']} ({item['customer_name']})...")
        payload = {
            "text": item["text"],
            "model": "timbre-v2.5",
            "voice": "Pranav",
            "language": "hi-IN",
            "speed": 1.0,
        }
        audio_bytes = gnani_client.call("tts", payload, live=live)

        out_path = output_dir / f"{item['id']}.wav"
        # Verify and normalize to 16kHz mono PCM16
        with io.BytesIO(audio_bytes) as bio:
            audio_data, sr = sf.read(bio, dtype="float32")
            if sr != 16000 or audio_data.ndim > 1:
                import scipy.signal as signal
                if audio_data.ndim > 1:
                    audio_data = audio_data.mean(axis=-1)
                if sr != 16000:
                    num_samples = int(round(len(audio_data) * 16000 / sr))
                    audio_data = signal.resample(audio_data, num_samples)
                sr = 16000
            sf.write(str(out_path), audio_data, 16000, subtype="PCM_16")

        info = sf.info(str(out_path))

        entry = {
            "clip_id": item["id"],
            "customer_name": item["customer_name"],
            "text": item["text"],
            "amount": item["amount"],
            "due_day": item["due_day"],
            "file_path": str(out_path),
            "duration_sec": round(info.duration, 2),
            "sample_rate": info.samplerate,
            "synthetic_tts": True,
            "tts_model": "timbre-v2.5",
            "tts_voice": "Pranav",
        }
        manifest.append(entry)
        ground_truth.append({
            "clip_id": item["id"],
            "amount": item["amount"],
            "due_day": item["due_day"],
            "expected_transcript": item["text"],
        })

    manifest_path = output_dir / "manifest.json"
    gt_path = output_dir / "ground_truth.json"

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(manifest)} utterances to {output_dir}")
    print(f"Manifest: {manifest_path}")
    print(f"Ground Truth: {gt_path}")
    return manifest_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate BFSI Utterances")
    parser.add_argument("--live", action="store_true", help="Execute live TTS calls via Gnani API")
    parser.add_argument("--dry-run", action="store_true", help="Display intended calls without execution")
    parser.add_argument("--out-dir", type=str, default=None, help="Output directory")
    args = parser.parse_args()

    generate_bfsi_utterances(
        output_dir=Path(args.out_dir) if args.out_dir else None,
        live=args.live,
        dry_run=args.dry_run,
    )
