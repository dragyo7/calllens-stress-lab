# CallLens — Architectural Extensibility & Future Roadmap
### Technical Design Review, Modular Readiness, Dependency Assessment & Complexity Matrix

**Document Purpose:** Senior architectural assessment of future product extensions for CallLens.  
**Scope:** Architectural evaluation only. None of the speculative enhancements below are implemented in the current frozen release.  
**Repository Baseline:** Synchronized at `abb0d45922d7d6de1a7b004c3a586750fa9e3b9a` (136 tests passing).

---

## 1. Executive Extensibility Assessment

CallLens was architected around modular separation of concerns:
- **`calllens/gnani_client.py`:** Centralized provider gateway with caching, rate limits, and credential filtering.
- **`calllens/degrade.py`:** Standardized acoustic signal processing pipeline (Butterworth filtering, G.711 $\mu$-law, SNR calibration).
- **`calllens/metrics.py`:** Statistical analysis engine (WER, CER, RTF, Bootstrap Confidence Intervals).
- **`calllens/extract.py`:** Regular expression and token-based entity extraction for financial Indian English and Devanagari.
- **`calllens/history.py`:** Relational SQLite persistence layer tracking sessions, audio assets, transcripts, and commitments.
- **`app/main.py`:** High-concurrency FastAPI REST and WebSocket controller.

Because storage, metrics, gateway routing, and signal processing are decoupled into independent Python packages, CallLens demonstrates strong architectural readiness for horizontal expansion into multi-lingual, multi-provider, and enterprise contact-center environments.

---

## 2. Detailed Technical Extensibility Review (15 Directions)

---

### Direction 1: Additional Indian Languages & Dialects
- **Current Readiness:** High. The existing STT and TTS endpoints already accept BCP-47 language codes (`hi-IN`, `ta-IN`, `te-IN`, `kn-IN`, `mr-IN`, `bn-IN`, `gu-IN`, `pa-IN`, `ml-IN`, `od-IN`).
- **Reusable Modules:** `calllens/gnani_client.py` (passes `language_code`), `app/main.py` (`STTRequest.language_code`), `calllens/history.py` (`AudioAsset.language`).
- **Required Changes:** Update frontend language selectors; add text normalization and Devanagari/Dravidian punctuation rules in `calllens/metrics.py`.
- **Dependencies:** None (uses existing `unicodedata` and `re`).
- **Security & Privacy:** Low risk; standard unicode string sanitization applies.
- **Estimated Complexity:** **Low**
- **Database Migration Required:** No (`language` column already exists in schema).
- **Provider Cost Impact:** Normal per-minute STT/TTS rates for new languages.

---

### Direction 2: Pluggable Multi-Provider Support (Bhashini, Whisper, Google Cloud Speech, Azure)
- **Current Readiness:** Medium. Gateway currently couples to `gnani_client.call()`.
- **Reusable Modules:** `calllens/degrade.py`, `calllens/metrics.py`, `calllens/history.py`.
- **Required Changes:** Introduce an abstract `BaseSpeechProvider` interface with `transcribe(audio_bytes)` and `synthesize(text, voice)`. Implement adapter classes (`GnaniProvider`, `BhashiniProvider`, `WhisperProvider`).
- **Dependencies:** Provider SDKs (`google-cloud-speech`, `azure-cognitiveservices-speech`, or local `faster-whisper`).
- **Security & Privacy:** Per-provider secret management; separate environment variables (`BHASHINI_API_KEY`, etc.).
- **Estimated Complexity:** **Medium**
- **Database Migration Required:** No (`model` column accommodates provider names).
- **Provider Cost Impact:** Dependent on external provider billing models.

---

### Direction 3: Additional Model Versions & Benchmark Comparisons
- **Current Readiness:** High. The benchmark orchestrator accepts arbitrary model strings and computes bootstrap confidence intervals.
- **Reusable Modules:** `calllens/benchmark.py`, `calllens/metrics.py`, SQLite `benchmark_results` schema.
- **Required Changes:** Add model strings to UI configuration; expand factorial benchmark matrix.
- **Dependencies:** None.
- **Security & Privacy:** None.
- **Estimated Complexity:** **Low**
- **Database Migration Required:** No.
- **Provider Cost Impact:** Linear increase in API calls per new model evaluated ($30 \text{ clips} \times 4 \text{ conditions} = 120$ calls per model).

