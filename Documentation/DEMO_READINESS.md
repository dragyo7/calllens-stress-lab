# CallLens — Demonstration Playbook & Evaluator Guide

**Document ID:** `CL-DEMO-001`  
**Version:** 2.0.0  
**Status:** Canonical Reference  
**Last Updated:** November 2026  
**Author:** Technical Ownership & Engineering Governance  

---

## 1. Demonstration Philosophy & Objectives

CallLens is designed to demonstrate that **standard clean-audio benchmarks are fundamentally flawed for predicting real-world contact center telephony performance**. 

During an evaluator or executive demonstration, your primary goals are:
1. **Highlight the Core Insight:** Show that newer models (Prisma v3.0) outperform older models in clean audio, but suffer dramatic degradation under severe acoustic noise (0 dB SNR) where older models (Prisma v2.5) demonstrate superior acoustic robustness.
2. **Demonstrate Real Multi-Modal AI:** Showcase interactive Speech-to-Text, multi-voice Text-to-Speech synthesis, and domain-specific dialogue simulation.
3. **Establish Engineering Rigor:** Prove that every figure is backed by forensic data, 1,000-resample bootstrap confidence intervals, and zero-credit safety guardrails.

---

## 2. Pre-Flight Verification Checklist

Before initiating a live presentation or evaluator walkthrough:

```
[ ] 1. Backend Server Daemon Active:
       Uvicorn running on http://127.0.0.1:8000
       Verify via browser: http://127.0.0.1:8000/api/health -> "status": "healthy"

[ ] 2. Audio Output Verified:
       Confirm workstation audio speakers/headphones are unmuted and set to ~50% volume.

[ ] 3. Database State Verified:
       Confirm benchmark.db contains 360 rows in benchmark_results.

[ ] 4. Clean Browser Session:
       Open Google Chrome or Mozilla Firefox in a standard browser window (not incognito, to allow local audio caching).
       Navigate to http://127.0.0.1:8000/
       Open Chrome DevTools (F12) -> Console tab -> Confirm zero red errors.
```

---

## 3. The 5-Minute Executive Demonstration Script

### Act 1: The Core Problem & Overview (1 Minute)
1. **Navigate to:** `Overview` tab.
2. **Narration:**
   > *"Welcome to CallLens. In the speech AI industry, vendors frequently claim 95%+ accuracy based on pristine, wideband studio recordings. But in production telephony—where audio is constrained by standard PSTN filters, lossy companding, and extreme background noise—models often collapse. CallLens is an engineering platform that evaluates speech models under true telephony stress while providing practical contact center speech tools."*
3. **Showcase:** Point out the 4-stage degradation cascade visual card and the platform stat counter (360 verified benchmark runs).

---

### Act 2: The Benchmark Revelation (1.5 Minutes)
1. **Navigate to:** `Compare AI Models` tab.
2. **Showcase:** Examine the side-by-side comparison matrix between Prisma v2.5 and Prisma v3.0:
   - **Clean Audio:** Prisma v3.0 leads (**$6.65\%\text{ WER}$** vs $8.18\%\text{ WER}$, $+1.53\%$ v3.0 advantage).
   - **PSTN Telephony:** Prisma v3.0 leads (**$7.84\%\text{ WER}$** vs $8.20\%\text{ WER}$, $+0.36\%$ v3.0 advantage).
   - **Telephony + 10 dB SNR:** Prisma v2.5 leads (**$11.32\%\text{ WER}$** vs $13.03\%\text{ WER}$, $+1.71\%$ v2.5 advantage).
   - **Telephony + 0 dB SNR (The Turning Point):**
     - **Prisma v2.5:** **$18.92\%\text{ WER}$**
     - **Prisma v3.0:** **$25.82\%\text{ WER}$** (Prisma v2.5 demonstrates a **$+6.90\%$** noise resilience advantage!)
3. **Narration:**
   > *"Under extreme 0 dB ambient noise, Prisma v3.0 suffers attention dispersion, while v2.5's localized acoustic modeling retains better intelligibility. This proves why architecture decisions must be stress-tested against real telephony noise, not assumed."*
4. **Point to:** The 1,000-resample non-parametric bootstrap confidence interval table confirming statistical significance.

---

### Act 3: Speech-to-Text & Text-to-Speech in Action (1.5 Minutes)
1. **Navigate to:** `Record & Transcribe` tab.
   - Select the pre-recorded clip: `banking_ivr_english_02.wav`.
   - Select Model: `Prisma v3.0`.
   - Click **Transcribe Clip**.
   - Show instantaneous transcript generation, Real-Time Factor ($RTF \approx 0.10$), and click the **Copy Transcript** button.
