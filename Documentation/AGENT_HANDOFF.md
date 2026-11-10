# CallLens — Agent & Engineer Handoff Protocol

**Document ID:** `CL-HND-001`  
**Version:** 2.0.0  
**Status:** Canonical Reference  
**Last Updated:** November 2026  
**Author:** Technical Ownership & Engineering Governance  

---

## 1. Purpose & Target Audience

This document is the **primary technical onboarding and handoff specification** for future software engineers, technical leads, and autonomous AI coding agents assuming ownership of the **CallLens** repository. 

Read this document first before inspecting code or proposing modifications.

---

## 2. Essential Repository & Data Anatomy

```
E:\Gnani AI proj\
├── calllens\                            # Application Source & Code Repository (Git)
│   ├── app\
│   │   ├── main.py                      # FastAPI application gateway (20 endpoints)
│   │   └── static\
│   │       ├── index.html               # Single-page UI (10 unified tabs)
│   │       ├── app.js                   # Client controller (Vanilla ES6, Web Audio)
│   │       └── style.css                # Enterprise dark-mode stylesheet
│   ├── calllens\                        # Core Python Intelligence Service Tier
│   │   ├── degradation.py               # G.712 filter, μ-law, SNR noise injection
│   │   ├── metrics.py                   # Levenshtein WER, CER, Word Accuracy
│   │   ├── evaluator.py                 # Benchmark execution orchestrator
│   │   ├── bootstrap.py                 # 1,000-resample non-parametric bootstrap CIs
│   │   ├── gnani_client.py              # ASR/TTS client, voice normalization, mock engine
│   │   ├── history.py                   # SQLite ACID session management
│   │   ├── storage_manager.py           # Storage diagnostics, asset integrity, unlinking
│   │   └── rate_limiter.py              # Token-bucket limiter & attempt cap guard
│   ├── tests\                           # 14 Pytest Test Modules (143 Tests)
│   │   ├── test_speech_platform.py      # Core platform regression suite (20 tests)
│   │   ├── verify_browser_e2e.py        # Native Chrome CDP headless automation
│   │   └── ...                          # DSP, accounting, evaluator, API test modules
│   ├── Documentation\                   # CANONICAL ARCHITECTURE DOCUMENTATION (v2.0+)
│   ├── docs\                            # Historical legacy notes & sketches (Preserved)
│   └── scripts\                         # Historical benchmark experiment runners (Read-only)
│
└── calllens-data\                       # Dedicated Persistent Storage (EXTERNAL TO GIT)
    ├── benchmark.db                     # SQLite 3 Database (WAL Mode, 360 benchmark records)
    ├── call_accounting.json             # Provider call counter & network attempt log
    ├── call_accounting.lock             # OS-level file lock for accounting concurrency
    ├── recordings\                      # Audio store for STT inputs (217 WAV files)
    ├── tts_audio\                       # Audio store for synthesized TTS (130 WAV files)
    └── temp\                            # Transient scratch directory (0 files)
```

---

## 3. Ground-Truth Invariants & Architectural Rules

Any agent or engineer working on this codebase **MUST STRICTLY OBEY** the following invariants:

### Rule 1: The Zero-Credit Spend Policy (`ALLOW_LIVE_API=0`)
- **Default State:** Live network calls to external speech APIs are **prohibited**.
- Never alter the default `ALLOW_LIVE_API=0` policy in code or tests. Automated test suites and local runs must use the deterministic offline mock engine.
- External calls consume finite, paid credits. Do not spend live credits without explicit human user authorization.

### Rule 2: Immutability of the 360 Historical Benchmark Records
- The `benchmark_results` table in `calllens-data/benchmark.db` contains **exactly 360 rows** representing genuine scientific evaluations across Experiments A, D, and F.
- **Never modify, delete, truncate, or rerun** historical benchmark evaluations.
- Interactive user history (`history_records`) is isolated from benchmark data.