---

### Direction 4: True Incremental Provider-Side Streaming STT
- **Current Readiness:** Low. Current Gnani Prisma STT operates via atomic HTTP REST gateway. CallLens currently buffers chunks over WebSockets and performs atomic REST transcription.
- **Reusable Modules:** `app/main.py` (`/ws/speech` connection lifecycle and binary packet transport).
- **Required Changes:** Replace REST buffer submission with gRPC bidirectional stream or chunked HTTP/2 if supported by upstream provider. Add `transcription_partial` WebSocket event handling in frontend.
- **Dependencies:** `grpcio`, `protobuf` (if gRPC); otherwise asynchronous chunk streaming client.
- **Security & Privacy:** WebSocket message size validation; packet flood mitigation.
- **Estimated Complexity:** **High**
- **Database Migration Required:** Yes (add `is_partial` flag and segment timestamps to `transcripts` table).
- **Provider Cost Impact:** Streaming connections may incur minimum stream duration rounding costs.

---

### Direction 5: Speaker Diarization (Agent vs. Customer Separation)
- **Current Readiness:** Medium. Telephony calls can be ingested as stereo WAV (Channel 0 = Agent, Channel 1 = Customer).
- **Reusable Modules:** `calllens/degrade.py` (channel splitting), `calllens/history.py` (`AudioAsset.channels`).
- **Required Changes:** Ingest stereo audio, transcribe channels independently, merge timestamps, and label speaker turns. For mono audio, integrate acoustic clustering (e.g., PyAnnote).
- **Dependencies:** `pyannote.audio` or provider-native diarization flags.
- **Security & Privacy:** Heightened PII handling for caller voice profiles.
- **Estimated Complexity:** **High** (for mono neural diarization) / **Medium** (for stereo dual-channel).
- **Database Migration Required:** Yes (add `speaker_label` and `start_ms`/`end_ms` to `transcripts` table).
- **Provider Cost Impact:** Dual-channel transcription doubles per-call ASR processing minutes.

---

### Direction 6: Emotion & Sentiment Analysis
- **Current Readiness:** Medium. Post-processing can analyze either raw audio acoustics (pitch, energy) or transcribed text sentiment.
- **Reusable Modules:** `app/main.py`, `calllens/extract.py`.
- **Required Changes:** Add acoustic sentiment classifier or Devanagari text sentiment model (e.g., fine-tuned IndicBERT). Add sentiment score cards to UI.
- **Dependencies:** `torch`, `transformers` (for local inference) or external sentiment API.
- **Security & Privacy:** Caller emotional distress data must comply with DPDP Act (India).
- **Estimated Complexity:** **Medium**
- **Database Migration Required:** Yes (add `sentiment_score` and `emotion_label` to `transcripts` or `followup_records`).
- **Provider Cost Impact:** Zero if run locally; API cost if outsourced.

---

### Direction 7: Telephony Call-Quality & Acoustic MOS Analytics
- **Current Readiness:** High. Signal processing tools in `degrade.py` already measure SNR, RMS energy, and sample clipping.
- **Reusable Modules:** `calllens/degrade.py`, `calllens/metrics.py`.
- **Required Changes:** Implement non-intrusive ITU-T P.563 / NISQA acoustic quality estimator calculating Mean Opinion Score (MOS), packet loss concealment artifacts, and jitter.
- **Dependencies:** `scipy`, `librosa`.
- **Security & Privacy:** Low risk (computes aggregate mathematical audio features).
- **Estimated Complexity:** **Medium**
- **Database Migration Required:** Yes (add `mos_score`, `snr_db`, and `clipping_ratio` to `audio_assets`).
- **Provider Cost Impact:** None (100% local mathematical computation).

---

### Direction 8: Configurable BFSI Extraction Schemas (Insurance, Mortgages, KYC)
- **Current Readiness:** High. `calllens/extract.py` provides modular regex parsers.
- **Reusable Modules:** `calllens/extract.py` (`extract_followup_details`).
- **Required Changes:** Move hardcoded extraction rules to external JSON/YAML schema definitions (e.g., `schemas/bfsi_collection.json`, `schemas/kyc_verification.json`). Allow operators to define custom field extractors.
- **Dependencies:** `pydantic` (already installed).
- **Security & Privacy:** Validation against schema injection.
- **Estimated Complexity:** **Medium**
- **Database Migration Required:** Yes (store schema version in `followup_records`).
- **Provider Cost Impact:** None.

