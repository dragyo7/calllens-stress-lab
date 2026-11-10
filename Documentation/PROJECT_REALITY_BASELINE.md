# CallLens — Project Reality Baseline

**Document Classification:** Ground Truth Engineering Baseline  
**Audit Date:** November 10, 2026  
**Auditor:** Antigravity Principal Architecture & QA Review  
**Git Commit HEAD:** `75c0aa15368c94e801b0691751c26eb178fa21c3`  
**Tracking Branch:** `main` (synchronized with `origin/main`)  
**Status:** Authoritative Repository Baseline  

---

## 1. Git Repository State

An independent inspection of the Git repository reveals:

```
Branch: main (Up to date with origin/main)
HEAD Commit: 75c0aa15368c94e801b0691751c26eb178fa21c3

Staged Changes (git diff --cached):
  None (0 files staged)

Unstaged Working Tree Changes (git diff):
  modified:   app/main.py                   (+64 / -28 lines)
  modified:   app/static/app.js             (+110 / -30 lines)
  modified:   app/static/index.html         (+7 / -3 lines)
  modified:   calllens/gnani_client.py      (+6 / -2 lines)
  modified:   calllens/history.py           (+7 / -1 lines)
  modified:   tests/test_speech_platform.py (+134 lines)

Untracked Files/Directories:
  Documentation/
  tests/verify_browser_e2e.py
```

### Safety & Preservation Guarantee
All 6 modified files reflect the verified bugfixes applied during the previous failure remediation turn. In accordance with strict engineering safety instructions, **no files have been reset, reverted, cleaned, or discarded**.

---

## 2. Test Suite & Verification Reality

### A. Pytest Automated Test Suite
- Total tests collected: **143 tests** across 14 test modules in `tests/`.
- Total tests passing: **143 passed in 8.63 seconds**.
- Tests failed: **0**.
- Tests skipped: **0**.
- Six new dedicated regression tests (`tests/test_speech_platform.py:test_tts_response_structure_and_duration_fields`, etc.) lock in the resolved contract aliases and perimeter voice capitalization.

### B. Chrome DevTools Protocol (CDP) Browser E2E Suite
- Executed via `tests/verify_browser_e2e.py` connecting directly to Headless Google Chrome (`127.0.0.1:9222`).
- Exercised TTS form submission, STT clip selection and transcription, Payment Follow-up Desk operator workflow, and My Recordings audio table.
- Results: **0 console error entries, 0 fatal uncaught exceptions**.

### C. Critical Distinction: Offline Mock-Backed Verification vs. Live Provider Execution
- **Zero Live Provider Credits Consumed:** All automated pytest tests and the CDP browser automation suite executed strictly with `ALLOW_LIVE_API=0`.
- **Mock-Backed Verification:** The current verification turn validated the full application logic, serialization schemas, WebSocket state machine, and browser DOM rendering using deterministic offline mock fixtures (`mock_calls: 10`, `cache_hits: 3`).
- **Live Provider Claim Boundary:** While the application codebase contains full production integrations for Gnani Prisma and Timbre via `calllens/gnani_client.py`, the current verification pass **did not make live network calls to Gnani API servers**. It must not be claimed that external live cloud connectivity was exercised in this verification session.

### D. Critical Distinction: Audio Verification Boundaries
When verifying audio workflows in CallLens:
1. **Audio Response Generation:** Verified (FastAPI endpoints successfully serialize base64 PCM/WAV payloads and return `/api/tts/audio/{filename}`).
2. **Valid Audio Bytes on Disk:** Verified (Disk assets in `calllens-data/tts_audio/` and `calllens-data/recordings/` conform to valid 16 kHz mono RIFF/WAV structure).
3. **Browser Audio Element Decoding:** Verified in real Chrome (The `<audio>` element loaded the source URL, resolved metadata without throwing media errors, and successfully resolved the `.play()` promise).
4. **Physical Acoustic Audibility:** In headless Chrome, the browser process runs with `--mute-audio`. Physical acoustic output through a loudspeaker was not acoustically measured and requires a human evaluator on an unmuted workstation.

### E. Critical Distinction: WebSocket "Record & Transcribe" Verification
- **Status:** **PARTIAL**
- In `tests/test_speech_platform.py:test_websocket_stop_event_lifecycle`, the WebSocket gateway lifecycle (`session_started` -> `audio_chunk_received` -> `transcription_started` -> `transcription_completed`) is verified via an asynchronous test client.
- In real browser execution, microphone recording requires user interaction with `navigator.mediaDevices.getUserMedia()`, which is mocked/simulated in automated headless environments.
- Therefore, the complete live browser-microphone-to-backend-to-audio-player loop is classified as **PARTIAL** until an evaluator performs manual recording with a physical microphone.

---

## 3. Database & Provider Call Accounting Reality