### Rule 3: External Storage Isolation
- Persistent audio files and databases reside in `../calllens-data/`.
- Do not commit `.wav` files, `.db` files, or `.lock` files into the git repository.
- Ensure all storage access utilizes `calllens/storage_manager.py` or configured environment paths.

### Rule 4: Preserving User Working Tree
- Never run `git reset --hard`, `git checkout .`, `git clean -fd`, or discard unstaged modifications without explicit user instruction.
- The working tree may contain intentional active edits. Always inspect `git status` first.

---

## 4. Key Lessons Learned & Defenses Against Common Traps

Future maintainers should be aware of known failure modes that were resolved during forensic remediation:

### Trap 1: The `undefined.toFixed(2)` Runtime Crash
- **Problem:** If an API endpoint returns `audio_duration_sec` and the frontend expects `duration_sec` (or vice versa), the browser crashes with `TypeError: Cannot read properties of undefined (reading 'toFixed')`.
- **Defense:** Always implement **Dual-Contract Redundancy**:
  - In FastAPI routes: Return both keys: `{"duration_sec": dur, "audio_duration_sec": dur}`.
  - In JavaScript: Access via null-coalescing: `(data.audio_duration_sec ?? data.duration_sec ?? 0).toFixed(2)`.

### Trap 2: Voice Name Capitalization (`ValueError: Invalid voice`)
- **Problem:** External TTS APIs require exact proper casing (`"Pranav"`). Sending lowercase (`"pranav"`) causes a fatal 400 error.
- **Defense:** Enforce perimeter normalization in `calllens/gnani_client.py`:
  ```python
  normalized_voice = voice_str.strip().capitalize()
  ```

### Trap 3: History Table Key Mismatches
- **Problem:** If the backend emits `{"records": [...]}` and the frontend expects `data.history`, the recordings table renders empty.
- **Defense:** The history endpoint emits both: `{"records": rows, "history": rows, "total_count": len(rows)}`. The frontend parses `data.records || data.history || []`.

### Trap 4: WebSocket Finalization Deadlock
- **Problem:** Frontend sending `{ action: 'stop' }` while the server was listening for `finish_recording` caused recording sessions to hang indefinitely.
- **Defense:** The server accepts both actions (`if action in ("finish_recording", "stop")`), and the client sends both: `{ action: 'finish_recording', type: 'stop' }`.

---

## 5. Development & Verification Commands

```powershell
# 1. Activate Virtual Environment (PowerShell)
.\.venv\Scripts\Activate.ps1

# 2. Run the Full Automated Test Suite (143 Tests)
.\.venv\Scripts\pytest -q

# 3. Check for Git Whitespace / Formatting Warnings
git diff --check

# 4. Run the Uvicorn Application Server (Port 8000)
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000

# 5. Run Headless Browser E2E Automation (With server active)
.\.venv\Scripts\python tests/verify_browser_e2e.py

# 6. Verify Benchmark Record Count
.\.venv\Scripts\python -c "import sqlite3; con = sqlite3.connect('E:/Gnani AI proj/calllens-data/benchmark.db'); print('Benchmark Rows:', con.execute('SELECT COUNT(*) FROM benchmark_results').fetchone()[0])"
```

---

## 6. Recommended Priority Backlog for Next Engineering Sprint

1. **FastAPI Router Decomposition (v2.1):** Break down `app/main.py` into distinct sub-routers under `app/routers/` to reduce file size.
2. **ES6 Module Refactor (v2.1):** Separate `app/static/app.js` into modular components (`stt.js`, `tts.js`, `compare.js`, `history.js`).
3. **Real-Time Streaming Transcripts (v2.2):** Upgrade `/ws/speech` to emit partial interim hypotheses as audio chunks arrive.
4. **Data Retention & TTL Pruning (v2.2):** Implement a daily cron task to delete user recordings older than 30 days.

