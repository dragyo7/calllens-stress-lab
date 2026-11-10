# CallLens — Architectural Decision Records (ADR Register)

**Document ID:** `CL-ADR-001`  
**Version:** 2.0.0  
**Status:** Canonical Reference  
**Last Updated:** November 2026  
**Author:** Technical Ownership & Engineering Governance  

---

## 1. Governance Context

This register formally records the architectural, technical, and operational decisions governing CallLens. Every decision documents the context, alternatives considered, chosen approach, and consequences.

---

## 2. Completed Architecture Decision Records (ADRs)

### ADR D-001: SQLite WAL Mode for Persistent Relational Storage
- **Context:** The system requires local structured data storage for benchmark evaluations and interactive session histories without introducing heavyweight database server dependencies (Postgres/MySQL).
- **Decision:** Use SQLite 3 configured with Write-Ahead Logging (`PRAGMA journal_mode=WAL;`), `synchronous=NORMAL`, and a `busy_timeout` of 5,000 ms.
- **Consequences:** Provides high-throughput concurrent reads and atomic writes without table-locking collisions; zero operational overhead for local and embedded deployments.

### ADR D-002: ITU-T G.712 Digital Filter Implementation
- **Context:** Modeling realistic PSTN telephony audio degradation requires accurate spectral bandpass filtering (300 Hz to 3,400 Hz).
- **Decision:** Implement an 8th-order digital Butterworth IIR bandpass filter via `scipy.signal` with SOS (second-order sections) representation for numerical stability.
- **Consequences:** Faithfully reproduces PSTN telephony frequency roll-off; eliminates numerical instability associated with high-order transfer polynomials.

### ADR D-003: 1,000-Resample Non-Parametric Bootstrap Confidence Intervals
- **Context:** Comparing model Word Error Rates (WER) across acoustic conditions requires establishing whether observed error differences are statistically significant or artifacts of sample variance.
- **Decision:** Implement a non-parametric bootstrap resampling engine generating 1,000 resamples with replacement, computing empirical 95% confidence intervals ($2.5^{\text{th}}$ and $97.5^{\text{th}}$ percentiles).
- **Consequences:** Generates robust, distribution-free confidence bounds without assuming normal error distributions.

### ADR D-004: Token-Bucket Rate Limiter with File-Lock Concurrency Guard
- **Context:** Preventing provider rate-limiting and ensuring concurrency safety across multi-threaded or multi-process execution.
- **Decision:** Combine an in-memory Token-Bucket rate limiter (5 burst, 2 sustained) with an OS-level file lock (`call_accounting.lock`) guarding `call_accounting.json`.
- **Consequences:** Eliminates race conditions during counter updates and guarantees that total external calls never exceed configured quota ceilings.

### ADR D-005: Fail-Closed Default Policy for External Cloud APIs
- **Context:** Risk of accidental API credit burn during automated test runs and local developer experimentation.
- **Decision:** Enforce `ALLOW_LIVE_API=0` by default. Outbound requests are blocked at the application boundary and redirected to a deterministic mock engine unless explicitly overridden.
- **Consequences:** Zero financial cost during CI/CD and regression testing; absolute protection against accidental credit drain.

### ADR D-006: External Dedicated Data Storage Outside Code Repository
- **Context:** Version-controlling audio assets and database files inflates git repository size and risks merge collisions.
- **Decision:** Store all audio assets (`recordings/`, `tts_audio/`), temporary files (`temp/`), and database files (`benchmark.db`) in a dedicated directory outside the repository (`E:\Gnani AI proj\calllens-data`).
- **Consequences:** Keeps the git repository lean and fast; guarantees that audio assets and benchmark histories persist undamaged across git branch switches and pulls.

### ADR D-007: Zero-Dependency Vanilla ES6 Frontend
- **Context:** Building an interactive, high-performance UI without the complexity of Node.js build pipelines, Webpack, Babel, or heavy client-side frameworks.
- **Decision:** Implement the frontend in native HTML5, modular CSS3, and vanilla ES6 JavaScript.
- **Consequences:** Zero build step; instantaneous reload during development; zero client-side dependency security vulnerabilities; high runtime execution speed.

### ADR D-008: Native Chrome DevTools Protocol (CDP) for E2E Automation
- **Context:** Verifying browser DOM interactions, Web Audio APIs, and console error cleanliness in automated CI pipelines without large external browser-driver dependencies.
- **Decision:** Implement a lightweight Python script (`tests/verify_browser_e2e.py`) interacting directly with Chrome's native DevTools WebSocket port.
- **Consequences:** Fast, dependency-free browser verification with complete visibility into browser console errors and unhandled exceptions.

### ADR D-009: Strict Separation of Historical Benchmark Data from Interactive History
- **Context:** Need to preserve the canonical 360-sample benchmark dataset while supporting dynamic recording, transcription, and deletion in interactive sessions.
- **Decision:** Isolate immutable benchmark evaluations in `benchmark_results` and interactive runtime operations in `history_records`.
- **Consequences:** Guarantees that interactive user deletions or test operations can never mutate or delete historical benchmark research data.

