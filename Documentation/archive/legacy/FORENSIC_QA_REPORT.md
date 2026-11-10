# CallLens Stress Lab — Forensic QA & Verification Report
**Date:** 2026-11-09  
**Auditor:** Independent Principal QA & Security Engineer  
**Harness / Environment:** Python 3.12.10, Windows NT 10.0.26300, Git 2.55.0, Google Chrome 142.0.x  
**Mode:** Independent Forensic Verification (Zero Live API Spending)

---

## 1. Executive Summary & Audit Baseline

This audit independently tested the claims made in the initial project release. Rather than accepting passing unit test counts as sufficient evidence of product readiness, this evaluation subjected the system to:
1. Real headless Google Chrome browser interactions and viewport renders.
2. Hard backend boundary conditions (15 edge cases).
3. Adversarial audio signal edge cases (clipping, silence, odd length, stereo downmixing, zero SNR).
4. Direct cryptographic and provenance forensics on the SQLite database (`benchmark.db`).
5. Security injection and boundary attacks (XSS, SQLi, path traversal, 5 MB upload ceiling, 30s duration enforcement, rate limiting).

### Forensic Headline Finding
> [!CAUTION]
> **Provenance Transparency on Benchmark Metrics:**
> The SQLite database (`benchmark.db`) contains **360 valid evaluation rows**; however, forensic code tracing reveals that **100% of these evaluations were generated via offline deterministic mock mode**.
> - The repeated **0.480-second latency** is not a provider inference measurement; it originates from a hardcoded mock return in `calllens/gnani_client.py:221`.
> - The **0.0000 WER** in clean and telephony conditions is not live model transcription; it originates from `calllens/benchmark.py:168` setting `mock_transcript = raw_ref`.
> - Therefore, while the benchmarking pipeline, statistical bootstrap mathematics, database schema, and degradation mechanics are **100% verified and operational**, the published figures represent a **synthetic pipeline baseline**, not verified Gnani live API accuracy.

---

## 2. Test Execution & Scorecard

### Test Suite Summary
- **Execution Command:** `.venv\Scripts\pytest -v`
- **Total Tests:** 89 collected and executed
- **Results:** **89 PASSED, 0 FAILED, 0 WARNINGS** (Duration: 10.28 seconds)

| Test Module | Tests | Status | Scope Verified |
| :--- | :---: | :---: | :--- |
| `tests/test_scaffold.py` | 2 | **PASS** | Python version $\ge 3.10$, import integrity of all 14 approved dependencies |
| `tests/test_client.py` | 8 | **PASS** | Centralized client routing, SHA-256 caching, live cap blocking ($N+1$), bounded retries, logging redaction, concurrency limit |
| `tests/test_data.py` | 4 | **PASS** | External dataset layout (`../calllens-data`), FLEURS CC BY 4.0 attribution, Exp D 20 clips, Exp F 10 utterances & ground truth |
| `tests/test_degrade.py` | 5 | **PASS** | Butterworth bandpass filter, $\mu$-law companding, polyphase resampling, SNR tolerance on 3 signals ($\pm 0.5$ dB) |
| `tests/test_metrics.py` | 6 | **PASS** | Reference `a b c` vs `a x c` ($\text{WER}=0.3333$), Unicode NFC, Devanagari danda stripping, CER, bootstrap 95% CI |
| `tests/test_extract.py` | 22 | **PASS** | Mandatory examples (2.25 lakh, 3,50,000 rupees, ₹2.25 crore, 5 तारीख तक) + 18 edge cases |
| `tests/test_app.py` | 10 | **PASS** | Endpoints (`GET /`, `/api/health`, `/api/clips`, `/api/stress`), rate limit (10 req/min), 5 MB upload ceiling, 30s audio limit |
| `tests/test_hard_backend.py` | 15 | **PASS** | 15 boundary cases (malformed JSON, extra fields, database isolation, concurrent mock requests, missing fixtures) |
| `tests/test_security_adversarial.py` | 7 | **PASS** | XSS reflection sanitization, SQLi resistance, path traversal blocking, zero-byte file handling, 5 MB boundary |
| `tests/test_audio_metric_adversarial.py` | 10 | **PASS** | Silence, clipping, stereo downmixing, odd lengths, 5 hand-calculated WER cases, repeated words |

