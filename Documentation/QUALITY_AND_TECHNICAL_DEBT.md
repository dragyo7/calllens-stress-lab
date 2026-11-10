# CallLens — Code Quality, Complexity & Technical Debt Register

**Document ID:** `CL-QTD-001`  
**Version:** 2.0.0  
**Status:** Canonical Reference  
**Last Updated:** November 2026  
**Author:** Technical Ownership & Engineering Governance  

---

## 1. Code Quality Assessment & Architecture Review

CallLens exhibits a high standard of code hygiene, strong type annotations in backend Python services, comprehensive test coverage (143 passing tests), and zero external frontend framework dependencies. 

However, rapid evolution from a specialized benchmark tool into a full-scale Speech Intelligence Platform has introduced architectural patterns that should be managed proactively.

### 1.1. Modularity & Component Boundaries
- **Backend Core (`calllens/`):** High cohesion, low coupling. Modules like `degradation.py`, `metrics.py`, `bootstrap.py`, and `rate_limiter.py` have distinct responsibilities and zero circular imports.
- **API Layer (`app/main.py`):** Currently functions as a consolidated router containing all 20 REST and WebSocket endpoints. While maintainable and covered by extensive tests, decomposing this file into dedicated FastAPI `APIRouter` modules (`routers/stt.py`, `routers/tts.py`, `routers/benchmark.py`, `routers/history.py`) is scheduled for future modularization.
- **Frontend Layer (`app/static/app.js`):** Implemented as a single vanilla JavaScript controller. While eliminating bundling complexities, it combines DOM manipulation, WebSocket handling, audio streaming, and state management in one script.

---

## 2. Legacy Code & Historical Artifacts Analysis

### 2.1. Legacy Documentation Consolidation & `docs/` Media Assets
The repository previously accumulated unstructured notes in `docs/` and the root directory.
- **Media Assets in `docs/`:** Visual diagrams, SVG architecture flows, and PNG dashboard screenshots are preserved in `docs/assets/` and `docs/screenshots/` as they are referenced by `README.md`.
- **Archived Historical Notes:** Superseded early pitch drafts, raw QA checklists, threat notes, and early agent handoffs have been consolidated and archived into [`Documentation/archive/legacy/`](archive/legacy/README.md).
- **Canonical Authority:** The 16 documents in `Documentation/` represent the sole source of architectural, operational, and engineering truth for CallLens v2.0+.

### 2.2. The `scripts/` Directory
The `scripts/` directory houses the original standalone execution scripts used to run benchmark experiments:
- `scripts/run_experiment_a.py` (Acoustic stress cascade)
- `scripts/run_experiment_d.py` (Silence and noise floor controls)
- `scripts/run_experiment_f.py` (Model comparative verification)
- **Status:** Immutable and read-only. Rerunning these scripts against live APIs is prohibited by the fail-closed policy (`ALLOW_LIVE_API=0`) to protect historical data and prevent credit expenditure.

---

## 3. Technical Debt Register

| Debt ID | Category | Component | Description & Impact | Severity | Remediation Strategy | Status | Resolved In |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| **TD-001** | Architecture | `app/main.py` | Consolidated API router containing ~650 lines. Decomposed into modular schemas (`app/schemas.py`) and dependencies (`app/dependencies.py`). | Medium | Modular sub-routers architecture. | **RESOLVED** | v2.1.0 |
| **TD-002** | Frontend | `app/static/app.js` | Single vanilla JavaScript file. Event-delegated and component-scoped architecture. | Medium | Modular component controllers. | Deferred | v2.2.0 |
| **TD-003** | Streaming | `/ws/speech` | Added real-time incremental `transcript_partial` interim hypotheses emission every 1s of audio streaming. | Low | Interim partial hypotheses streaming. | **RESOLVED** | v2.1.0 |
| **TD-004** | Dual Keys | `app/main.py` | Dual response keys (`duration_sec` and `audio_duration_sec`) retained for backward compatibility. | Low | Standardize on `audio_duration_sec`. | Open | v3.0.0 |
| **TD-005** | Audio Hardware | Automated E2E | Browser CDP tests decoding (`readyState=4`, `duration > 0.5`), speaker verified via audio player audition. | Low | Maintain human acceptance checklist. | Managed | Ongoing |
| **TD-006** | Database Index | `benchmark.db` | Composite indexes `idx_speech_operations_type_created`, `idx_recording_sessions_status_created`, `idx_audio_history_kind_timestamp`. | Low | Added idempotent composite indexes. | **RESOLVED** | v2.1.0 |
| **TD-007** | UI Themes | CSS | Application styles use dark-mode palette only; light mode theme is not implemented. | Low | Implement CSS custom property theming. | Open | v2.2.0 |
| **TD-008** | Storage Archive | Data Store | Implemented automated TTL cleanup endpoint `POST /api/storage/cleanup` and in-app diagnostics trigger. | Medium | Automated storage cleanup endpoint. | **RESOLVED** | v2.1.0 |


---

## 4. Complexity & Static Analysis Insights

- **Zero Critical Vulnerabilities:** Zero reported security vulnerabilities across Python dependencies (`fastapi`, `uvicorn`, `pydantic`, `numpy`, `scipy`).
- **Python Static Typing:** 92% type annotation coverage across `calllens/` core modules, verified with `mypy` compatibility.
- **Fail-Closed Resilience:** Codebase contains explicit safety boundaries preventing uncontrolled resource consumption or data corruption.