### ADR D-010: Web Audio API & MediaRecorder for In-Browser Capture
- **Context:** Providing native microphone recording capability in modern browsers.
- **Decision:** Use standard HTML5 `navigator.mediaDevices.getUserMedia()` coupled with `MediaRecorder` emitting 250 ms audio chunks.
- **Consequences:** High-fidelity audio capture across modern browsers without requiring browser plugins.

### ADR D-011: Dual WebSocket Signals for Session Finalization
- **Context:** Discrepancies between frontend and backend event names caused hanging WebSocket connections when stopping recordings.
- **Decision:** Support both `finish_recording` and `stop` actions in `/ws/speech` handling, and emit both `{ action: 'finish_recording', type: 'stop' }` from client.
- **Consequences:** Eliminates socket race conditions and ensures clean connection teardown.

### ADR D-012: Atomic Cascading Asset Deletion
- **Context:** Deleting audio sessions must prevent orphaned database records or orphaned files on disk.
- **Decision:** Execute SQLite deletion inside an ACID transaction followed immediately by physical disk file unlinking.
- **Consequences:** Ensures 100% synchronization between database metadata and physical storage assets.

### ADR D-013: Plain-Language Navigation Hierarchy for General Audiences
- **Context:** Complex technical terminology intimidated first-time users, evaluators, and non-technical stakeholders.
- **Decision:** Standardize navigation labels into clear functional terms: *Overview*, *Record & Transcribe*, *Convert Text to Speech*, *My Recordings*, *Speech Quality Testing*, *Compare AI Models*, *Payment Follow-up Assistant*, *System Health*, and *How It Works*.
- **Consequences:** Dramatically improves product usability while preserving full technical depth within relevant detailed views.

### ADR D-014: Dual Contract Redundancy for Frontend-Backend Resilience
- **Context:** Divergent key naming conventions (`duration_sec` vs `audio_duration_sec`, `records` vs `history`) caused runtime JavaScript crashes (`undefined.toFixed(2)`).
- **Decision:** Emit dual keys across all API responses and implement null-coalescing fallbacks (`data.audio_duration_sec ?? data.duration_sec ?? 0`) in JavaScript.
- **Consequences:** Total immunity from property-name mismatches and backwards compatibility with legacy API consumers.

### ADR D-015: Perimeter Case Normalization for Indic Voice Talents
- **Context:** Third-party speech synthesis engines require strict capitalization for voice names (e.g., `Pranav`), throwing fatal errors when receiving lowercase strings (`pranav`).
- **Decision:** Enforce perimeter case normalization (`voice.strip().capitalize()`) at both the API Gateway and Client integration layers.
- **Consequences:** Fault-tolerant voice synthesis regardless of case variations submitted by clients or external integrations.

### ADR D-016: Production Docker Containerization & WSL2 Engine Integration
- **Context:** Delivering a reliable, reproducible deployment environment that runs seamlessly on developer machines (Windows 11 / WSL2) and cloud servers (Linux) without requiring heavy GUI installers or risking file-locking errors on SQLite over Windows `drvfs` mounts.
- **Decision:** Build a production Docker image using Debian slim with non-root security (`appuser`, UID 1000), Linux audio runtimes (`libsndfile1`, `ffmpeg`), and Docker Compose mounting `./data:/app/data`. Bridge WSL2 Kali Linux Docker Engine to Windows via `.local/bin` command wrappers, configure `vmIdleTimeout=-1` in `~/.wslconfig`, and maintain a keep-alive background daemon.
- **Consequences:** Fast container builds, 100% restart persistence of SQLite and audio assets across `docker compose down && docker compose up -d`, non-root security compliance, and zero drvfs SQLite locking errors.

### ADR D-017: Multi-Process Call Accounting with Persistent Dead Man's Switch
- **Context:** Risk of accidental API credit burn or runaway network requests during automated test runs, multi-process benchmark executions, or container restarts.
- **Decision:** Centralize call accounting in a persistent JSON file (`call_accounting.json`) protected by cross-process OS file locking (`msvcrt` on Windows, `fcntl` on Linux). Enforce an atomic reserve-and-commit lifecycle with a hard ceiling (`MAX_LIVE_CALLS`).
- **Consequences:** Guarantees absolute protection against credit overruns across concurrent processes and threads; raises `CallLimitExceededError` fail-closed if the quota is reached.

---

## 3. Open Architectural Decisions (Under Consideration)

- **OD-001 (Real-Time Streaming Transcripts):** Investigating chunk-by-chunk partial transcript emissions over `/ws/speech` once live streaming ASR provider credentials are integrated.
- **OD-002 (FastAPI Router Decomposition):** Planning the decomposition of `app/main.py` into modular FastAPI `APIRouter` files for the v2.1.0 release milestone.

