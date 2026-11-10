# CallLens — Security Controls, Safety Guardrails & Reliability Architecture

**Document ID:** `CL-SEC-001`  
**Version:** 2.0.0  
**Status:** Canonical Reference  
**Last Updated:** November 2026  
**Author:** Technical Ownership & Engineering Governance  

---

## 1. Security Architecture & Threat Model

CallLens operates as an enterprise-grade speech intelligence platform handling audio uploads, text prompts, real-time audio streams, and external AI provider communications. The security model addresses four primary threat vectors:
1. **Unintended Cloud Spend:** Preventing automated test loops or rogue queries from exhausting external API credits.
2. **Path Traversal & Local File Inclusion:** Preventing malicious path manipulations (`../../etc/passwd` or `C:\Windows`) via audio retrieval endpoints.
3. **Audio File Exploitation:** Preventing buffer overflow attacks or malicious binary payload execution via malformed audio files.
4. **Data Injection & SQL Attacks:** Protecting relational database stores against tampering or extraction.

```mermaid
flowchart TD
    Request["Incoming Inbound Request"] --> SecFilter["Security Interceptors & Normalization"]
    
    subgraph Interceptors ["Defensive Interception Layers"]
        PathSanitize["Path Traversal Sanitizer (os.path.basename)"]
        AudioValidator["Audio Header & MIME Validator (RIFF/WAV)"]
        ParamQuery["Parameterized SQL Enforcer (Zero String Concat)"]
        CreditGate{"ALLOW_LIVE_API Gate (Default: 0)"}
    end

    SecFilter --> PathSanitize
    SecFilter --> AudioValidator
    SecFilter --> ParamQuery
    SecFilter --> CreditGate

    CreditGate -->|Blocked (0)| OfflineEngine["Deterministic Offline Engine"]
    CreditGate -->|Allowed (1)| TokenBucket["Token Bucket Limiter (5 burst, 2 sustained)"]
    TokenBucket --> AttemptCap["File-Locked Hard Cap (Max 434 calls)"]
    AttemptCap --> OutboundClient["External Gnani Cloud API"]
```

---

## 2. Core Security Controls

### 2.1. Fail-Closed Provider Gate (`ALLOW_LIVE_API`)
- **Mechanism:** The environment variable `ALLOW_LIVE_API` controls whether outbound network calls to external speech providers are permitted.
- **Default State:** `ALLOW_LIVE_API=0` (Disabled / Fail-Closed).
- **Enforcement:** If an unauthenticated or misconfigured deployment attempts to call Gnani APIs, the client layer rejects the network dispatch before any TCP socket is opened.

### 2.2. Hard Call Attempt Cap & Atomic File Lock
- **Cap Ceiling:** Lifetime external calls are capped at **434 attempts**.
- **Accounting Store:** `E:\Gnani AI proj\calllens-data\call_accounting.json`.
- **Concurrency Guard:** All reads and writes to the accounting store are synchronized through `call_accounting.lock` using operating system file locking:
  ```python
  # Windows locking primitive
  import msvcrt
  msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
  # Unix fallback primitive
  import fcntl
  fcntl.flock(f.fileno(), fcntl.LOCK_EX)
  ```
- **Behavior on Cap Exceeded:** The system raises an explicit `QuotaExceededException`, immediately halting outbound network activity.

### 2.3. Path Traversal & Audio Streaming Sanitization
Endpoints serving audio files (`/api/audio/{filename}`, `/api/tts/audio/{filename}`) sanitize input parameters to prevent local file inclusion:
- **Sanitization Rule:** File paths are stripped using `os.path.basename()` and strictly resolved against allowed asset directories:
  ```python
  clean_filename = os.path.basename(filename)
  target_path = os.path.abspath(os.path.join(AUDIO_DIR, clean_filename))
  if not target_path.startswith(os.path.abspath(AUDIO_DIR)):
      raise HTTPException(status_code=403, detail="Access denied")
  ```
- Any request containing `..`, `/`, or absolute disk references is rejected with HTTP 400 or 403.

### 2.4. Audio Format & MIME Type Validation
To prevent arbitrary file uploads, `/api/stt/transcribe` enforces binary inspection:
- Verifies standard `RIFF` header chunk identifier.
- Verifies `WAVE` format header.
- Enforces maximum file size limit ($25\text{ MB}$) to prevent denial-of-service through memory exhaustion.

### 2.5. Parameterized SQL Execution
All interactions with `benchmark.db` use parameterized SQLite queries (`?` place-holders):
```python
cursor.execute(
    "SELECT * FROM history_records WHERE session_id = ? AND operation_type = ?",
    (session_id, op_type)
)
```
String interpolation and f-strings are strictly banned across all database access layers, eliminating SQL injection risks.

### 2.6. Sensitive Credential Redaction
- Access keys (`GNANI_ACCESS_KEY`, `GNANI_ACCESS_TOKEN`) are loaded via environment variables and never logged in plain text.
- Health diagnostics endpoints (`/api/health`, `/api/storage/diagnostics`) mask credential values, displaying boolean status flags only.

---

## 3. Reliability, Fault Tolerance & Recovery

### 3.1. SQLite Write-Ahead Logging (WAL) Mode
- **Concurrency:** SQLite operates in `WAL` mode with `synchronous = NORMAL`. This architecture allows high-volume concurrent reads (dashboard telemetry, audio fetching) while background worker threads write audit records without locking collisions.
- **Auto-Recovery:** In the event of an abrupt power loss or process kill, SQLite automatically replays the `.wal` journal on the next startup, ensuring zero database corruption.

### 3.2. Graceful Degradation & Safe Fallbacks
- If a temporary network partition occurs during a live speech call, the platform logs the error in `provider_logs`, records the failure state in `history_records`, and returns an informative HTTP 504 status to the UI without crashing the application daemon.
- Frontend JavaScript includes try-catch wrappers on all fetch calls, automatically dismissing spinners and displaying user-friendly error banners.

