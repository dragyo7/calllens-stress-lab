# CallLens Stress Lab — Claude Handoff & Successor Guide

**Date:** 2026-11-09  
**From:** Independent Principal QA & Security Auditor  
**To:** Next Engineering Agent / Human Maintainer  
**Repository:** CallLens Stress Lab (`e:\Gnani AI proj\calllens`)  
**Data Directory:** `../calllens-data` (sibling directory, git-excluded)  
**Status:** **READY WITH DISCLOSED LIMITATIONS**  

---

## 1. Executive Summary of Audit Findings

The CallLens Stress Lab implementation has been independently audited, forensic-tested across backend boundaries and signal invariants, verified in headless Google Chrome with genuine screenshot artifacts, and confirmed green across an 89-test automated pytest suite.

### Core Audit Outcomes:
1. **Automated Test Scorecard:** **89 tests passing, 0 failures, 0 warnings** in 10.47 seconds.
2. **Browser Validation:** Verified in real Google Chrome (v142.0.x headless). Captured 5 genuine screenshots in `docs/screenshots/` across desktop and mobile viewports.
3. **Hard Backend Tests:** 15 adversarial boundary cases tested in `tests/test_hard_backend.py` (malformed JSON, extra fields, type errors, database isolation, concurrent mock requests, 404/400 handling).
4. **Security & Adversarial Controls:** Verified in `tests/test_security_adversarial.py` (5 MB upload ceiling, 30s audio duration rejection, XSS reflection sanitization, SQLi resistance, Zip-Slip traversal rejection, process-level rate limiting, secret log redaction).
5. **Audio & Metric Signal Tests:** Verified in `tests/test_audio_metric_adversarial.py` (all-zero silence, full-scale clipping, stereo downmixing, odd sample counts, hand-calculated WER edge cases, bootstrap 95% CIs).
6. **Benchmark & Provenance Audit:** Forensic reconciliation of all 360 database rows in `../calllens-data/benchmark.db`. Detailed disclosure that all 360 rows were generated in deterministic mock mode (`0.480s` latency and `0.0000` WER are mock fixtures, not live provider inferences).
7. **Defect Resolutions:** 4 defects identified and fixed with regression tests:
   - `DEF-001` (Medium): XSS reflection in 404 detail &rarr; sanitized via `html.escape()`.
   - `DEF-002` (Low): Starlette HTTP 413 deprecation warning &rarr; migrated to `HTTP_413_CONTENT_TOO_LARGE`.
   - `DEF-003` (Low): Native `alert()` blocking headless browsers &rarr; replaced with DOM `#error-banner`.
   - `DEF-004` (Info): Audio duration read pointer EOF &rarr; calculated directly from sample length.

---

## 2. Exact Repository State & Commit History

### Commit History:
- `c56253d`: `feat(calllens): complete end-to-end implementation of CallLens Stress Lab (M2-M6)`
- `5259ad6`: `feat(client): implement centralized gnani_client with caching, live cap and usage probe (M1)`
- `d1df6ca`: `feat(scaffold): complete M0 foundation, pinned requirements and environment verification`

### Active Git Working Tree:
- Core codebase: `calllens/`, `scripts/`, `tests/`, `app/`, `docs/`.
- No `.env`, API keys, bearer tokens, or secrets tracked or staged.
- External data directory: `../calllens-data` contains `benchmark.db`, `fleurs/`, `bfsi/`, `noise_silence/`, and `cache/`.

---

## 3. Strict Verification of Zero Live Calls

- **Live Provider Invocations:** **0** (Zero live calls made).
- **API Credits Consumed:** **0** (Zero Gnani credits spent).
- **Enforcement:** `calllens/gnani_client.py` defaults to `live=False` unless `x-live: 1` or `--live` is explicitly passed with a valid user-approved gate budget (`MAX_LIVE_CALLS`).
- **Gate Status:**
  - Gate G1 (Usage Probe, 2 calls): **PENDING USER AUTHORIZATION**.
  - Gate G2 (Exp F pilot, 10 calls): **PENDING USER AUTHORIZATION**.
  - Gate G3 (Full Benchmark, 360 calls): **PENDING USER AUTHORIZATION**.

---

## 4. Instructions for Future Agents & Human Maintainers

### Launching the Application Locally:
```powershell
# 1. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 2. Start FastAPI application server
uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Open `http://127.0.0.1:8000` in any modern web browser.

### Executing the Complete Test Suite:
```powershell
.\.venv\Scripts\pytest -v
```
Expected: 89 passed in ~10 seconds.

### Re-running Real Browser Screenshots (Headless Chrome):
```powershell
$CHROME = "C:\Program Files\Google\Chrome\Application\chrome.exe"
& $CHROME --headless=new --disable-gpu --no-sandbox --window-size=1440,1200 --screenshot="docs/screenshots/side_by_side_comparison.png" "http://127.0.0.1:8000/?clip_id=fleurs_hi_000&condition=tel&auto=1"
```

### Transitioning from Mock to Live Provider Benchmarking:
If the user provides explicit authorization and valid credentials in `.env`:
1. Verify credential via Gate G1 dry-run:
   ```powershell
   python scripts/usage_probe.py
   ```
2. Present exact call budget and request explicit user `go` before executing:
   ```powershell
   python scripts/usage_probe.py --live
   ```
3. Do **not** execute full live benchmark without user approval.

---

## 5. Exact Next Task

The forensic QA audit is complete. All deliverables (`docs/FORENSIC_QA_REPORT.md`, `docs/BROWSER_TEST_REPORT.md`, `docs/SECURITY_TEST_REPORT.md`, `docs/BENCHMARK_PROVENANCE_AUDIT.md`, `docs/CLAUDE_HANDOFF.md`, `docs/screenshots/`) are generated. The next task is to stage the audit files, commit the changes to Git, and deliver the final release readiness report to the user.