2. **Navigate to:** `Convert Text to Speech` tab.
   - Enter prompt: *"Your EMI payment of 5,200 rupees is scheduled for deduction on Friday."*
   - Select Voice: **`Pranav`** (Corporate Male).
   - Click **Generate Speech**.
   - The audio player loads the generated WAV immediately. Click **Play** so the audience hears the synthesized output.
   - Highlight the telemetry cards: audio duration, latency, and character count.

---

### Act 4: Contact Center Application & System Integrity (1 Minute)
1. **Navigate to:** `Payment Follow-up Assistant`.
   - Select scenario: **Overdue Loan Escalation**.
   - Click **Synthesize Agent Voice** to preview the compliant collection notice.
   - Point out the customer response analysis and automated intent classification (e.g., *"Financial Hardship / Dispute"*).
2. **Navigate to:** `My Recordings`.
   - Show the live chronological audit table capturing every transcription and synthesis executed during the demo.
   - Click the inline **`▶ Play`** button in the newest row to play back the audio directly from history.
3. **Navigate to:** `System Health`.
   - Show storage telemetry: 347 verified assets, zero missing files, zero orphaned records, and healthy database synchronization.

---

## 4. Evaluator Questions & Answers

### Q1: *"Are the benchmark numbers real or simulated?"*
> **Answer:** *"The 360 benchmark records are 100% genuine historical evaluations executed against the provider API and stored in our SQLite database (`benchmark.db`). They were run across 3 controlled experiments (A, D, and F) and verified through 1,000-resample bootstrap confidence intervals. Our current demonstration runs in a fail-closed offline mode to protect cloud credits, but reads directly from the immutable historical dataset."*

### Q2: *"Why does Prisma v3.0 degrade more severely under 0 dB SNR than v2.5?"*
> **Answer:** *"Prisma v3.0 employs deeper self-attention transformer layers optimized for semantic context in clean speech. In severe zero-dB noise environments, background acoustic artifacts contaminate attention matrices, causing hallucinated token deletions. Prisma v2.5 uses a more localized acoustic frame decoder, giving it superior robustness when signal and noise powers are equal."*

### Q3: *"Can CallLens run in production with live telephone lines?"*
> **Answer:** *"Yes. The application exposes standard REST and WebSocket endpoints (`/ws/speech`), G.712 audio ingestion filters, and an Indic voice catalog. Connecting CallLens to a live telephony PBX (such as Asterisk or FreeSWITCH) simply requires configuring SIP/RTP media forwarding to our WebSocket gateway and enabling `ALLOW_LIVE_API=1`."*

---

## 5. Troubleshooting & Fallback Procedures

| Scenario | Symptom | Immediate Remediation |
| :--- | :--- | :--- |
| **No Sound on Playback** | Player timer advances but no audio heard. | 1. Check physical hardware volume.<br>2. Confirm browser tab is not muted.<br>3. In Windows Volume Mixer, confirm Chrome audio is enabled. |
| **Microphone Permission Denied** | Browser blocks microphone input in STT. | 1. Click the lock/tune icon in the browser address bar.<br>2. Toggle Microphone to 'Allow'.<br>3. Reload page. (Or fall back to Clip Mode using pre-recorded samples). |
| **Server Offline / Connection Refused** | Browser displays 'Unable to connect'. | Run PowerShell command: `.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000` |

---

## 6. Remote & Online Demonstration Deployment Guide

To conduct a remote or online demo for evaluators, clients, or conference attendees:

### Option A: Instant Remote Tunneling (Fastest for Remote Screen-Share)
If running CallLens on your local workstation and sharing access with remote participants:
1. Start the server locally:
   ```powershell
   .\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000
   ```
2. In a separate terminal, expose via Cloudflare Tunnel or ngrok:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   # OR
   ngrok http 8000
   ```
3. Share the secure HTTPS URL with remote evaluators. WebSockets and audio playback function seamlessly over secure HTTPS/WSS tunnels.

### Option B: Standalone Docker Deployment (Production Shippable)
Deploy to any Linux cloud instance (AWS EC2, GCP Compute Engine, DigitalOcean, Hetzner, Render, Railway):
1. Clone the repository and configure `.env`:
   ```bash
   git clone https://github.com/dragyo7/calllens-stress-lab.git
   cd calllens
   cp .env.example .env
   ```
2. Build and run with Docker Compose:
   ```bash
   docker compose up -d --build
   ```
3. The platform automatically creates local `./data` directories with standalone fallback, mounts ports `8000:8000`, and runs health checks continuously.

### Option C: Live Provider Enablement (When API Credentials Are Provided)
To switch the demo from deterministic offline fixtures to genuine live Gnani Cloud APIs:
1. In `.env`, set:
   ```env
   ALLOW_LIVE_API=1
   GNANI_API_KEY=your_actual_gnani_api_key
   MAX_LIVE_CALLS=50
   ```
2. Restart the server. CallLens automatically detects the live configuration, validates token balance, and routes STT/TTS calls directly to Gnani endpoints while maintaining file-lock attempt accounting.

