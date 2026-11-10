# CallLens — Product Requirements Document (PRD)

**Document ID:** `CL-PRD-001`  
**Version:** 2.0.0  
**Status:** Canonical Reference  
**Last Updated:** November 2026  
**Author:** Technical Ownership & Engineering Governance  

---

## 1. Executive Summary & Problem Statement

Modern speech recognition and synthesis models (ASR and TTS) demonstrate high accuracy under clean, laboratory conditions (wideband 16–48 kHz PCM, low ambient noise, studio microphones). However, when deployed into enterprise production environments—specifically contact center telephony—performance degrades significantly due to acoustic stressors:
1. **Narrowband Bandwidth Limitation:** Legacy PSTN and standard SIP trunks enforce G.712 bandpass filtering (300 Hz – 3,400 Hz), eliminating critical high-frequency formants and sibilants.
2. **Lossy Quantization:** 8-bit companding ($\mu$-law / A-law) induces quantization distortion.
3. **Severe Telephony Noise:** Call centers, vehicular environments, and mobile device mics expose audio streams to low Signal-to-Noise Ratios (SNRs) down to 10 dB and 0 dB.
4. **Sub-optimal Indian Accent Handling:** Indian English and vernacular Indic telephony require domain-specific models tuned to regional phonetic variations and mixed-language switching.

**CallLens** bridges this gap. It serves as both a **forensic stress evaluation benchmark** and an **enterprise-grade speech intelligence application**, providing interactive Speech-to-Text (STT), Text-to-Speech (TTS), real-time streaming audio handling, contact center scenario simulation, and rigorous comparative evaluation between speech AI models.

---

## 2. Target Personas & User Journeys

| Persona | Primary Goal | Critical Features Utilized |
| :--- | :--- | :--- |
| **Enterprise AI Architect** | Evaluate model resilience and choose between ASR engines for contact centers. | Model Comparison, Speech Quality Testing (Stress Lab), Bootstrap CIs, RTF Telemetry. |
| **Contact Center Operations Leader** | Test automated debt collection and reminder voice bot workflows. | Payment Follow-up Assistant, TTS Voice Quality, Indic Voice Talents. |
| **Speech ML Engineer / Researcher** | Forensically inspect failure modes across acoustic degradation stages. | Audio Inspection, G.712/$\mu$-law/SNR Cascade, CER/WER Breakdown, Provenance. |
| **Executive Evaluator / First-time Visitor** | Rapidly understand capabilities without getting overwhelmed by jargon. | Overview page, plain-language walkthrough, interactive demo clips, How It Works. |

---

## 3. Product Architecture & Navigation Hierarchy