---

### Direction 9: Enterprise Human Review Queues & Multi-Operator Audit Trails
- **Current Readiness:** Medium. Follow-up Desk currently implements single-operator review.
- **Reusable Modules:** `calllens/history.py` (`FollowupRecord`, `verification_status`, `confirmed_by`, `operator_notes`).
- **Required Changes:** Add workflow states (`pending_review`, `under_review`, `escalated`, `approved`, `rejected`), assign calls to operator IDs, and implement review queues.
- **Dependencies:** None.
- **Security & Privacy:** Audit logging of who accessed customer financial records.
- **Estimated Complexity:** **Medium**
- **Database Migration Required:** Yes (add `assigned_to`, `reviewed_by`, and `rejection_reason` to `followup_records`).
- **Provider Cost Impact:** None.

---

### Direction 10: Role-Based Access Control (RBAC) & Authentication
- **Current Readiness:** Low. CallLens is currently a local engineering workstation without user authentication.
- **Reusable Modules:** `app/main.py` middleware pipeline.
- **Required Changes:** Add JWT bearer authentication, session cookies, and user roles (`admin`, `qa_auditor`, `call_center_operator`, `read_only_evaluator`).
- **Dependencies:** `python-jose`, `passlib`, `bcrypt`.
- **Security & Privacy:** Essential for production deployment. Prevents unauthorized audio access.
- **Estimated Complexity:** **Medium**
- **Database Migration Required:** Yes (create `users` and `roles` tables).
- **Provider Cost Impact:** None.

---

### Direction 11: Multi-Tenant Tenant Isolation & User Recording History
- **Current Readiness:** Medium. SQLite database currently uses global tables.
- **Reusable Modules:** `calllens/history.py`.
- **Required Changes:** Add `tenant_id` and `user_id` foreign keys to all relational tables. Enforce tenant filtering in all SQLAlchemy queries.
- **Dependencies:** None.
- **Security & Privacy:** Prevents cross-tenant data leaks in SaaS deployments.
- **Estimated Complexity:** **Medium**
- **Database Migration Required:** Yes (add `tenant_id` index across all tables).
- **Provider Cost Impact:** None.

---

### Direction 12: Cloud Object Storage (AWS S3, Google Cloud Storage, Azure Blob)
- **Current Readiness:** Medium. Local file operations are encapsulated in `history.save_audio_asset()`.
- **Reusable Modules:** `calllens/history.py` (`AudioAsset.storage_path`).
- **Required Changes:** Introduce an `AudioStorageBackend` protocol with `LocalDiskStorage` and `S3Storage` implementations. Generate presigned URLs for browser playback.
- **Dependencies:** `boto3` or `google-cloud-storage`.
- **Security & Privacy:** Enable server-side encryption (SSE-KMS) and bucket retention lifecycle policies.
- **Estimated Complexity:** **Medium**
- **Database Migration Required:** No (`storage_path` accommodates `s3://` URIs).
- **Provider Cost Impact:** Standard cloud storage and egress fees ($0.023/GB/month).

---

### Direction 13: Asynchronous Background Processing & Distributed Task Queues
- **Current Readiness:** Medium. Long-running STT/TTS calls currently execute synchronously within async endpoints.
- **Reusable Modules:** `app/main.py`.
- **Required Changes:** Offload audio conversion and batch benchmark runs to Celery or ARQ with Redis/RabbitMQ. Return `202 Accepted` with a task polling URL or WebSocket task completion push.
- **Dependencies:** `redis`, `arq` or `celery`.
- **Security & Privacy:** Secure task message broker credentials.
- **Estimated Complexity:** **High**
- **Database Migration Required:** Yes (add `task_status` and `task_id` tracking).
- **Provider Cost Impact:** None.

---

