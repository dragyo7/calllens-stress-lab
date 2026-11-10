# CallLens — REST & WebSocket API Reference

**Document ID:** `CL-API-001`  
**Version:** 2.0.0  
**Status:** Canonical Reference  
**Last Updated:** November 2026  
**Author:** Technical Ownership & Engineering Governance  

---

## 1. Global Conventions & Protocol Standards

### 1.1. Base URL & Protocol
- **Local Development Base URL:** `http://127.0.0.1:8000`
- **WebSocket Base URL:** `ws://127.0.0.1:8000`
- **Content Type:** `application/json` (unless handling multipart audio uploads or audio streaming)
- **Character Encoding:** UTF-8

### 1.2. Status Codes & Error Formatting
Standard HTTP status codes are returned across all REST endpoints:
- `200 OK`: Request succeeded.
- `400 Bad Request`: Invalid input parameters, missing audio file, or malformed payload.
- `404 Not Found`: Requested session ID, audio file, or benchmark resource does not exist.
- `422 Unprocessable Entity`: Schema validation error (handled by Pydantic).
- `500 Internal Server Error`: Unhandled server exception (logged with stack trace).

Error responses conform to the standard structure:
```json
{
  "detail": "Error description message explaining the failure condition."
}
```

---

## 2. API Endpoint Directory

| Category | Method | Path | Summary |
| :--- | :--- | :--- | :--- |
| **System** | `GET` | `/` | Serves the single-page application dashboard. |
| **System** | `GET` | `/api/health` | System health, database connectivity, and credit protection status. |
| **Benchmark** | `GET` | `/api/clips` | Lists available pre-recorded telephony benchmark audio clips. |
| **Benchmark** | `GET` | `/api/benchmark/summary` | Aggregated 360-evaluation benchmark summary and bootstrap CIs. |
| **Benchmark** | `GET` | `/api/audio/{id}` | Streams pristine or degraded benchmark audio WAV files. |
| **Stress Lab** | `POST` | `/api/stress` | Applies on-demand acoustic degradation (G.712, $\mu$-law, SNR). |
| **Speech-to-Text** | `POST` | `/api/stt/transcribe` | Batch speech recognition (accepts multipart file or clip ID). |
| **Text-to-Speech** | `POST` | `/api/tts/synthesize` | Batch speech synthesis using curated Indic voices. |
| **Text-to-Speech** | `GET` | `/api/tts/audio/{filename}` | Streams generated TTS audio WAV files. |
| **Text-to-Speech** | `GET` | `/api/tts/voices` | Returns catalog of supported Indic voice talents. |
| **Live Streaming** | `WS` | `/ws/speech` | Bidirectional real-time audio streaming WebSocket channel. |
| **Follow-up** | `GET` | `/api/followup/scenarios` | Returns pre-configured debt recovery dialogue scenarios. |
| **Follow-up** | `GET` | `/api/followup/records` | Returns persisted operator-confirmed commitments from SQLite. |
| **Follow-up** | `POST` | `/api/followup/process` | Processes customer response, synthesizes agent speech, extracts intent. |
| **Follow-up** | `POST` | `/api/followup/confirm` | Commits payment arrangement to audit log. |
| **History** | `GET` | `/api/history` | Returns paginated session audit log (JSON or CSV format). |
| **History** | `DELETE`| `/api/history/{history_id}` | Removes a specific history record and cleans up associated audio assets. |
| **History** | `DELETE`| `/api/history` | Clears all history records (privacy/test isolation). |
| **Recordings** | `GET` | `/api/recordings` | Lists recorded audio sessions with metadata. |
| **Recordings** | `DELETE`| `/api/recordings/{session_id}` | Cascading deletion of session record and disk WAV file. |
| **Diagnostics** | `GET` | `/api/storage/diagnostics` | Storage telemetry, folder sizes, and asset integrity metrics. |
| **Documentation**| `GET` | `/docs` | Interactive Swagger / OpenAPI documentation. |

---

## 3. Detailed Endpoint Specifications

### 3.1. System Health & Platform Status
#### `GET /api/health`
Returns runtime status, environment parameters, database health, and safety gate state.