---

## 3. Real Browser Testing Evidence

- **Browser Engine:** Google Chrome (`C:\Program Files\Google\Chrome\Application\chrome.exe`), headless mode with `--headless=new` and `--disable-gpu`.
- **Target URL:** `http://127.0.0.1:8000` (FastAPI + Uvicorn server).
- **Verified Workflows:**
  1. **Initial Page Load:** Clean render, status badge reads `MOCK MODE (DEFAULT)`, zero console errors, zero broken asset requests.
  2. **Clip Selection:** Dynamic population of 24 pre-loaded clips from `/api/clips` across FLEURS, BFSI, and Noise categories.
  3. **Condition Toggle:** Interactive selection between Clean, Telephony (300–3400 Hz), Tel + 10 dB SNR, and Tel + 0 dB SNR.
  4. **Side-by-Side Comparison:** Triggered stress evaluation displays dual model cards (Prisma v2.5 baseline vs Prisma v3.0), comparative WER/CER badges, latency metrics, and extracted BFSI entity checklist.
  5. **Error & Empty State:** Submitting without clip or audio displays an accessible inline `#error-banner` (`role="alert"`), preventing silent failures.
  6. **Responsive Layouts:** Rendered and captured at 1440px desktop width and 390px mobile viewport width.

### Captured Genuine Screenshots:
- `docs/screenshots/initial_dashboard.png` (21,675 bytes)
- `docs/screenshots/selected_clip.png` (22,914 bytes)
- `docs/screenshots/side_by_side_comparison.png` (38,019 bytes)
- `docs/screenshots/error_state.png` (22,989 bytes)
- `docs/screenshots/mobile_layout.png` (2,743 bytes)

---

## 4. Defect Findings & Corrective Actions

| ID | Severity | Defect Description | Root Cause | Corrective Action & Verification |
| :--- | :---: | :--- | :--- | :--- |
| **DEF-001** | **Medium** | Raw user string reflection in 404 error detail. | In `app/main.py`, `req_data.clip_id` was interpolated unescaped into `f"Clip ID '{req_data.clip_id}' not found..."`. | Applied `html.escape(str(req_data.clip_id)[:64])`. Verified in `tests/test_security_adversarial.py`. |
| **DEF-002** | **Low** | Starlette deprecation warning on HTTP 413. | Used deprecated `HTTP_413_REQUEST_ENTITY_TOO_LARGE` constant. | Migrated to `status.HTTP_413_CONTENT_TOO_LARGE`. Zero pytest warnings achieved. |
| **DEF-003** | **Low** | Browser alert() blocking automated flows. | `app.js` used native browser `alert()` on empty form submission, which hangs headless browsers. | Replaced with DOM `#error-banner` (`role="alert"`). Captured in `docs/screenshots/error_state.png`. |
| **DEF-004** | **Informational** | Audio read stream pointer EOF in duration check. | `sf.read(bio)` left stream at EOF before `sf.info(bio)`. | Replaced with direct sample count calculation `len(audio_data) / sr`. |

---

## 5. Final Release Verdict

### **VERDICT: READY WITH DISCLOSED LIMITATIONS**

1. **Software Engineering & Quality:** The codebase is robust, modular, clean, fully documented, and passes **89 automated tests**.
2. **Browser UX & Real Runtime:** The web application is verified via headless Google Chrome with genuine screenshot artifacts.
3. **Security:** Upload ceilings, duration constraints, IP rate limiting, secret redaction, and error handling are fully operational.
4. **Research Limitation:** The published 360 benchmark numbers are derived from deterministic mock fixtures. They validate pipeline reproducibility, but must be accompanied by explicit disclosure that live provider accuracy requires user-authorized credentials.
