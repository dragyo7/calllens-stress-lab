# CallLens Security & Adversarial Test Report

**Date:** 2026-11-09  
**Auditor:** Independent Security & Vulnerability Auditor  
**Target:** FastAPI Service (`app/main.py`) & Client Layer (`calllens/gnani_client.py`)  
**Test Suite:** `tests/test_security_adversarial.py` & `tests/test_hard_backend.py`

---

## 1. Vulnerability & Threat Matrix

| Threat Category | Test Method | Expected Behavior | Actual Behavior | Severity | Mitigation Status |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **1. Oversized Upload (DoS)** | Sent 5.5 MB payload to `/api/stress`. | Reject with HTTP 413 before processing. | HTTP 413 Content Too Large returned immediately. | **High** | **PASS** (`app/main.py:173`) |
| **2. Audio Duration Abuse** | Sent valid 32.0s PCM16 WAV audio. | Reject with HTTP 400. | HTTP 400 Bad Request returned with duration detail. | **Medium** | **PASS** (`app/main.py:239`) |
| **3. Non-Audio / Malformed File** | Sent Windows PE executable binary with `.wav` MIME. | Reject with HTTP 400. | `sf.read()` caught decoding error, returning HTTP 400. | **Medium** | **PASS** (`app/main.py:229`) |
| **4. Zero-Byte Audio Stream** | Sent 0-byte payload with audio header. | Reject with HTTP 400. | HTTP 400 Bad Request returned. | **Low** | **PASS** (`app/main.py:233`) |
| **5. Cross-Site Scripting (XSS)** | Injected `<script>alert(1)</script>` into `clip_id`. | Escape or reject; do not reflect raw script. | Escaped via `html.escape()` in 404 response. UI uses `textContent`. | **Medium** | **PASS** (Fixed in DEF-001) |
| **6. Path Traversal (Zip-Slip)** | Injected `../../.env` into clip lookup. | Reject with HTTP 404; prevent file traversal. | HTTP 404 returned; path restricted to dataset manifest. | **High** | **PASS** (`app/main.py:270`) |
| **7. SQL Injection (SQLi)** | Injected `' OR '1'='1` into `clip_id`. | Parameterized lookup; no database injection. | Handled safely by SQLAlchemy ORM; HTTP 404 returned. | **Critical** | **PASS** (`calllens/benchmark.py`) |
| **8. Rate Limiting Flooding** | Dispatched 11 rapid requests from single client IP. | First 10 succeed; 11th returns HTTP 429. | Request 11 returned HTTP 429 Too Many Requests. | **Medium** | **PASS** (`app/main.py:76-86`) |
| **9. Credential Log Leakage** | Injected secret token strings into client logger. | Redact API key and auth headers in stdout. | `RedactingFilter` substituted `[REDACTED]` for secrets. | **High** | **PASS** (`calllens/gnani_client.py:54`) |
| **10. Concurrency Flooding** | Dispatched 5 concurrent requests simultaneously. | Process without thread starvation or race conditions. | All 5 requests completed successfully (HTTP 200). | **Low** | **PASS** (`tests/test_hard_backend.py:12`) |

---

## 2. Security Limitations & Operational Boundaries

1. **Process-Local Rate Limiting:**
   - The current rate limiter uses an in-memory dictionary (`app/main.py:66`). In a multi-worker production environment (e.g. running multiple Uvicorn workers behind Gunicorn), rate limit state is not shared across worker processes.
   - *Recommendation for production:* Use Redis or memcached with token bucket algorithms for multi-worker scaling.
2. **Reverse Proxy IP Trust:**
   - Client IP is obtained via `request.client.host` (`app/main.py:168`). If deployed behind an untrusted reverse proxy, clients could spoof `X-Forwarded-For`.
   - *Current scope:* Configured for localhost pair-programming demo and evaluation.
3. **No Dynamic Web Application Firewall (WAF):**
   - The application relies on Python application-layer guards rather than an edge WAF (e.g. Cloudflare, AWS WAF). This is appropriate for an evaluation benchmark, but should be documented as an operational boundary.
