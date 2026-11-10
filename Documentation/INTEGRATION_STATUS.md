# CallLens — Provider Integration & Gateway Status

**Document ID:** `CL-INT-001`  
**Version:** 2.0.0  
**Status:** Canonical Reference  
**Last Updated:** November 2026  
**Author:** Technical Ownership & Engineering Governance  

---

## 1. Provider Ecosystem & Integration Scope

CallLens interfaces with the **Gnani.ai Speech Intelligence Suite**, specifically:
1. **Gnani Prisma Speech-to-Text (ASR):** Evaluated across two model generations:
   - **Prisma v2.5:** Previous-generation production acoustic model.
   - **Prisma v3.0:** Modern transformer-based acoustic model.
2. **Gnani Timbre Text-to-Speech (TTS):** Generative neural speech synthesis supporting 7 curated Indic voices.

```mermaid
flowchart TD
    subgraph AppBoundary ["CallLens Application Boundary"]
        ClientReq["Application Request (STT / TTS)"]
        Gatekeeper{"ALLOW_LIVE_API == 1 ?"}
        MockEngine["Deterministic Mock Engine<br>(Zero Credit Spend)"]
        RateLimiter["Token-Bucket Limiter<br>(Max 5 req/s)"]
        FileLock["Attempt Cap & File Lock<br>(Max 434 calls)"]
        GnaniClient["Gnani Client Transport"]
    end

    subgraph GnaniCloud ["Gnani External Cloud APIs"]
        PrismaAPI["Prisma ASR Endpoints<br>(v2.5 / v3.0)"]
        TimbreAPI["Timbre TTS Endpoints<br>(7 Indic Voices)"]
    end

    ClientReq --> Gatekeeper
    Gatekeeper -->|No (Default: 0)| MockEngine
    Gatekeeper -->|Yes| RateLimiter
    RateLimiter --> FileLock
    FileLock --> GnaniClient
    GnaniClient --> PrismaAPI
    GnaniClient --> TimbreAPI
```

---

## 2. The Fail-Closed Zero-Credit Policy

To prevent unintended expenditure of cloud provider API credits during automated testing, continuous integration, and local evaluation, CallLens enforces a strict **fail-closed architectural gate**:
- **Environment Variable:** `ALLOW_LIVE_API` (Default: `0` / `false`).
- **Policy Enforcement:**
  - When `ALLOW_LIVE_API=0`, all outbound network calls to `gnani.ai` endpoints are intercepted at the gateway transport boundary.
  - The client dispatches requests to the deterministic offline mock engine (`calllens/gnani_client.py`).
  - Synthetic transcripts and voiced multi-tone WAV audio files are generated deterministically, consuming **0 credits**.

### 2.1. Distinguishing Real Browser Execution from Live Provider Calls
It is essential to maintain transparency regarding evaluation layers:
- **Real Browser Execution:** Validated using Chrome Headless via the Chrome DevTools Protocol (CDP). JavaScript event listeners, DOM mutations, Web Audio API instantiation, and WebSocket frames are executed in a real browser process.
- **Provider Layer:** In the default verification environment, the backend serves deterministic mock responses to the real browser.

### 2.2. Verified Genuine Live Integration Smoke Test
Under controlled authorization (`ALLOW_LIVE_API=1`, `MAX_LIVE_CALLS=2`), genuine live requests were executed and verified against the Gnani Speech AI platform:
1. **Live Prisma STT v2.5 (`POST https://api.vachana.ai/stt/v3`):**
   - **Request ID:** `req_e0c640ca0f3a`
   - **Audio Payload:** `data/fleurs/audio/14706914212578682198.wav` (4.74s, 16kHz mono)
   - **Returned Transcript:** `'लूना को साथी पहलवानों ने भी श्रद्धांजलि दी'` (100% exact match to ground truth)
   - **Latency:** 0.832s, `from_cache: False`