**Response Schema (`200 OK`):**
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "allow_live_api": false,
  "live_api_enabled": false,
  "database": {
    "status": "connected",
    "path": "E:\\Gnani AI proj\\calllens-data\\benchmark.db",
    "benchmark_count": 360
  },
  "storage": {
    "status": "ok",
    "total_assets": 347,
    "total_size_mb": 33.21
  },
  "rate_limiter": {
    "max_requests_per_sec": 5.0,
    "available_tokens": 5.0
  }
}
```

---

### 3.2. Speech-to-Text (STT) Studio
#### `POST /api/stt/transcribe`
Transcribes an uploaded audio file or a pre-existing benchmark clip using the specified model.

**Request Type:** `multipart/form-data`  
**Parameters:**
- `file` (*optional*, Binary): Uploaded audio file (WAV format, 16 kHz or 8 kHz). Required if `clip_id` is omitted.
- `clip_id` (*optional*, String): Identifier of a server-hosted benchmark clip. Required if `file` is omitted.
- `model` (*optional*, String, default: `"prisma-v3.0"`): ASR engine (`"prisma-v2.5"` or `"prisma-v3.0"`).
- `language` (*optional*, String, default: `"en-IN"`): Language code (`"en-IN"` or `"hi-IN"`).

**Response Schema (`200 OK`):**
```json
{
  "transcript": "Hello I am calling regarding your overdue EMI payment for loan number 4821",
  "duration_sec": 4.12,
  "audio_duration_sec": 4.12,
  "processing_time_sec": 0.45,
  "rtf": 0.109,
  "word_count": 13,
  "model": "prisma-v3.0",
  "language": "en-IN",
  "session_id": "stt-9b1d7f3c-8a21-4f1b-b72e-3f9c6d1a4e8b",
  "from_cache": false,
  "audio_url": "/api/audio/stt-9b1d7f3c.wav"
}
```
*Note: Both `duration_sec` and `audio_duration_sec` are emitted for frontend contract redundancy.*

---

### 3.3. Text-to-Speech (TTS) Studio
#### `POST /api/tts/synthesize`
Synthesizes speech from input text using one of the 7 curated Indic voices.

**Request Type:** `application/json`  
**Request Body:**
```json
{
  "text": "Your account has an outstanding balance of 4,500 rupees due tomorrow.",
  "voice": "Pranav",
  "language": "en-IN",
  "speed": 1.0
}
```

**Response Schema (`200 OK`):**
```json
{
  "audio_url": "/api/tts/audio/tts-8c2f1a4e-1289-4d87-a89c-01bcde345678.wav",
  "filename": "tts-8c2f1a4e-1289-4d87-a89c-01bcde345678.wav",
  "audio_duration_sec": 3.84,
  "duration_sec": 3.84,
  "character_count": 68,
  "processing_time_sec": 0.38,
  "rtf": 0.099,
  "voice": "Pranav",
  "language": "en-IN",
  "session_id": "tts-8c2f1a4e-1289-4d87-a89c-01bcde345678"
}
```

#### `GET /api/tts/voices`
Returns metadata for all supported Indic voice talents.

**Response Schema (`200 OK`):**
```json
{
  "voices": [
    {"name": "Pranav", "gender": "male", "language": "en-IN", "style": "Corporate / Professional"},
    {"name": "Priya", "gender": "female", "language": "en-IN", "style": "Warm / Conversational"},
    {"name": "Neerja", "gender": "female", "language": "hi-IN", "style": "Customer Support"},
    {"name": "Aditi", "gender": "female", "language": "en-IN", "style": "Expressive"},
    {"name": "Rohan", "gender": "male", "language": "en-IN", "style": "Energetic"},
    {"name": "Kavya", "gender": "female", "language": "hi-IN", "style": "Friendly"},
    {"name": "Suresh", "gender": "male", "language": "en-IN", "style": "Authoritative"}
  ]
}
```

#### `GET /api/tts/audio/{filename}`
Streams the synthesized WAV audio file with proper binary headers.
- **Response Headers:** `Content-Type: audio/wav`, `Accept-Ranges: bytes`

---

### 3.4. Live Speech WebSocket Protocol
#### `WS /ws/speech`
Bidirectional WebSocket streaming endpoint for low-latency live audio.

**Protocol State Flow:**
1. **Client Handshake:** Connects to `ws://127.0.0.1:8000/ws/speech`.
2. **Session Initialization:**
   ```json
   {"action": "start", "model": "prisma-v3.0", "language": "en-IN"}
   ```
   *Server Response:*
   ```json
   {"status": "ready", "session_id": "ws-1731234567"}
   ```
