# CallLens Failure Modes & Resilience Architecture

This document specifies the operational failure scenarios of CallLens Stress Lab, detailing detection mechanisms, automatic recoveries, and file:line citations.

---

## 1. Gnani API Downtime & Upstream 5xx Errors

- **Symptom:** Gnani API returns HTTP 500, 502, 503, or 504 during transcription or synthesis.
- **Detection:** `calllens/gnani_client.py:390-399` detects HTTP 5xx status codes and connection errors during request execution.
- **Resilience Mitigation:**
  - **Bounded Exponential Backoff:** `calllens/gnani_client.py:401-412` retries up to 3 attempts (`MAX_RETRIES = 3`), applying exponential delays (1.0s, 2.0s, 4.0s) capped at 8.0s (`MAX_BACKOFF = 8.0`).
  - **No Cache Contamination:** `calllens/gnani_client.py:365-370` only commits successful responses to cache; failed responses are discarded immediately.
  - **Circuit Breaker / Secondary Provider Failover:** NOT IMPLEMENTED.

---

## 2. Upstream 429 Rate Limiting

- **Symptom:** Gnani API rejects bursts of requests with HTTP 429 (Too Many Requests).
- **Detection:** `calllens/gnani_client.py:392-398` categorizes status 429 as retryable.
- **Resilience Mitigation:**
  - **Concurrency Limiting:** `calllens/gnani_client.py:43` and `calllens/gnani_client.py:337` enforce a hard ceiling of 2 concurrent outbound HTTP requests via `threading.Semaphore(2)`.
  - **Exponential Backoff:** `calllens/gnani_client.py:401-412` applies backed-off pauses before retrying.
  - **Fallback to Mock Mode on Exhaustion:** `app/main.py:127` and `calllens/gnani_client.py:314-320` allow the application to function seamlessly in mock mode without consuming network credits.

---

## 3. Account Credit Exhaustion

- **Symptom:** User credit wallet runs out, causing Gnani API to return authorization or balance errors.
- **Detection:** Detected as a non-retryable API error (`calllens/gnani_client.py:413-417`).
- **Resilience Mitigation:**
  - **Pre-Flight Gate Accounting:** `calllens/gnani_client.py:100-106` halts live execution before sending requests if the planned budget exceeds `MAX_LIVE_CALLS`.
  - **Resumable Benchmark State:** `calllens/benchmark.py:159-166` queries the SQLite database prior to every evaluation. If credit runs out mid-run, completed evaluations remain persisted; re-running resumes from the exact failure point without re-billing.

---

## 4. Audio Input Duration Limits (> 30 Seconds)

- **Symptom:** Client uploads an audio file exceeding the 30-second model constraint.
- **Detection & Enforcement:**
  - **Application API Layer:** `app/main.py:239-243` calculates duration using `len(audio_data) / sr` and immediately raises HTTP 400 Bad Request before calling any model.
  - **Degradation Pipeline Guard:** `calllens/degrade.py:186-191` automatically truncates any long audio to exactly 30.0 seconds (`max_samples = 30 * sr`) as a safety net.

---

## 5. Database Concurrency & Storage Failures

- **Symptom:** SQLite database file locked (`database is locked`) or corrupted.
- **Detection & Behavior:** SQLAlchemy engine raises `OperationalError` or `DatabaseError`.
- **Resilience Mitigation:**
  - **Transaction Granularity:** `calllens/benchmark.py:214-215` commits results on a per-evaluation basis rather than one massive batch, ensuring no loss of progress upon unexpected termination.
  - **Idempotent Initialization:** `calllens/benchmark.py:84-88` invokes `Base.metadata.create_all()` ensuring tables and schemas are created automatically if missing.
  - **Multi-Region Distributed Database Replication:** NOT IMPLEMENTED (Local SQLite design intentionally chosen for zero-dependency reproducibility).