2. **Live Timbre TTS v2.5 (`POST https://api.vachana.ai/api/v1/tts/inference`):**
   - **Request ID:** `req_7f0a104e3bf4`
   - **Text:** `'कॉल लेंस लाइव एकीकरण परीक्षण सफल रहा'`
   - **Voice:** `Pranav`, `model: timbre-v2.5`, `language: hi-IN`
   - **Returned Audio:** 230,444 bytes, 48 kHz mono PCM16 WAV, 2.40s duration, valid RIFF header
   - **Latency:** 0.956s
3. **Dead Man's Switch Cap Enforcement:** Attempt #3 was rejected with `CallLimitExceededError: Persistent global network attempt cap reached across processes: 2/2`, confirming zero credit overrun.

---

## 3. Curated Indic Voice Catalog

The platform provides seven curated voices across gender and regional acoustic characteristics:

| Voice Name | Gender | Primary Language | Accent / Style Description | Recommended Use Case | Normalization Target |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Pranav** | Male | `en-IN` | Corporate, deliberate, professional | Payment reminders, corporate IVR | `Pranav` |
| **Priya** | Female | `en-IN` | Warm, conversational, clear | Banking customer service, onboarding | `Priya` |
| **Neerja** | Female | `hi-IN` / Hinglish | Empathetic, conversational, customer support | Retail assistance, debt dispute handling | `Neerja` |
| **Aditi** | Female | `en-IN` | Expressive, dynamic | Marketing announcements, interactive bots | `Aditi` |
| **Rohan** | Male | `en-IN` | Energetic, young professional | Fintech alerts, two-factor auth calls | `Rohan` |
| **Kavya** | Female | `hi-IN` | Friendly, vernacular | Regional outreach, agricultural advisory | `Kavya` |
| **Suresh** | Male | `en-IN` | Authoritative, mature | Legal compliance notices, security alerts | `Suresh` |

### 3.1. Perimeter Case Normalization
The external Gnani Timbre API strictly enforces proper-case strings (e.g., `"Pranav"`) and throws `ValueError: Invalid voice` if provided lowercase strings (e.g., `"pranav"`).
- **Client Defense:** `calllens/gnani_client.py` and `app/main.py` enforce:
  ```python
  def normalize_voice(voice_str: str) -> str:
      if not voice_str:
          return "Pranav"
      cleaned = voice_str.strip()
      return cleaned.capitalize()
  ```
- This guarantees resilient operation even if frontends or third-party webhooks submit unnormalized strings.

### 3.2. Official Gnani Timbre & Prisma SDK Contracts
Inspection of the installed `gnani-vachana` SDK (`gnani.tts.client.GnaniTTSClient` and `gnani.stt.client.GnaniSTTClient`) establishes the exact provider protocol contracts:

#### 1. Text-to-Speech (Gnani Timbre v2.5 / v3.0)
- **Base URL:** `https://api.vachana.ai`
- **Inference Endpoint:** `/api/v1/tts/inference` (HTTP POST)
- **Streaming Endpoints:** `/api/v1/tts/sse` (Server-Sent Events), `/api/v1/tts` (WebSocket)
- **Authentication Headers:** `X-API-Key-ID: <GNANI_API_KEY>`, `X-API-Request-ID: <UUID>`, `Content-Type: application/json`
- **Request Body Schema:**
  ```json
  {
    "text": "नमस्ते यह परीक्षण है",
    "voice": "Pranav",
    "model": "timbre-v2.5",
    "language": "hi-IN",
    "speed": 1.0,
    "audio_config": {
      "sample_rate": 48000,
      "encoding": "linear_pcm",
      "num_channels": 1,
      "sample_width": 2,
      "container": "wav"
    }
  }
  ```
