# CallLens — Project Vision & Core Principles

**Document Classification:** Strategic Architecture & Product Mission  
**Last Updated:** November 10, 2026  
**Status:** Canonical Reference  

---

## 1. Product Identity & Purpose

**CallLens** is a unified Indic Speech Intelligence and Telephony Evaluation Platform designed to bridge the severe chasm between laboratory Automatic Speech Recognition (ASR) performance and real-world Indian telephony acoustics.

Built originally for *The Great Indian Internship Challenge by Gnani.ai*, CallLens has grown into a production-grade speech workstation that combines:
1. **Empirical Telephony Benchmarking:** Quantifying acoustic degradation under ITU-T G.712 telephony channel constraints (300–3400 Hz bandpass, G.711 $\mu$-law companding, and noise injection) comparing **Gnani Prisma v2.5** and **Prisma v3.0**.
2. **Interactive Speech Engineering Workstation:** A full-featured speech suite offering Speech-to-Text (STT), Text-to-Speech (TTS), Live Microphone Recording, and an Operator-Assisted Banking Follow-up Desk.
3. **Enterprise Reliability & Observability:** Safe-by-default execution (`ALLOW_LIVE_API=0`), persistent SQLite call metadata and audio storage, cross-process network attempt caps, and comprehensive storage diagnostics.

---

## 2. The Core Problem: Telephony Acoustic Fragility

Enterprise voice systems in India routinely experience catastrophic performance degradation when deploying speech models trained on clean public datasets (e.g., FLEURS read speech) onto public switched telephone networks (PSTN) and mobile cellular networks.

```
+----------------------------------------------------------------------------------------------------+
|                               THE TELEPHONY DEGRADATION CASCADE                                   |
+----------------------------------------------------------------------------------------------------+
|  Studio Read Audio (16 kHz)  ──>  Bandpass Filter (300–3400 Hz)  ──>  Downsampling (8 kHz)         |
|  [Frequencies up to 8 kHz]        [High-frequency sibilants lost]      [Nyquist cutoff at 4 kHz]   |
|                                                                                │                   |
|  Corrupted Transcription     <──  Acoustic Noise (Traffic/Jitter) <──  G.711 μ-law Companding     |
|  [Amounts/Dates misheard]         [0 dB to 10 dB SNR Gaussian]         [Non-linear 8-bit dynamic]  |
+----------------------------------------------------------------------------------------------------+
```

### Critical Domain Vulnerability: BFSI (Banking & Finance)
In high-stakes debt collection, loan origination, and customer service calls:
- Phonetic erosion of numerals directly corrupts outstanding debt amounts and promise-to-pay dates.
- A model with an acceptable general Word Error Rate (WER) can still fail completely in business utility if it misidentifies `₹50,000` as `₹15,000` or `15 तारीख` as `5 तारीख`.
- CallLens was created to provide deterministic, reproducible measurements of this degradation and to evaluate human-in-the-loop safeguards.

---

## 3. Product Principles

### I. Architectural Honesty
- We never simulate streaming by chopping text with artificial delays if the provider is batch-based.
- Gnani Prisma STT operates via atomic HTTP REST; our Live Playground truthfully buffers audio packets over WebSockets and submits an atomic batch, reporting actual lifecycle timings.
- Synthetic mock fixtures and recorded live provider results are isolated by database-level provenance tags (`provenance = 'live'` vs `'mock'`).

### II. Safe-by-Default Execution
- All platform workflows run out-of-the-box in offline/cached-replay mode (`ALLOW_LIVE_API=0`).
- No test, build script, or demonstration can silently drain live cloud provider credits.
- A persistent cross-process file-locked counter enforces an immovable ceiling of 434 cumulative network attempts.

### III. Human-in-the-Loop AI Oversight
- Autonomous decision-making in sensitive domains (like debt collection) is fundamentally hazardous.
- The CallLens Follow-up Desk extracts commitments from transcripts but strictly flags missing or ambiguous data for human operator verification before any reminder voice call can be synthesized.

### IV. Durable Physical Persistence
- Audio recordings, transcripts, and operational records are not ephemeral memory objects.
- All assets are persisted to relational SQLite tables and local disk storage outside Git (`calllens-data/`), indexed with SHA-256 checksums and collision-resistant UUIDs that survive application restarts.

---

## 4. Target Personas

| Persona | Primary Workflow | Key Product Value |
| :--- | :--- | :--- |
| **Speech AI Engineers** | Telephony Stress Lab & Model Comparison | Empirical WER/CER metrics under calibrated ITU-T G.712 degradation, 1,000-resample bootstrap confidence intervals. |
| **BFSI Operations Leads** | Payment Follow-up Assistant | Structured commitment extraction with human audit gates and courteous Indic voice reminders. |
| **Voice Application Developers** | STT Studio & TTS Studio | Multi-format transcription, 10 Indic languages, 7 curated Timbre voices, dynamic speaking rates, and WAV downloads. |
| **Technical Evaluators & Judges** | System Health & Overview Dashboard | Transparent observability, zero-credit offline replay, 143 passing regression tests, and full architectural clarity. |

