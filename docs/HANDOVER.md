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
  - Added unit test suite in `tests/test_client.py` (all 10 tests passing across suite).

## In progress
- GATE G1: Awaiting user approval for 4 live probe calls.

## Broken or risky
- Live calls prohibited without explicit user approval.
- Currently running in MOCK mode until Gate G1 decision.

## Next
- Present Gate G1 plan to user.
- Upon approval, execute `scripts/usage_probe.py --live` and record metrics.
- Proceed to M2 (Data Engineering: FLEURS fetch, noise/utterance generation, format pilot).


## Do not touch
- `.env` and all secret values.
- `../calllens-data` or any existing user data/cache.
- Never stage datasets, audio, cache, local databases, or secrets.

