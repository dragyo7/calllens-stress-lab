# HANDOVER

## Latest session
- Date/model: 2026-11-09 / Claude 3.5 Sonnet / Antigravity Agent
- Milestone: Forensic QA, Real-Browser Testing & Independent Audit Complete

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
- Forensic QA Audit & Release Validation completed:
  - Executed real headless Google Chrome (v142.0.x) browser tests across desktop and mobile viewports.
  - Captured 5 genuine screenshots in `docs/screenshots/`.
  - Authored hard backend test suite (`tests/test_hard_backend.py`, 15 tests).
  - Authored security adversarial test suite (`tests/test_security_adversarial.py`, 7 tests).
  - Authored audio/metric adversarial test suite (`tests/test_audio_metric_adversarial.py`, 10 tests).
  - Corrected defects: `DEF-001` (XSS detail escaping), `DEF-002` (Starlette 413 constant), `DEF-003` (DOM `#error-banner` replacing `alert()`), `DEF-004` (audio duration calculation).
  - Authored `docs/FORENSIC_QA_REPORT.md`, `docs/BROWSER_TEST_REPORT.md`, `docs/SECURITY_TEST_REPORT.md`, `docs/BENCHMARK_PROVENANCE_AUDIT.md`, and `docs/CLAUDE_HANDOFF.md`.
  - Total automated test suite: **89 passed in 10.47s**, 0 failed, 0 warnings.
  - Zero live Gnani API calls were made or charged.

## In progress
- None (All development, test, browser verification, and audit milestones completed).

## Broken or risky
- Live provider benchmark numbers in `tests/results.md` reflect offline deterministic mock baseline; live API benchmarking is gated awaiting user credentials and explicit `go`.

## Next
1. Review final audit report and screenshots in `docs/`.
2. Present application and audit findings for The Great Indian Internship Challenge.
3. (Optional) Provide live Gnani credentials to run live Gate G1 probe (`python scripts/usage_probe.py --live`).

## Do not touch
- `.env` and all secret values.
- `../calllens-data` or any existing user data/cache.
- Never stage datasets, audio, cache, local databases, or secrets.
