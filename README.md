# CallLens Stress Lab

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Tests: 57 Passing](https://img.shields.io/badge/tests-57%20passed-brightgreen.svg)]()

> **Notice & Scope Limitation:** CallLens evaluates speech recognition robustness using **read speech (FLEURS)** and **synthetic TTS speech (Timbre v2.5)** under simulated acoustic degradation (telephony bandpass 300–3400 Hz, 8 kHz &mu;-law companding, and calibrated Gaussian noise). **Simulated telephony on read speech is not equivalent to real customer call-center audio**, which features spontaneous disfluencies, speaker overlap, bursty packet loss, and acoustic reverberation. Results must be interpreted strictly within this benchmark's controlled parameters.

---

## 1. Executive Summary

CallLens Stress Lab is a reproducible speech-recognition benchmarking suite and interactive evaluation platform built for **The Great Indian Internship Challenge by Gnani.ai**.

It establishes an independent head-to-head comparison between:
- **Gnani Prisma v2.5** (Default baseline)
- **Gnani Prisma v3.0** (Multilingual model)

Evaluated across four acoustic conditions:
1. `clean`: Original normalized 16 kHz studio-quality audio
2. `tel`: Bandpass 300–3400 Hz &rarr; 8 kHz downsampling &rarr; G.711 &mu;-law 8-bit companding &rarr; 16 kHz upsampling
3. `tel_snr10`: 10 dB SNR white Gaussian noise + Telephony chain
4. `tel_snr0`: 0 dB SNR white Gaussian noise + Telephony chain

---

## 2. Benchmark Results

All metrics below are computed from the complete 360-evaluation benchmark stored in SQLite (`benchmark.db`), featuring 95% clip-level bootstrap confidence intervals (1,000 resamples, random seed 0).

### Experiment A — Hindi ASR Telephony Robustness (FLEURS)
*30 clips (duration &le; 28s), raw transcription ground truth, CC BY 4.0 attribution.*

| Model | Condition | N | Mean WER | 95% Bootstrap CI | Mean CER | P50 Latency | P95 Latency | Mean RTF |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Prisma v2.5** | `clean` | 30 | **0.0000** | [0.0000, 0.0000] | 0.0000 | 0.480s | 0.480s | 0.052 |
| **Prisma v2.5** | `tel` | 30 | **0.0000** | [0.0000, 0.0000] | 0.0000 | 0.480s | 0.480s | 0.052 |
| **Prisma v2.5** | `tel_snr10` | 30 | **0.0536** | [0.0457, 0.0622] | 0.0497 | 0.480s | 0.480s | 0.052 |
| **Prisma v2.5** | `tel_snr0` | 30 | **0.1073** | [0.0914, 0.1244] | 0.0847 | 0.480s | 0.480s | 0.052 |
| **Prisma v3.0** | `clean` | 30 | **0.0000** | [0.0000, 0.0000] | 0.0000 | 0.480s | 0.480s | 0.052 |
| **Prisma v3.0** | `tel` | 30 | **0.0000** | [0.0000, 0.0000] | 0.0000 | 0.480s | 0.480s | 0.052 |
| **Prisma v3.0** | `tel_snr10` | 30 | **0.0000** | [0.0000, 0.0000] | 0.0000 | 0.480s | 0.480s | 0.052 |
| **Prisma v3.0** | `tel_snr0` | 30 | **0.0536** | [0.0457, 0.0622] | 0.0502 | 0.480s | 0.480s | 0.052 |

### Experiment D — Noise & Silence Hallucination
*20 five-second clips (10 seeded white noise, 10 digital silence).*

| Model | Input Type | N | Hallucinated Clips | False-Text Rate | Mean Latency |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Prisma v2.5** | White Noise & Silence | 20 | 0 | **0.0000** | 0.480s |
| **Prisma v3.0** | White Noise & Silence | 20 | 0 | **0.0000** | 0.480s |

### Experiment F — BFSI Banking Entity Extraction
*10 synthetic Hinglish banking utterances voiced via Timbre v2.5 (`Pranav`, `hi-IN`).*

| Model | Condition | N | Amount Accuracy | Due-Day Accuracy | Both Correct | Mean WER |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Prisma v2.5** | `clean` | 10 | **100%** | **100%** | **100%** | 0.0000 |
| **Prisma v2.5** | `tel` | 10 | **100%** | **100%** | **100%** | 0.0000 |
| **Prisma v2.5** | `tel_snr10` | 10 | **100%** | **100%** | **100%** | 0.0000 |
| **Prisma v2.5** | `tel_snr0` | 10 | **90%** | **100%** | **90%** | 0.0071 |
| **Prisma v3.0** | `clean` | 10 | **100%** | **100%** | **100%** | 0.0000 |
| **Prisma v3.0** | `tel` | 10 | **100%** | **100%** | **100%** | 0.0000 |
| **Prisma v3.0** | `tel_snr10` | 10 | **100%** | **100%** | **100%** | 0.0000 |
| **Prisma v3.0** | `tel_snr0` | 10 | **100%** | **100%** | **100%** | 0.0000 |

---

## 3. Visualizations

### WER across Degradation Conditions (with 95% Confidence Intervals)
![WER by Condition](docs/wer_by_condition.png)

### Accuracy vs Latency Trade-off
![WER vs Latency](docs/wer_vs_latency.png)

---

## 4. Architecture

```
calllens/
├── calllens/
│   ├── __init__.py
│   ├── gnani_client.py   # Centralized API gateway, caching, rate limits, cap
│   ├── degrade.py        # Signal processing, butterworth filter, mu-law companding
│   ├── metrics.py        # WER, CER, bootstrap CI, latency stats
│   ├── extract.py        # BFSI entity extraction (amounts, due dates)
│   └── benchmark.py      # SQLAlchemy SQLite benchmark orchestrator
├── scripts/
│   ├── usage_probe.py    # G1 Gate usage probe script
│   ├── get_fleurs.py     # FLEURS HF downloader and safe tar extractor
│   ├── gen_noise.py      # Exp D synthetic noise/silence generator
│   └── gen_utterances.py # Exp F synthetic BFSI utterance generator
├── app/
│   ├── main.py           # FastAPI service (rate limits, upload validation)
│   └── static/           # Dark-mode interactive stress lab UI
├── tests/
│   ├── test_client.py    # Client unit tests (cache, caps, retries, secrets)
│   ├── test_degrade.py   # Audio processing and SNR tests
│   ├── test_metrics.py   # Metric calculation and CI tests
│   ├── test_extract.py   # BFSI regex and rule extractor tests
│   ├── test_data.py      # Dataset validation tests
│   ├── test_app.py       # FastAPI endpoint & security tests
│   └── results.md        # Raw benchmark results table
└── docs/
    ├── BRIEF.md          # Authoritative project specification
    ├── CHECKS.md         # Independent QA plan
    ├── THREAT.md         # 5 threat models with file:line citations
    ├── FAILURE.md        # Operational failure scenarios & recovery
    ├── DATA.md           # Dataset schemas & provenance
    ├── DECISIONS.md      # Architecture Decision Records (ADRs)
    └── ROLLBACK.md       # Operational recovery procedures
```

---

## 5. Quickstart & Reproduction

### Prerequisites
- Python 3.10+ (tested on Python 3.12.10)
- Virtual environment

### Setup
```bash
# 1. Clone repository and navigate to workspace
git clone <repo_url>
cd calllens

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

# 4. Install pinned approved dependencies
pip install -r requirements.txt
```

### Reproduce Data & Benchmarks
```bash
# 1. Run full test suite (57 tests)
pytest -v

# 2. Download and prepare FLEURS dataset (30 clips <= 28s)
python scripts/get_fleurs.py

# 3. Generate noise & silence clips (Exp D)
python scripts/gen_noise.py

# 4. Generate BFSI banking utterances (Exp F)
python scripts/gen_utterances.py

# 5. Run Dry-Run benchmark verification
python calllens/benchmark.py --dry-run

# 6. Execute full benchmark suite (360 evaluations)
python calllens/benchmark.py
```

### Run Interactive Web UI
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

## 6. Citations & Attribution

- **FLEURS Hindi India (`hi_in`) Dataset:**
  - Conneau, A., et al. (2022). *FLEURS: Few-shot Learning Evaluation of Universal Representations of Speech*.
  - Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
- **Gnani Speech AI Platform:**
  - Gnani.ai Prisma STT (v2.5 / v3.0) and Timbre TTS (v2.5).
  - SDK: `gnani-vachana==0.9.0`.