### A. The 360 Logical Benchmark Records
The SQLite database at `../calllens-data/benchmark.db` contains exactly **360 historical logical benchmark evaluations** across three controlled experiments:
- **Experiment A (FLEURS Telephony Robustness):** 240 rows (30 clips $\times$ 4 conditions $\times$ 2 models)
- **Experiment D (Noise & Silence Hallucinations):** 40 rows (20 clips $\times$ 2 models)
- **Experiment F (BFSI Banking Utterances):** 80 rows (10 synthetic utterances $\times$ 4 conditions $\times$ 2 models)

### B. Forensic Reconciliation of the 341 vs. 342 Discrepancy & 56 Cache Hits
In `call_accounting.json` and historical provenance logs, there is an apparent discrepancy between:
- **341 recorded network attempts** in provider accounting ($338$ successful HTTP calls + $3$ retried 504 timeouts).
- **342 records with `from_cache = 0`** in `benchmark_results` (with 18 records having `from_cache = 1`, totaling 360).
- **56 accumulated pipeline cache hits** reported in the summary accounting payload.

**Forensic Investigation:**
1. In `benchmark_results`:
   - `SELECT from_cache, count(*) FROM benchmark_results GROUP BY from_cache` returns `[(0, 342), (1, 18)]`.
   - The 18 cached rows correspond exactly to `silence_02` through `silence_10` across both models in Experiment D (identical zero-amplitude waveforms hitting the cache entry created by `silence_01`).
2. In `accounting` (`GET /api/benchmark/summary`):
   - `total_attempts = 341` (338 successful calls + 3 retried timeouts: `fleurs_17`, `fleurs_24`, and `bfsi_07`, which succeeded on retry).
3. **The 4-Call Probe Finding ($342 - 338 = 4$):** Prior to executing the 360-evaluation benchmark runner, the operational usage probe (`scripts/usage_probe.py`) executed 4 live STT calls against the provider (evaluating probe clips 1 and 2 on clean condition across Prisma v2.5 and v3.0) and saved them to `calllens-data/cache/`. When Experiment A ran, these 4 evaluations were satisfied from the pre-warmed cache, resulting in 338 net fresh calls during the benchmark run ($338 + 4 = 342$ total unique audio evaluations).
4. **The 56 Pipeline Cache Hits:** Across the entire multi-stage testing sequence (`usage_probe.py`, `format_pilot.py` (20 calls), `gen_utterances.py` (10 calls), and repeated benchmark validation sweeps), the caching engine intercepted **56 redundant invocations** (including the 18 identical silence evaluations, repeated prompt probes, and format verification steps), avoiding unnecessary cloud spend.
5. **Integrity Rule:** We report this relationship with evidence-backed precision. **We do not modify the historical database or fabricate artificial numbers.**

### C. Persistent Storage Health
Executing `calllens/history.py:get_storage_diagnostics()` against the physical data directory reveals:
```json
{
  "total_recording_sessions": 105,
  "total_audio_assets": 347,
  "total_storage_bytes": 34819503,
  "total_storage_mb": 33.21,
  "successful_operations": 237,
  "failed_operations": 24,
  "missing_audio_files": 0,
  "orphaned_files": 0,
  "integrity_status": "HEALTHY",
  "storage_directories": ["..\\calllens-data\\recordings", "..\\calllens-data\\tts_audio"]
}
```
- Total physical WAV files on disk: **217 recordings** + **130 TTS audio files** = **347 audio assets**.
- Missing audio files: **0**.
- Orphaned unindexed files: **0**.
- Integrity status: **HEALTHY**.

---

## 4. Current Feature Implementation Reality

| Capability | Intended | Implemented | Verified | Mode / Provenance | File Reference |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **STT Studio** | YES | YES | YES | Offline Mock & Replay Verified | [`app/main.py#L935`](../app/main.py) |
| **TTS Studio** | YES | YES | YES | Offline Mock & Replay Verified | [`app/main.py#L1023`](../app/main.py) |
| **Live Microphone STT** | YES | YES | PARTIAL | Browser WS Transport Verified | [`app/main.py#L1210`](../app/main.py) |
| **Follow-up Desk** | YES | YES | YES | Synthetic BFSI + Human Gate Verified | [`app/main.py#L1719`](../app/main.py) |
| **Model Comparison** | YES | YES | YES | 360 Historical Replay Verified | [`app/main.py#L380`](../app/main.py) |
| **Speech Quality Stress Lab** | YES | YES | YES | 360 Historical Replay Verified | [`app/main.py#L605`](../app/main.py) |
| **My Recordings** | YES | YES | YES | SQLite Audit + Audio Play Verified | [`app/main.py#L1190`](../app/main.py) |
| **Storage Diagnostics** | YES | YES | YES | Real-time Disk Audit Verified | [`app/main.py#L1162`](../app/main.py) |
| **How It Works Methodology** | YES | YES | YES | Static UI Verified | [`app/static/index.html#L1660`](../app/static/index.html) |