3. **Audio Chunk Ingestion:**
   ```json
   {"action": "audio_chunk", "data": "UklGRiQAAABXQVZFZm10IBAAAAABAAEA..."}
   ```
   *Server Response:*
   ```json
   {"status": "streaming", "bytes_received": 8192}
   ```
4. **Finalization & Transcription:**
   ```json
   {"action": "finish_recording", "type": "stop"}
   ```
   *Server Response:*
   ```json
   {
     "status": "completed",
     "transcript": "Hello this is a live test over WebSockets",
     "audio_duration_sec": 2.50,
     "audio_url": "/api/audio/ws-1731234567.wav"
   }
   ```

---

### 3.5. Model Comparison & Benchmark Summary
#### `GET /api/benchmark/summary`
Returns the complete 360-record historical benchmark evaluation, stratified across Prisma v2.5 and v3.0 under all 4 acoustic conditions with 1,000-resample non-parametric bootstrap confidence intervals.

**Response Schema (`200 OK`):**
```json
{
  "total_records": 360,
  "experiments": {
    "A": 240,
    "D": 40,
    "F": 80
  },
  "experiment_a": {
    "prisma-v2.5": {
      "clean": {"n": 30, "mean_wer": 0.0818, "ci_lower": 0.0549, "ci_upper": 0.1161, "mean_cer": 0.0296, "p50_latency": 0.194, "rtf": 0.021},
      "tel": {"n": 30, "mean_wer": 0.0820, "ci_lower": 0.0549, "ci_upper": 0.1153, "mean_cer": 0.0282, "p50_latency": 0.197, "rtf": 0.022},
      "tel_snr10": {"n": 30, "mean_wer": 0.1132, "ci_lower": 0.0703, "ci_upper": 0.1680, "mean_cer": 0.0510, "p50_latency": 0.179, "rtf": 0.020},
      "tel_snr0": {"n": 30, "mean_wer": 0.1892, "ci_lower": 0.1282, "ci_upper": 0.2581, "mean_cer": 0.1028, "p50_latency": 0.193, "rtf": 0.021}
    },
    "prisma-v3.0": {
      "clean": {"n": 30, "mean_wer": 0.0665, "ci_lower": 0.0481, "ci_upper": 0.0867, "mean_cer": 0.0245, "p50_latency": 0.214, "rtf": 0.022},
      "tel": {"n": 30, "mean_wer": 0.0784, "ci_lower": 0.0578, "ci_upper": 0.1016, "mean_cer": 0.0301, "p50_latency": 0.210, "rtf": 0.022},
      "tel_snr10": {"n": 30, "mean_wer": 0.1303, "ci_lower": 0.0898, "ci_upper": 0.1750, "mean_cer": 0.0620, "p50_latency": 0.213, "rtf": 0.022},
      "tel_snr0": {"n": 30, "mean_wer": 0.2582, "ci_lower": 0.1926, "ci_upper": 0.3319, "mean_cer": 0.1546, "p50_latency": 0.209, "rtf": 0.022}
    }
  }
}
```

---

### 3.6. History & Storage Diagnostics
#### `GET /api/history`
Returns chronological session audit records. Supports optional query parameters:
- `limit` (*integer*, default: `50`): Max records to return.
- `offset` (*integer*, default: `0`): Pagination offset.
- `format` (*string*, default: `"json"`): Either `"json"` or `"csv"`.

**Response Schema (`200 OK`):**
```json
{
  "total_count": 25,
  "records": [
    {
      "session_id": "stt-9b1d7f3c-8a21",
      "operation_type": "stt",
      "model_or_voice": "prisma-v3.0",
      "language": "en-IN",
      "input_text": null,
      "output_transcript": "Payment reminder confirmed",
      "duration_sec": 3.2,
      "latency_ms": 320.0,
      "audio_file": "recordings/stt-9b1d7f3c.wav",
      "created_at": "2026-11-10T06:15:32"
    }
  ],
  "history": [ ... ]
}
```