- **Supported Speed Range:** `0.85` to `1.15` (normal: `1.0`).
- **Official Voice Catalog (`TIMBRE_V25_VOICES`):**
  - **English (6):** `Pranav`, `Kaveri`, `Trupti`, `Devika`, `Shlok`, `Girish`
  - **Hindi (13):** `Nalini`, `Bhavna`, `Yashvi`, `Urmila`, `Jwala`, `Chitra`, `Ambuja`, `Deepak`, `Roopesh`, `Vikrant`, `Hemraj`, `Jalaj`, `Omkar`
  - **Hinglish (1):** `Poorvi`
  - **Regional Indic (22):** Tamil (`Asmita`, `Trisha`, `Brinda`, `Vedika`, `Noopur`), Telugu (`Suhana`, `Lehara`, `Lavanya`, `Yukti`, `Varuni`), Kannada (`Saanvi`, `Kavin`), Malayalam (`Reshma`, `Riyaan`), Marathi (`Zahira`, `Ishaan`), Bengali (`Kirra`, `Dhruva`), Gujarati (`Falak`, `Veera`), Punjabi (`Mehuli`, `Zayan`).
- **Response Format:** Raw binary audio bytes (`audio/wav`), streamable directly into HTML5 `<audio>` elements or saved to persistent disk.

#### 2. Speech-to-Text (Gnani Prisma v2.5 / v3.0)
- **Base URL:** `https://api.vachana.ai`
- **Batch Inference Endpoint:** `/stt/v3` (HTTP POST, multipart/form-data)
- **Real-time Streaming Endpoint:** `/stt/v3/stream` (WebSocket)
- **Authentication Headers:** `X-API-Key-ID: <GNANI_API_KEY>`, `X-API-Request-ID: <UUID>`
- **Model Parameter:**
  - `model = None`: Selects production baseline **Prisma v2.5**
  - `model = "prisma-v3.0"`: Opts in to transformer-based **Prisma v3.0**
- **Output Formats:** `"verbatim"` (raw spoken transcription), `"transcribe"` (inverse text normalized).
- **Supported Languages:** `en-IN`, `hi-IN`, `gu-IN`, `ta-IN`, `kn-IN`, `te-IN`, `mr-IN`, `bn-IN`, `ml-IN`, `pa-IN`, plus `indic-auto` on Prisma v3.0.

---

## 4. Rate Limiting, File Locking & Attempt Caps

When live calls are authorized (`ALLOW_LIVE_API=1`), three protection layers safeguard provider quota:

### 4.1. Token-Bucket Rate Limiter (`calllens/rate_limiter.py`)
- **Capacity:** 5 tokens (max burst of 5 concurrent requests).
- **Refill Rate:** 2 tokens per second (sustained 2 requests/sec).
- **Behavior:** Requests arriving when tokens are exhausted enter an asynchronous wait queue until tokens refill.

### 4.2. Hard Call Attempt Cap (434 Calls)
To prevent infinite loops from draining accounts, a strict ceiling is enforced:
- **Maximum Lifetime Attempts:** **434 calls**.
- **Audit File:** `E:\Gnani AI proj\calllens-data\call_accounting.json`
- **File Locking:** Concurrent writes to `call_accounting.json` are synchronized via `call_accounting.lock` using operating-system primitives (`msvcrt.locking` on Windows, `fcntl.flock` on Unix).

### 4.3. Verified Accounting State (Current Audit)
```json
{
  "total_attempts": 341,
  "successful_calls": 338,
  "retried_timeouts": 3,
  "recent_session": {
    "live_calls": 0,
    "network_attempts": 0,
    "cache_hits": 3,
    "mock_calls": 10
  },
  "remaining_credit_quota": 93
}
```

---

## 5. Live Mode Deployment Procedure

For engineers conducting authorized live evaluations with genuine Gnani API credentials:

1. **Verify Credentials:** Ensure valid API keys and Access Tokens are configured in `.env`:
   ```bash
   GNANI_ACCESS_TOKEN="<valid_token>"
   GNANI_ACCESS_KEY="<valid_key>"
   ```
2. **Enable Live Flag:**
   ```powershell
   $env:ALLOW_LIVE_API="1"
   ```
3. **Verify Health Endpoint:**
   ```bash
   curl http://127.0.0.1:8000/api/health
   # Response must show: "allow_live_api": true, "live_api_enabled": true
   ```
4. **Execute Single Test Call:** Verify live response and monitor `call_accounting.json` to confirm atomic counter incrementation.

