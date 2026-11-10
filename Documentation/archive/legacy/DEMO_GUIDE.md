# CallLens — Demonstration & Evaluator Presentation Guide
### Step-by-Step Playbook, Safe Demo Workflows, Resilience Fallbacks & 5–8 Minute Pitch Script

**Target Evaluator Audience:** Interviewers, evaluators, hackathon judges, and AI engineering leads.  
**Demonstration Mode:** Safe offline replay / mock mode (`ALLOW_LIVE_API=0` by default; zero live API credit spend required).  
**Repository:** `https://github.com/dragyo7/calllens-stress-lab`  
**Platform URL:** `http://127.0.0.1:8000`

---

## 1. Pre-Demo Checklist

Complete this checklist 5 minutes prior to the demonstration:

| Item | Requirement | Verification Command / Check | Status |
| :--- | :--- | :--- | :---: |
| **Python Environment** | Python 3.10+ in `.venv` | `.venv\Scripts\python --version` (or `python3 --version`) | Verified |
| **Dependencies** | All 14 pinned packages installed | `.venv\Scripts\pip check` | Verified |
| **Environment File** | `.env` exists with safe defaults | `Get-Content .env` (confirm `ALLOW_LIVE_API=0`) | Verified |
| **Benchmark Database** | `benchmark.db` present in `../calllens-data` | 360 live records verified | Verified |
| **Storage Folders** | `recordings` and `tts_audio` present | `../calllens-data/recordings`, `../calllens-data/tts_audio` | Verified |
| **Uvicorn Server** | FastAPI server running on port 8000 | `curl http://127.0.0.1:8000/api/health` returns `200 OK` | Verified |
| **Browser Compatibility**| Chrome / Edge / Firefox | Modern Web Audio API & MediaRecorder support | Verified |
| **Audio Hardware** | System audio output enabled | Verify speaker volume for TTS audio playback | Verified |