#### `DELETE /api/history/{history_id}`
Deletes an individual speech activity record from SQLite `audio_history` and removes associated audio file assets.

**Response Schema (`200 OK`):**
```json
{
  "success": true,
  "deleted_id": 42
}
```

#### `DELETE /api/history`
Clears all history records from `audio_history` for privacy reset and test isolation.

**Response Schema (`200 OK`):**
```json
{
  "success": true,
  "deleted_count": 16
}
```

#### `DELETE /api/recordings/{session_id}`
Atomically deletes a recorded audio session:
1. Deletes metadata entry from SQLite table `history_records`.
2. Physically unlinks the corresponding `.wav` file from `recordings/`.

**Response Schema (`200 OK`):**
```json
{
  "status": "deleted",
  "session_id": "stt-9b1d7f3c-8a21",
  "file_deleted": true
}
```

#### `GET /api/storage/diagnostics`
Audits persistent disk directories and verifies database-to-file synchronization.

**Response Schema (`200 OK`):**
```json
{
  "total_recording_sessions": 129,
  "total_audio_assets": 438,
  "total_storage_mb": 42.91,
  "missing_audio_files": 0,
  "orphaned_files": 0,
  "integrity_status": "HEALTHY"
}
```

#### `POST /api/storage/cleanup`
Safely prunes expired temporary files and unreferenced assets while maintaining database integrity.

**Query Parameters:**
- `max_age_hours` (integer, default: 24): Age threshold in hours beyond which unpinned temp files are deleted.
- `prune_temp_only` (boolean, default: false): When true, restricts cleanup to temporary cache directory only.

**Response Schema (`200 OK`):**
```json
{
  "status": "success",
  "cleaned_temp_files": 38,
  "cleaned_asset_files": 0,
  "total_files_removed": 38,
  "freed_bytes": 0,
  "freed_mb": 0.0,
  "retention_hours": 24,
  "timestamp": "2026-11-10T08:24:56.222007+00:00"
}
```

---

### 3.7. Payment Follow-up Desk Endpoints
#### `GET /api/followup/scenarios`
Returns pre-configured synthetic BFSI telephony dialogue scenarios across Hindi, Hinglish, and South Indic English telephony.

**Response Schema (`200 OK`):**
```json
{
  "scenarios": [
    {
      "id": "scenario_01",
      "customer_name": "राहुल शर्मा",
      "dialogue_text": "नमस्ते राहुल जी...",
      "reference_amount": 50000,
      "reference_due_day": 5,
      "reference_ptp": "15th"
    }
  ]
}
```

#### `GET /api/followup/records`
Returns recent operator-confirmed commitments from SQLite storage (`followup_records` table) for human-in-the-loop review.

**Query Parameters:**
- `limit` (*integer*, default: `50`, max: `200`): Maximum records to retrieve.

**Response Schema (`200 OK`):**
```json
{
  "success": true,
  "count": 50,
  "records": [
    {
      "followup_id": "flw_a1b2c3d4e5f6",
      "session_id": null,
      "asset_id": "ast_9876543210ab",
      "audio_url": "/api/tts/audio/followup_reminder_a1b2c3.wav",
      "customer_name": "राहुल शर्मा",
      "amount": 50000,
      "due_date": "5th",
      "ptp_date": "15th",
      "concern": "Delay due to medical emergency",
      "call_summary": "Customer confirmed payment promise for 15th",
      "reminder_text": "नमस्ते राहुल जी, आपका ₹50,000 का भुगतान 15 तारीख तक अपेक्षित है।",
      "voice": "Pranav",
      "verification_status": "operator_verified",
      "confirmed_at": "2026-11-10 08:30:00 UTC"
    }
  ]
}
```

#### `POST /api/followup/process`
Transcribes follow-up audio/text and extracts structured commitments (Amount, Due Date, PTP Date, Customer Concern).

#### `POST /api/followup/confirm`
Synthesizes verified follow-up reminder audio via Gnani Timbre neural TTS and commits the verified record to the SQLite database.



