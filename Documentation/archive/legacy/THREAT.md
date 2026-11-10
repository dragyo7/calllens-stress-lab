# CallLens Threat Model & Security Posture

This document evaluates five core threat vectors against the CallLens Stress Lab system, citing exact file and line implementations for each mitigation control.

---

## 1. Anonymous Uploader (Storage & Memory Exhaustion)

- **Threat Scenario:** An unauthenticated user uploads excessively large audio files, non-audio executables, or deeply nested payloads attempting to cause Denial of Service (DoS), OOM crashes, or disk exhaustion.
- **Mitigation Implementations:**
  - **Upload Size Ceiling (5 MB):** `app/main.py:61`, `app/main.py:173-177`, and `app/main.py:222-226` enforce a strict 5 MB payload limit before processing, returning `413 Request Entity Too Large`.
  - **Audio Duration Limit (30s):** `app/main.py:62` and `app/main.py:239-243` reject any audio with a decoded duration exceeding 30.0 seconds with `400 Bad Request`.
  - **Stream Validation & Decoding:** `app/main.py:229-237` attempts PCM decoding via `soundfile.read()`; non-audio or corrupt files are rejected with `400 Bad Request` without disk persistence.
  - **Temporary File Isolation:** Uploads are written to an isolated directory outside the Git tree (`app/main.py:187-188`).

---

## 2. Credit-Burning Scraper (API Quota Exhaustion)

- **Threat Scenario:** An automated script rapidly triggers endpoints in live mode to consume Gnani API balance or cause denial of wallet funds.
- **Mitigation Implementations:**
  - **Default Mock Mode:** `app/main.py:127` and `calllens/gnani_client.py:314-320` default all requests to local mock execution unless explicitly requested.
  - **Hard Live Call Cap (`MAX_LIVE_CALLS`):** `calllens/gnani_client.py:100-106` and `calllens/gnani_client.py:325` check the reserved call count before initiating any network request; calls beyond the budget raise `CallLimitExceededError`.
  - **Deterministic Caching:** `calllens/gnani_client.py:302-311` intercepts duplicate payloads using SHA-256 cache keys, serving responses without network dispatch.
  - **Per-IP Rate Limiting:** `app/main.py:76-86` and `app/main.py:169` restrict clients to a sliding window of 10 requests per minute, returning `429 Too Many Requests`.

---

## 3. Malicious Audio & Path Traversal (Tar Slip / Injection)

- **Threat Scenario:** Malicious audio archives or crafted filenames containing `../` traversal strings attempt to overwrite critical system files or executable binaries.
- **Mitigation Implementations:**
  - **Tar Slip / Path Traversal Guard:** `scripts/get_fleurs.py:27-30` explicitly inspects every tar archive member with `is_relative_to(target_dir)` before extracting, discarding any member with traversal characters.
  - **Deterministic File Naming:** `calllens/degrade.py:173-178` and `calllens/benchmark.py:145` sanitize and construct output paths using explicit internal prefixes and IDs rather than unvalidated user strings.
  - **No Dynamic Code Execution:** `datasets.load_dataset` and `trust_remote_code` are strictly prohibited; source data is parsed with standard CSV readers (`scripts/get_fleurs.py:61-68`).

---

## 4. Leaked API Key / Credential Exposure

- **Threat Scenario:** An engineer or automated tool prints `GNANI_API_KEY` to stdout, logs, commit history, or API error responses.
- **Mitigation Implementations:**
  - **Environment Segregation:** `.gitignore:1-4` explicitly ignores `.env` and `.env.*`.
  - **Centralized Redaction Logging Filter:** `calllens/gnani_client.py:54-68` applies a custom `RedactingFilter` regex matching `api_key`, `token`, `auth`, and the raw `GNANI_API_KEY` string, replacing them with `[REDACTED]`.
  - **Generic API Error Handling:** `app/main.py:293-298` wraps backend exceptions, logging internally and returning a generic error message without exposing backend stack traces or authorization tokens.

---

## 5. Compromised Dependency / Supply Chain Injection

- **Threat Scenario:** A third-party package dependency update introduces backdoors, unauthorized telemetry, or altered evaluation results.
- **Mitigation Implementations:**
  - **Pinned Dependency Manifest:** `requirements.txt:1-14` strictly pins all 14 pre-approved packages to exact semantic versions.
  - **Restricted Host Policy:** Application and scripts only connect to pre-approved hosts (`api.vachana.ai`, `huggingface.co`, `pypi.org`).
  - **Automated Container Sandboxing:** NOT IMPLEMENTED (Runs in virtual environment `.venv`).
  - **Automated Dependency Vulnerability Scanning (e.g. Snyk/pip-audit):** NOT IMPLEMENTED.
