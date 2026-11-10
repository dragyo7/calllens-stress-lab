# CallLens Data Provenance, Schemas, and Storage Architecture

This document outlines the data sources, synthetic audio generation protocols, storage schemas, and retention policies for the CallLens Stress Lab.

---

## 1. Data Sources & Provenance

### A. FLEURS Hindi India (`hi_in`)
- **Source:** Hugging Face repository `google/fleurs` (`data/hi_in/test.tsv` and `data/hi_in/audio/test.tar.gz`).
- **Attribution & License:** Creative Commons Attribution 4.0 International (CC BY 4.0) by Google LLC.
- **Selection Criteria:** 30 clips selected sequentially where duration &le; 28.0 seconds (`samples <= 448000` at 16 kHz).
- **Ground Truth Reference:** Extracted from the verified raw transcription column (Column 2 of `test.tsv`).

### B. Experiment D (Noise & Silence Hallucination)
- **Source:** Deterministic synthetic audio generated via NumPy (`scripts/gen_noise.py`).
- **Volume:** 20 clips total (10 white Gaussian noise, 10 digital silence).
- **Format:** 16,000 Hz, mono, 16-bit PCM, exactly 5.0 seconds duration.
- **Seeding:** Seeds 1001 to 1010 for deterministic reproducibility.
- **Ground Truth:** Empty string `""` (zero expected speech).

### C. Experiment F (BFSI Banking Entities)
- **Source:** Synthetic banking domain templates voiced using Gnani Timbre v2.5 (`scripts/gen_utterances.py`).
- **Voice / Language:** Voice `Pranav`, language `hi-IN`.
- **Entities Tested:** Customer name, amount in Indian Rupees (various numerical and linguistic formats), due date (day of month 1–31).
- **Ground Truth:** Persisted in `../calllens-data/bfsi/ground_truth.json`.
- **Note:** Stored and reported explicitly as synthetic TTS audio, not real customer call center recordings.

---

## 2. Directory Layout & Storage Segregation

All dataset and processed audio artifacts live outside the Git repository in `../calllens-data` (overridable via `DATA_DIR` environment variable):

```text
../calllens-data/
  ├── fleurs/
  │   ├── audio/*.wav
  │   └── manifest.json
  ├── noise_silence/
  │   ├── *.wav
  │   └── manifest.json
  ├── bfsi/
  │   ├── *.wav
  │   ├── manifest.json
  │   └── ground_truth.json
  ├── processed_audio/
  │   └── *_clean.wav, *_tel.wav, *_tel_snr10.wav, *_tel_snr0.wav
  ├── cache/
  │   └── [sha256].json
  └── benchmark.db
```

---

## 3. Database Schema (`benchmark_results`)

Evaluations are recorded in SQLite using SQLAlchemy ORM (`calllens/benchmark.py`):

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INTEGER | Primary Key (autoincrement) |
| `experiment` | VARCHAR(10) | "A" (FLEURS), "D" (Noise), or "F" (BFSI) |
| `clip_id` | VARCHAR(64) | Stable identifier of source clip |
| `condition` | VARCHAR(32) | "clean", "tel", "tel_snr10", "tel_snr0" |
| `model` | VARCHAR(32) | "prisma-v2.5" or "prisma-v3.0" |
| `format` | VARCHAR(32) | "verbatim" |
| `reference_text` | TEXT | Raw reference transcription |
| `hypothesis_text` | TEXT | Raw ASR output hypothesis |
| `normalized_ref` | TEXT | NFC, punctuation-stripped reference |
| `normalized_hyp` | TEXT | NFC, punctuation-stripped hypothesis |
| `wer` | FLOAT | Word Error Rate via `jiwer` |
| `cer` | FLOAT | Character Error Rate via `jiwer` |
| `latency_sec` | FLOAT | Wall-clock request latency |
| `duration_sec` | FLOAT | Audio duration in seconds |
| `rtf` | FLOAT | Real-Time Factor (`latency / duration`) |
| `gt_amount` | INTEGER | Ground truth amount in Rupees |
| `extracted_amount` | INTEGER | Extracted amount in Rupees |
| `amount_correct` | BOOLEAN | Exact match boolean |
| `gt_due_day` | INTEGER | Ground truth due day (1-31) |
| `extracted_due_day`| INTEGER | Extracted due day (1-31) |
| `due_day_correct` | BOOLEAN | Exact match boolean |
| `is_hallucinated` | BOOLEAN | True if non-empty text emitted on noise/silence |
| `from_cache` | BOOLEAN | Whether result was retrieved from cache |
| `mock` | BOOLEAN | Whether result was generated in mock mode |
| `timestamp` | DATETIME | Timestamp of evaluation |

---

## 4. Why SQLite?

1. **Zero External Dependency:** Requires no daemon, Docker container, or cloud service configuration.
2. **Atomic Consistency:** ACID compliant file-based storage guaranteeing reproducible benchmarks.
3. **Transportability:** The database file can be copied or inspected across Windows, Linux, and macOS platforms.