### Direction 14: Automated Exportable Benchmark Reports (PDF, LaTeX, CSV)
- **Current Readiness:** High. Markdown results and SQLite aggregates already exist.
- **Reusable Modules:** `calllens/benchmark.py`, `calllens/metrics.py`.
- **Required Changes:** Add endpoint `GET /api/benchmark/export?format=pdf` using ReportLab or WeasyPrint to generate publication-ready PDF reports with embedded charts and bootstrap confidence intervals.
- **Dependencies:** `weasyprint` or `reportlab`.
- **Security & Privacy:** Low risk.
- **Estimated Complexity:** **Low**
- **Database Migration Required:** No.
- **Provider Cost Impact:** None.

---

### Direction 15: External CRM & Contact-Centre Telephony Integrations (Twilio, Exotel, Salesforce)
- **Current Readiness:** Low. CallLens does not initiate real outbound PSTN telephone calls.
- **Reusable Modules:** `app/main.py`, `calllens/extract.py`, `calllens/history.py`.
- **Required Changes:** Integrate Twilio or Exotel telephony webhooks (`/telephony/inbound`, `/telephony/status`). Stream audio from telephony bridges into CallLens WebSocket gateway. Push confirmed follow-up reminder tasks into Salesforce/HubSpot via REST API.
- **Dependencies:** `twilio` or `exotel-py`.
- **Security & Privacy:** High risk. Telephony webhooks require signature validation (`X-Twilio-Signature`); customer calls require explicit recording consent announcements under Indian telecommunications regulations.
- **Estimated Complexity:** **High**
- **Database Migration Required:** Yes (add `telephony_call_sid` and `crm_lead_id` to `recording_sessions`).
- **Provider Cost Impact:** Telephony provider trunking rates (₹0.50–₹1.50 per minute).

---

## 3. Extensibility Complexity & Priority Matrix

| Direction | Focus Area | Architectural Readiness | Complexity | Database Migration | Recommended Priority |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **D1: Additional Indic Languages** | Multi-lingual | High | **Low** | No | Immediate (Phase 1) |
| **D8: Configurable BFSI Schemas** | Domain Customization | High | **Medium** | Yes | Immediate (Phase 1) |
| **D14: Exportable Benchmark Reports** | Reporting | High | **Low** | No | Immediate (Phase 1) |
| **D2: Multi-Provider Adapters** | Provider Flexibility | Medium | **Medium** | No | Near-term (Phase 2) |
| **D9: Human Review Queue** | Enterprise Workflow | Medium | **Medium** | Yes | Near-term (Phase 2) |
| **D10: RBAC Authentication** | Enterprise Security | Low | **Medium** | Yes | Near-term (Phase 2) |
| **D12: Cloud Object Storage** | Scalability | Medium | **Medium** | No | Near-term (Phase 2) |
| **D5: Dual-Channel Diarization** | Audio Analytics | Medium | **Medium** | Yes | Long-term (Phase 3) |
| **D6: Emotion/Sentiment Analysis** | AI Enhancement | Medium | **Medium** | Yes | Long-term (Phase 3) |
| **D7: Acoustic MOS Analytics** | Quality Monitoring | High | **Medium** | Yes | Long-term (Phase 3) |
| **D11: Multi-Tenant Architecture** | SaaS Readiness | Medium | **Medium** | Yes | Long-term (Phase 3) |
| **D13: Background Task Queue** | Performance | Medium | **High** | Yes | Long-term (Phase 3) |
| **D4: True Incremental Streaming** | Real-time Speech | Low | **High** | Yes | Dependent on Upstream Provider |
| **D15: Contact Centre Telephony** | External Telecom | Low | **High** | Yes | Dependent on Commercial Trunking |

---

## 4. Architectural Decoupling Recommendations for Future Engineering

If the product transitions into a commercial SaaS platform, the three highest-leverage architectural refactorings are:

1. **Provider Abstraction Layer:** Define a typed `SpeechProviderProtocol` so new speech models (Whisper, Bhashini) can be benchmarked alongside Gnani without editing `app/main.py`.
2. **Audio Storage Protocol:** Abstract disk I/O behind an `AudioStore` interface so local development uses `LocalDiskStore` and production seamlessly swaps to `S3AudioStore` via environment variables.
3. **Background Worker Boundary:** Separate compute-heavy audio degradation and model benchmarking from the FastAPI event loop using Redis-backed background workers.