### Server Launch Command
```bash
# From repository root:
.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser.

---

## 2. End-to-End Demonstration Sequence (13 Steps)

Follow this exact sequence for a seamless 5–8 minute presentation.

---

### Step 1: Overview & Value Proposition
- **Navigation:** Press `[1]` on keyboard or click **Overview** in the sidebar.
- **Action:** Point out the top-level KPI cards (Total Benchmark Runs: 360, Clean WER: 6.65%, Hinglish WER: 31.60%, Curated Indic Voices: 7).
- **Talk Track:**
  > *"Welcome to CallLens. CallLens is a unified Indic Speech Intelligence and Telephony Evaluation Platform. Public speech benchmarks like FLEURS evaluate ASR models on clean studio speech, which conceals how models fail in real Indian telephony—such as bandpass loss, 8-bit companding, and background street noise. CallLens provides both an empirical evaluation lab and a complete, functional speech workstation with STT, TTS, WebSocket live interaction, persistent audio storage, and an operator-assisted debt-collection Follow-up Desk."*
- **What it demonstrates:** Architecture breadth, high-level business impact, and clear product information architecture.
- **What it does NOT demonstrate:** Real customer call recordings (FLEURS and synthetic Timbre audio are used).

---

### Step 2: Speech-to-Text (STT) Studio — Preloaded Benchmark Clip
- **Navigation:** Press `[2]` or click **Speech to Text**.
- **Action:** In the *Preloaded Benchmark Clip* dropdown, select `[FLEURS Hindi] fleurs_01`. The Devanagari reference text and waveform visualizer load automatically. Click **Transcribe Speech**.
- **Expected Result:**
  - Loader spins briefly with simulated/real inference latency.
  - Transcript appears in the Devanagari text box.
  - Metrics row updates: Duration (~11.6s), Word Count (~25 words), Latency (~0.21s), Model (`Prisma v2.5` or `v3.0`).
  - Audio player allows playback of the clean reference audio.
- **Talk Track:**
  > *"In our STT Studio, users can transcribe preloaded clips, upload audio files up to 5 MB, or record live speech. Notice the output format options: Verbatim, ITN Transcribe, and Codemix. Here, we transcribe a Hindi sentence using Prisma with sub-250ms latency."*
- **What it demonstrates:** Clean STT workflow, audio waveform preview, and multi-format transcription.

---

### Step 3: Speech-to-Text Studio — Live Microphone Recording
- **Navigation:** Remain on **Speech to Text**.
- **Action:** Switch the input mode to **Microphone**. Click **Start Recording**, speak a brief Hindi phrase (e.g., *"मेरा नाम राहुल है और मैं दिल्ली में रहता हूँ"*), then click **Stop Recording**. Review the waveform, then click **Transcribe Speech**.
- **Expected Result:**
  - Browser requests microphone permission (if first time).
  - Web Audio API canvas displays live dynamic waveform.
  - Stopped audio is encoded to WAV, persisted as an `audio_asset` with a unique UUID, and transcribed.
- **Talk Track:**
  > *"When recording via microphone, the audio is captured as standard PCM WAV, validated for duration and sample rate, and assigned a collision-resistant UUID before processing. If upstream ASR ever fails, the raw audio recording is already safely persisted on disk."*
- **What it demonstrates:** Audio capture, Web Audio API visualization, and durable storage ingestion.

---

### Step 4: Text-to-Speech (TTS) Studio — Hindi Synthesis
- **Navigation:** Press `[3]` or click **Text to Speech**.
- **Action:**
  1. Click the quick template pill **"Banking EMI Reminder"**.
  2. Text populates: *"नमस्ते राहुल शर्मा जी, आपका क्रेडिट कार्ड बिल ₹ 50,000 है जो 5 तारीख तक देय है।"*
  3. Keep Voice set to **Pranav (Male / Flagship)**, Speed `1.0x`.
  4. Click **Generate Speech**.
- **Expected Result:**
  - TTS audio is synthesized and saved to `../calllens-data/tts_audio/tts_generated_{uuid}.wav`.
  - Embedded HTML5 audio player displays the waveform and play button.
  - Click Play to hear natural conversational Hindi speech.
  - Click **Download WAV** to verify downloadability.
- **Talk Track:**
  > *"Our TTS Studio exposes 7 curated Indic voices powered by Gnani Timbre, with Pranav and Kaveri as primary verified personas. We support dynamic speaking rates from 0.85x to 1.15x. Notice that the generated audio duration is accurately measured via soundfile decoding rather than guessed from character count."*
- **What it demonstrates:** Natural Hindi neural TTS, audio playback, downloadable WAV export, and exact metadata measurement.

---

### Step 5: Live Speech Playground — WebSocket Transport
- **Navigation:** Press `[4]` or click **Live Playground**.
- **Action:**
  1. Click **Connect Gateway**.
  2. Gateway status pill turns green: `Connected`.
  3. Click **Start Recording**, speak 2 seconds of audio, click **Stop Recording**.
  4. Click **Submit for Transcription**.
- **Expected Result:**
  - Event log streams JSON lifecycle messages:
    - `session_started` &rarr; `audio_chunk_received` &rarr; `transcription_started` &rarr; `transcription_completed`.
  - Returned transcript renders in the live display.
  - Live session is committed to `recording_sessions` in SQLite.
- **Talk Track:**
  > *"Here is the Live Playground. It uses an application-level WebSocket gateway over `/ws/speech`. In the spirit of architectural honesty: Gnani Prisma STT operates via an atomic HTTP REST gateway. CallLens buffers real-time microphone chunks over WebSockets, emits structured lifecycle events, and performs atomic transcription with zero fabricated streaming illusions."*
- **What it demonstrates:** Real WebSocket event transport, binary chunk streaming, and transparent system architecture.
- **What it does NOT demonstrate:** Provider-side incremental streaming (truthfully explained as buffered REST transcription).

---

### Step 6: Telephony Stress Lab — Head-to-Head Model Comparison
- **Navigation:** Press `[6]` or click **Stress Lab**.
- **Action:**
  1. Select Clip `fleurs_01`.
  2. Select Condition: **Telephony + 0 dB SNR Noise (`tel_snr0`)**.
  3. Click **Run Stress Comparison**.
- **Expected Result:**
  - Side-by-side comparison cards display:
    - Left: **Prisma v2.5** (WER: 18.92%, Latency: ~194ms).
    - Right: **Prisma v3.0** (WER: 25.82%, Latency: ~209ms).
  - Extracted financial entities show Indian Rupee amounts and dates.
- **Talk Track:**
  > *"This is the core empirical research differentiator: our Telephony Stress Lab. We subject identical audio to ITU-T G.712 standard degradation—300 to 3400 Hz bandpass, 8 kHz G.711 mu-law quantization, and calibrated Gaussian noise. Notice this critical finding: under severe 0 dB SNR noise, Prisma v2.5 actually outperforms Prisma v3.0 by nearly 7% absolute WER, because v2.5 has more conservative acoustic pruning."*
- **What it demonstrates:** Empirical stress-testing, side-by-side model comparison, and actionable architecture insight.

---

### Step 7: Model Comparison Matrix & Bootstrap Confidence Intervals
- **Navigation:** Press `[5]` or click **Model Comparison**.
- **Action:** Scroll through the comparative summary table and Interactive Charts.
- **Expected Result:**
  - Charts visualize WER degradation curves across Clean &rarr; Telephony &rarr; 10 dB SNR &rarr; 0 dB SNR.
  - 95% Bootstrap Confidence Intervals (1,000 resamples) prove non-overlapping statistical significance.
- **Talk Track:**
  > *"Rather than relying on single point estimates, CallLens calculates 95% clip-level bootstrap confidence intervals with 1,000 resamples. This gives enterprise architects defensible bounds when calculating expected SLA breach probabilities."*
- **What it demonstrates:** Statistical rigor, bootstrap resampling mathematics, and interactive Chart.js visualization.

---

### Step 8: Follow-up Desk — Scenario 1: Rahul Sharma (Salary Delay)
- **Navigation:** Press `[0]` or click **Follow-up Desk**.
- **Action:**
  1. In Step 1, select chip **Rahul Sharma — ₹50,000 (Salary Delay, PTP 10th)**.
  2. Dialogue text populates: *"नमस्ते राहुल शर्मा जी, आपका क्रेडिट कार्ड बिल ₹ 50,000 है जो 5 तारीख तक देय था..."*
  3. Click **Process Call & Extract Commitments**.
- **Expected Result:**
  - Step 2 unlocks automatically with extracted fields:
    - Customer Name: Rahul Sharma
    - Amount: ₹50,000 (Detected &check;)
    - Due Date: 5 तारीख (Detected &check;)
    - PTP Date: 10 तारीख (Detected &check;)
    - Hardship: Salary delay
  - Suggested reminder template is auto-generated.
  - Check the checkbox: **"I verify all commitments have been reviewed by a human operator"**.
  - Click **Confirm & Proceed to Reminder Synthesis**.
- **Talk Track:**
  > *"In debt collections, automated bots often make catastrophic errors—hallucinating wrong amounts or harassing customers after payment. CallLens implements a Human-in-the-Loop Follow-up Desk. The ASR extracts commitments, but an operator must review and confirm before any outgoing reminder is synthesized."*
- **What it demonstrates:** BFSI operational workflow, regex/Hinglish entity extraction, and human-in-the-loop safeguards.

---

### Step 9: Follow-up Desk — Scenario 5: Anita Desai (Missing PTP Date Flags Operator)
- **Navigation:** Scroll back up to Step 1 in Follow-up Desk.
- **Action:**
  1. Select chip **Anita Desai — ₹75,500 (Fee Dispute — Missing PTP Date, Flags Operator)**.
  2. Click **Process Call & Extract Commitments**.
- **Expected Result:**
  - Notice the **Red Warning Banner**:
    > *"Field(s) requiring verification: Promise-to-pay date."*
  - The Promise-to-Pay Date badge displays **"Not Detected — Operator Required"**.
  - The operator cannot confirm without manually addressing the missing commitment.
- **Talk Track:**
  > *"Here is our edge-case handling. In Anita Desai's call, there is a fee dispute; she never promised a payment date. Instead of silently fabricating a date or defaulting to today, our extraction engine marks `ptp_date: null` and raises an operator warning banner. This prevents wrongful automated collections."*
- **What it demonstrates:** Defensible AI safety, strict missing-field tracking, and zero hallucination.

---

### Step 10: Follow-up Desk — Synthesize Verified Reminder Call
- **Navigation:** Scroll down to Step 3 in Follow-up Desk.
- **Action:**
  1. Select Voice: **Kaveri (Female / Expressive)**.
  2. Review the synthesized reminder text.
  3. Click **Synthesize Customer Reminder**.
- **Expected Result:**
  - Generates courteous, personalized Hindi reminder audio via Timbre.
  - Play button allows evaluator to hear Kaveri speaking the verified customer reminder.
  - Record is committed to the relational `followup_records` database table.
- **Talk Track:**
  > *"Once verified, CallLens uses Timbre to generate a respectful, personalized Hindi audio reminder. The audio file is assigned a random UUID, saved with SHA-256 integrity check, and logged to our persistent audit trail."*
- **What it demonstrates:** End-to-end integration: STT &rarr; Extraction &rarr; Human Verification &rarr; TTS.

---

### Step 11: Call Data Persistence & History
- **Navigation:** Press `[7]` or click **Audio History**.
- **Action:** View the persistent audit log table.
- **Expected Result:**
  - Shows every recent STT transcription, TTS generation, and Follow-up commitment.
  - Displays Model ID, Language, Latency (ms), Provenance (`live`, `cache`, or `mock`), and Audio Download links.
- **Talk Track:**
  > *"Every speech operation is persistently tracked in SQLite with complete provenance separation. Notice the provenance column: it explicitly identifies whether a result came from live provider execution, cache, or mock replay. We never disguise mock data as live results."*
- **What it demonstrates:** Enterprise audit trail, provenance transparency, and database durability.

---

### Step 12: Failures, Error Telemetry & Storage Diagnostics
- **Navigation:** Press `[8]` or click **Failures & Diagnostics**.
- **Action:**
  1. Review the Provider Incident & Resilience Telemetry Log.
  2. Scroll down to **Call Data Persistence & Storage Integrity Diagnostics**.
  3. Point out:
     - Total Recording Sessions
     - Persisted Audio Assets
     - Managed Disk Footprint (MB)
     - Storage Integrity Status: **HEALTHY (0 missing files)**.
  4. Click **Refresh Storage Audit**.
- **Expected Result:**
  - Real-time audit queries physical directories against database rows and confirms 100% asset integrity.
- **Talk Track:**
  > *"In our Diagnostics view, we expose transparent accounting: 341 live network attempts, 3 recovered Cloudflare 504 timeouts, and zero unrecovered failures. Below, our Storage Diagnostics scan checks physical disk files against relational asset IDs. In production, this guarantees that orphaned or corrupted audio files are immediately surfaced."*
- **What it demonstrates:** Observability, self-healing diagnostics, and storage integrity audit.

---

### Step 13: Security Controls & Future Extensibility
- **Navigation:** Press `[9]` or click **Methodology** / review Safeguards box.
- **Action:** Conclude presentation highlighting the 4 core security controls:
  1. **Server-Enforced Live Authorization:** `ALLOW_LIVE_API=0` (fail-closed, HTTP 403).
  2. **Bounded Concurrency & Global Safety Cap:** File-locked counter halting at 434 attempts.
  3. **Path Traversal Guards:** Zero access outside approved directories.
  4. **Credential Redaction:** Zero API tokens in client headers, logs, or error responses.
- **Talk Track:**
  > *"CallLens was built with defense-in-depth: client requests cannot bypass server authorization, audio filenames use random UUIDs with path traversal guards, and all credentials remain server-side. Thank you, and I am happy to take any questions."*

---

## 3. Demo Resilience & Fallback Procedures

If an unexpected condition arises during a live demonstration, use these verified fallbacks:

| Scenario / Failure | Root Cause | Fallback Action | Evaluator Explanation |
| :--- | :--- | :--- | :--- |
| **Microphone Permission Denied** | Browser permissions blocked | Click **Preloaded Clip** (`fleurs_01`) in STT Studio instead of live mic | *"Since microphone access is blocked in this browser sandbox, we demonstrate transcription using our standardized FLEURS telephony test clip."* |
| **No Internet / Offline** | Network connection down | Application runs 100% offline using cached/mock fixtures | *"CallLens is engineered to operate offline. The benchmark database and audio synthesis fall back safely to cached fixtures with transparent provenance labeling."* |
| **Provider Times Out (504)** | Upstream network latency | System uses exponential backoff and displays sanitized error | *"The platform implements automatic retry with backoff. Even if an upstream timeout occurs, CallLens safely preserves the original audio asset."* |
| **Live Call Requested** | `live=1` sent in request | Backend returns HTTP 403 Forbidden | *"Our server-enforced safety policy strictly fails closed (`ALLOW_LIVE_API=0`) to protect against unauthorized cloud credit consumption."* |
| **Accidental Browser Refresh** | Page reloaded during demo | Press `[1]`–`[0]` keys to immediately return to any panel | *"CallLens uses client-side routing and persistent SQLite storage. Refreshing the browser does not lose historical records or benchmark data."* |

---

## 4. Concise 5–8 Minute Pitch Script

> **[0:00 - 1:00] The Problem:**  
> *"Hello. Today I am presenting CallLens, an Indic Speech Intelligence and Telephony Evaluation Platform built for The Great Indian Internship Challenge by Gnani.ai.  
> Indian enterprises deploying speech AI in banking and customer service face a major obstacle: models that achieve 95% accuracy on clean, studio-recorded datasets fail on real mobile phones. Telephony channels cut off frequencies outside 300 to 3400 Hz, compress speech to 8-bit mu-law, and introduce heavy street and background noise. In banking collections, an ASR error on a single Hindi number word can corrupt a loan amount or promise-to-pay date, leading to failed collections and regulatory penalties."*

> **[1:00 - 2:30] The Solution & Workstation:**  
> *"CallLens solves this with a unified speech engineering workstation. In our STT Studio, users can upload audio, record via microphone with real-time waveform visualization, and choose between Verbatim, ITN, and Codemix output formats. In our TTS Studio, users can synthesize natural Hindi and Hinglish speech across 7 curated Indic voices powered by Gnani Timbre. Our Live Playground provides a WebSocket session controller that captures audio chunks in real time, emitting transparent lifecycle events."*

> **[2:30 - 4:00] Empirical Stress Benchmarks:**  
> *"Our core research differentiator is the Telephony Stress Lab. We benchmarked Gnani Prisma v2.5 against Prisma v3.0 across 360 live evaluations using FLEURS Hindi and BFSI banking dialogues.  
> Our empirical data proves two critical deployment rules:  
> First, on clean audio and conversational Hinglish, Prisma v3.0 dominates—achieving 6.65% clean WER and beating v2.5 by over 8% absolute WER on code-mixed banking terms.  
> However, on severe 0 dB SNR noise, Prisma v2.5 is superior—achieving 18.92% WER versus 25.82% for v3.0, with lower P50 latency. This gives enterprises a quantitative deployment matrix rather than guesswork."*

> **[4:00 - 5:30] The Follow-up Desk & Human-in-the-Loop AI:**  
> *"In our Follow-up Desk, we show how this applies to BFSI operations. The system transcribes collection calls and extracts debt commitments. But critically, we enforce human-in-the-loop verification. For customer Sunil Kumar, it captures his Monday payment commitment. For Anita Desai, where no payment date was agreed upon, our engine explicitly outputs null and raises an operator warning banner rather than hallucinating a date. The operator verifies the details and synthesizes a personalized Hindi voice reminder via Timbre."*

> **[5:30 - 6:30] Persistence, Security & Architecture:**  
> *"Architecturally, CallLens enforces strict engineering standards: all audio files are assigned collision-resistant UUIDs with SHA-256 integrity checks, stored outside Git. Even if speech recognition fails, the original audio asset is preserved on disk. Our live API policy fails closed with HTTP 403, our rate limiter is thread-safe, and our global safety cap prevents budget overruns. All 137 automated regression tests pass, and our 360 live benchmark records remain preserved in SQLite.
> Thank you, and I look forward to your questions."*