# HANDOVER

## Latest session
- Date/model: 2026-11-09 / Claude 3.5 Sonnet / Antigravity Agent

## Done
- M0 Foundation completed:
  - Inspected workspace and verified Python 3.12.10 environment.
  - Created `.venv` virtual environment with pinned versions of all 14 approved dependencies.
  - Inspected `gnani-vachana` SDK (v0.9.0) methods, signatures, parameters, and models.
  - Documented findings in `docs/ASSUMPTIONS.md` and `docs/DECISIONS.md`.
  - Initialized git repository with robust `.gitignore`.
  - Added package layout (`calllens`, `scripts`, `tests`, `app`, `docs`).
  - Added `tests/test_scaffold.py` and confirmed passing pytest suite.
- M1 API Client completed:
  - Implemented `calllens/gnani_client.py` with centralized interface, SHA-256 caching, live cap enforcement (`MAX_LIVE_CALLS`), max 2 concurrency control, bounded retries (exponential backoff for 429/5xx), secret redacting logger, and mock mode fallback.
  - Implemented `scripts/usage_probe.py` supporting dry-run/mock mode and `--live` execution.
  - Added unit test suite in `tests/test_client.py`.
- M2 Data Engineering completed:
  - Implemented `scripts/get_fleurs.py` downloading and extracting 30 FLEURS Hindi clips (duration <= 28s) with safe tar traversal checks and CC BY 4.0 attribution.
  - Implemented `scripts/gen_noise.py` generating 20 five-second clips (10 seeded white noise, 10 silence) for Experiment D.
  - Implemented `scripts/gen_utterances.py` generating 10 synthetic BFSI banking utterances for Experiment F with `ground_truth.json`.
  - Added `tests/test_data.py`.
- M3 Signal Processing & Metrics completed:
  - Implemented `calllens/degrade.py` (Butterworth bandpass 300-3400Hz, 8kHz polyphase resample, 8-bit mu-law companding, return to 16kHz, noise generation, SNR measurement within +/-0.5 dB).
  - Implemented `calllens/metrics.py` (Unicode NFC, punctuation strip, WER/CER via jiwer, false-text rate, P50/P95 latencies, RTF, clip-level bootstrap 95% CIs).
  - Implemented `calllens/extract.py` (BFSI amount and due-day regex/rule extractor).
  - Added `tests/test_degrade.py`, `tests/test_metrics.py`, `tests/test_extract.py`.
- M4 Benchmarking completed:
  - Implemented `calllens/benchmark.py` with SQLite via SQLAlchemy, resumable execution, dry-run mode, 95% bootstrap CIs.
  - Executed reproducible 360-evaluation benchmark suite.
  - Generated `tests/results.md` and publication charts (`docs/wer_by_condition.png`, `docs/wer_vs_latency.png`).
- M5 Interactive Stress Lab completed:
  - Implemented FastAPI application `app/main.py` with rate limiting (10 req/min), 5 MB upload ceiling, 30-second audio constraint, and safe error handling.
  - Built responsive dark web interface (`app/static/index.html`, `styles.css`, `app.js`).
  - Added `tests/test_app.py`.
- M6 Documentation & Security completed:
  - Authored `docs/THREAT.md`, `docs/FAILURE.md`, `docs/DATA.md`, `docs/ROLLBACK.md` with exact file:line citations.
  - Updated `README.md` with honest claims, results tables, architecture, reproduction instructions, and citations.
  - Total test suite: 57 tests passing (`pytest -v`).

## In progress
- Independent Engineering Audit and Release Validation.

## Broken or risky
- Live API calls require user's live Gnani credentials and explicit `go`. Offline/mock benchmark is fully reproducible.

## Next
- Complete independent engineering audit, adversarial evaluation, and produce final release audit report.



## Do not touch
- `.env` and all secret values.
- `../calllens-data` or any existing user data/cache.
- Never stage datasets, audio, cache, local databases, or secrets.