The application interface is structured into ten unified views accessible via the primary navigation bar:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                             CallLens Navigation                              │
├────────────────────────────────┬─────────────────────────────────────────────┤
│ 1. Overview                    │ Plain-language platform introduction & stats│
│ 2. Record & Transcribe         │ Dual-mode STT (telephony clips & live mic)  │
│ 3. Convert Text to Speech      │ Multi-language TTS with 7 Indic voices      │
│ 4. Live Speech Playground      │ Real-time streaming audio pipeline (WS)     │
│ 5. Payment Follow-up Assistant │ Debt recovery & EMI reminder bot simulator  │
│ 6. Compare AI Models           │ Head-to-head Prisma v2.5 vs v3.0 benchmark  │
│ 7. Speech Quality Testing      │ Acoustic degradation laboratory (Stress Lab)│
│ 8. My Recordings               │ Historical audit log, playback, CSV export  │
│ 9. System Health               │ Storage diagnostics, rate limits, telemetry │
│ 10. How It Works               │ Mathematical & acoustic methodology guide   │
└────────────────────────────────┴─────────────────────────────────────────────┘
```

---

## 4. Detailed Functional Requirements

### 4.1. View 1: Overview
- **PR-OV-01 (Value Proposition):** Must present a clear, non-technical explanation of CallLens, emphasizing why clean-audio evaluations fail to predict real-world telephony behavior.
- **PR-OV-02 (Degradation Cascade Summary):** Visual summary of the 4-stage degradation pipeline (Clean $\to$ Telephone Bandwidth $\to$ +10 dB SNR $\to$ +0 dB SNR).
- **PR-OV-03 (Telemetry Stat Counters):** Display aggregate platform metrics:
  - Benchmark sample count (360 verified historical evaluations).
  - Production model versions under evaluation (Prisma v2.5 and v3.0).
  - Verified benchmark conditions (4 distinct acoustic environments).
  - Curated Indic voice talents available (7 voices).
- **PR-OV-04 (Quick-Start Navigation):** Direct action buttons leading to STT, TTS, and Model Comparison views.

### 4.2. View 2: Record & Transcribe (Speech-to-Text Studio)
- **PR-STT-01 (Dual Input Modality):**
  - *Clip Mode:* Select from 6 pre-recorded standard telephony benchmark clips (`call_center_hindi_01.wav`, `banking_ivr_english_02.wav`, etc.).
  - *Microphone Mode:* Browser-based recording using MediaRecorder API with live visual recording indicator.
- **PR-STT-02 (Model Selection):** Toggle between Gnani Prisma v2.5 and Gnani Prisma v3.0.
- **PR-STT-03 (Language Support):** Select language context (`en-IN` for Indian English, `hi-IN` for Hindi).
- **PR-STT-04 (Execution & Telemetry):**
  - Display full transcript with visual copy-to-clipboard button.
  - Return performance metrics: Audio duration (seconds), processing wall-clock time (seconds), Real-Time Factor ($RTF = \frac{\text{latency}}{\text{duration}}$), and detected word count.
- **PR-STT-05 (Resilience & Contract Redundancy):** Frontend must handle both `audio_duration_sec` and `duration_sec` without throwing `undefined.toFixed()` errors.

### 4.3. View 3: Convert Text to Speech (TTS Studio)
- **PR-TTS-01 (Text Input):** Multi-line text entry with character counter, max length validation, and preset prompt templates (IVR Greeting, EMI Reminder, Flight Alert).
- **PR-TTS-02 (Curated Voice Catalog):** Support 7 Indic voice talents across genders and styles:
  - `Pranav` (Indian English - Corporate / Professional Male)
  - `Priya` (Indian English - Warm / Conversational Female)
  - `Neerja` (Hindi / Hinglish - Customer Support Female)
  - `Aditi` (Indian English - Expressive Female)
  - `Rohan` (Indian English - Energetic Male)
  - `Kavya` (Hindi - Friendly Female)
  - `Suresh` (Indian English - Authoritative Male)
- **PR-TTS-03 (Perimeter Normalization):** Backend must normalize case variations (e.g., lowercase `pranav` $\to$ capitalized `Pranav`) before passing to synthesis engine.
- **PR-TTS-04 (Audio Playback & Waveform):** In-browser audio player with play/pause, seek bar, time display, and auto-play toggle.
- **PR-TTS-05 (Performance Metrics):** Display synthesis latency, generated audio duration, character count, and RTF.

### 4.4. View 4: Live Speech Playground
- **PR-LIVE-01 (Real-Time Bidirectional Streaming):** Dedicated WebSocket connection (`/ws/speech`) supporting chunked audio ingestion and immediate status feedback.
- **PR-LIVE-02 (State Machine & Signaling):** Support structured JSON control signals:
  - `start`: Initialize session with model, language, and sampling configuration.
  - `audio_chunk`: Base64-encoded PCM/WAV audio frames.
  - `finish_recording` / `stop`: Finalize session, commit audio to storage, and trigger final ASR transcription.
- **PR-LIVE-03 (Dual Channel Visualization):** Real-time visual feedback for uplink transmission and server acknowledgment.

### 4.5. View 5: Payment Follow-up Assistant
- **PR-FLW-01 (Domain Simulation):** Pre-configured banking and loan collection dialogue scenarios:
  - *Scenario A: Standard EMI Reminder* (Graceful payment reminder for upcoming due date).
  - *Scenario B: Overdue Loan Escalation* (Firm yet compliant collection notice for 30-day delinquency).
  - *Scenario C: Broken Promise Follow-up* (Addressing breached payment commitments).
- **PR-FLW-02 (Dynamic Voice Synthesis):** Integrated TTS synthesis using curated voices (`Pranav`, `Priya`, `Neerja`) to preview outbound agent speech.
- **PR-FLW-03 (Response Analysis & Intent Extraction):** Analyze simulated debtor responses for payment intent (Commitment, Dispute, Hardship, Refusal) with confidence scoring.

### 4.6. View 6: Compare AI Models
- **PR-CMP-01 (Side-by-Side Benchmark Matrix):** Compare Prisma v2.5 vs Prisma v3.0 across all 4 benchmark conditions:
  - Clean PCM (Baseline)
  - PSTN Bandwidth (G.712 filter: 300–3,400 Hz)
  - Telephony + 10 dB SNR (Moderate ambient noise)
  - Telephony + 0 dB SNR (Extreme ambient noise)
- **PR-CMP-02 (Key Metrics Display):**
  - Word Error Rate ($WER \pm 95\% \text{ CI}$)
  - Character Error Rate ($CER$)
  - Word Accuracy ($WAcc = 100\% - WER$)
  - Relative degradation percentage ($\Delta WER$)
- **PR-CMP-03 (Statistical Rigor):** 1,000-resample non-parametric bootstrap confidence intervals to ensure observed differences are statistically significant.

### 4.7. View 7: Speech Quality Testing (Stress Lab)
- **PR-LAB-01 (Interactive Degradation Lab):** Allow users to apply custom degradation chains to any sample clip:
  - G.712 bandpass filter toggle.
  - $\mu$-law companding toggle.
  - Gaussian noise injection slider ($0\text{ dB}$ to $30\text{ dB}$ SNR).
  - Packet loss simulation toggle.
- **PR-LAB-02 (A/B Audio Audition):** Dual audio player allowing immediate listening comparison between original pristine audio and degraded telephony audio.
- **PR-LAB-03 (On-Demand Evaluation):** Run real-time transcription on degraded audio to observe instantaneous recognition degradation.

### 4.8. View 8: My Recordings (Audit Log & Asset Manager)
- **PR-REC-01 (Session History Table):** Chronological log of all STT and TTS operations with columns:
  - Timestamp, Operation Type (STT / TTS), Session ID, Model / Voice, Audio Duration, Latency, and Status.
- **PR-REC-02 (Inline Audio Playback):** Dedicated `▶ Play` button in every row with inline playback trigger.
- **PR-REC-03 (Transcript & Text Inspection):** Collapsible modal/viewer showing full input/output text and raw JSON telemetry.
- **PR-REC-04 (CSV Export):** One-click download of session audit log formatted for analytical review.
- **PR-REC-05 (Atomic Cascading Deletion):** Deleting a session must remove database rows in SQLite and physically delete `.wav` audio files on disk.

### 4.9. View 9: System Health & Diagnostics
- **PR-SYS-01 (Storage Diagnostics):** Display live folder statistics:
  - Recordings directory: file count, total size on disk (MB), path verification.
  - TTS audio directory: file count, total size on disk (MB), path verification.
  - Temp directory: clean status.
- **PR-SYS-02 (Provider Integration Status):** Real-time connectivity check, mock vs live indicator (`ALLOW_LIVE_API`), active rate-limiter capacity, and file lock status.
- **PR-SYS-03 (Asset Integrity Checker):** Diagnostic verification confirming zero orphaned records (database entry without disk file) and zero orphaned files (disk file without database entry).

### 4.10. View 10: How It Works (Methodology)
- **PR-HOW-01 (Mathematical Formulations):** Comprehensive exposition of evaluation metrics:
  - Levenshtein-based WER and CER formulas.
  - G.712 8th-order Butterworth digital filter transfer functions.
  - $\mu$-law companding formula ($y = \text{sgn}(x) \frac{\ln(1 + \mu |x|)}{\ln(1 + \mu)}$ with $\mu=255$).
  - 1,000-resample non-parametric bootstrap confidence interval estimation.
- **PR-HOW-02 (Acoustic Telephony Context):** Technical explanation of formants, spectral truncation, and noise mask effects on acoustic phoneme decoders.

---

## 5. Non-Functional Requirements (NFRs)

### 5.1. Performance & Latency
- **NFR-PERF-01:** Batch STT and TTS API endpoints must respond with $RTF < 0.60$ under mock mode and $RTF < 1.20$ under live provider mode.
- **NFR-PERF-02:** Database queries on SQLite must execute in $< 50\text{ ms}$ for history pagination (index on `created_at` and `session_id`).
- **NFR-PERF-03:** Frontend asset loading must require zero build tools (no Webpack/Vite bundle step); static assets must load cleanly in modern evergreen browsers.

### 5.2. Reliability, Fail-Closed Safety & Concurrency
- **NFR-SAFE-01 (Credit Protection):** The platform MUST enforce a strict fail-closed policy (`ALLOW_LIVE_API=0` by default). Live network calls to external APIs are prohibited unless explicitly overridden in environment configuration.
- **NFR-SAFE-02 (File Lock Protection):** Live benchmark executions must be gated by a mandatory file-based lock (`call_accounting.lock`) limiting lifetime network attempts to 434 calls.
- **NFR-SAFE-03 (Token-Bucket Limiting):** External requests must be constrained by an internal token-bucket rate limiter (5 requests/sec burst, 2 sustained) to avoid provider rate limiting.

### 5.3. Data Integrity & Persistence
- **NFR-DATA-01:** Historical benchmark data (`benchmark_results` table, 360 records) is immutable. No application feature or cleanup task may modify or delete historical benchmark entries.
- **NFR-DATA-02:** User recording sessions, transcripts, and generated TTS audio must survive server reboots and restart cycles (stored on persistent file system with SQLite metadata).
- **NFR-DATA-03:** Deletion operations must be atomic and cascading: SQLite row deletion and physical file deletion must occur synchronously or log explicit rollback.

### 5.4. Verification & Testing Standards
- **NFR-TEST-01:** Full automated test suite must maintain 100% pass rate across all test modules with zero skipped tests.
- **NFR-TEST-02:** End-to-end browser automation (CDP/Puppeteer) must verify UI elements, DOM rendering, audio player controls, and table populating with zero uncaught JavaScript console errors.

