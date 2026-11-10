# CallLens Benchmark Provenance & Statistical Integrity Audit

**Date:** 2026-11-09  
**Auditor:** Principal AI Benchmark Auditor  
**Database Audited:** `../calllens-data/benchmark.db` (SQLite 3 via SQLAlchemy)  
**Total Database Rows Audited:** 360 rows  

---

## 1. Forensic Reconciliation of Database Rows

Direct SQL querying against `benchmark.db` verifies the exact logical counts specified in `docs/BRIEF.md`:

```sql
SELECT experiment, COUNT(*) FROM benchmark_results GROUP BY experiment;
```
- **Experiment A (FLEURS Telephony Robustness):** **240 rows**  
  (30 clips $\times$ 4 conditions $\times$ 2 models)
- **Experiment D (Noise & Silence Hallucination):** **40 rows**  
  (20 clips $\times$ 2 models)
- **Experiment F (BFSI Banking Entity Extraction):** **80 rows**  
  (10 synthetic utterances $\times$ 4 conditions $\times$ 2 models)
- **Total Physical Records:** **360 rows** (100% accounted for, zero missing combinations, zero duplicate primary keys).

---

## 2. Call Accounting Reconciliation

| Metric | Recorded Count | Forensic Source / Audit Note |
| :--- | :---: | :--- |
| **Logical Evaluations** | **360** | Complete factorial design across all three experiments. |
| **Live Provider Network Requests** | **0** | No live API calls were executed; live calls remain gated at Gate G1 awaiting user approval. |
| **Cache Hits** | **0** | Initial benchmark execution generated fresh records directly into SQLite. |
| **Mock Provider Invocations** | **360** | Executed via `calllens/gnani_client.py:call(..., live=False)`. |
| **Failed Requests** | **0** | No upstream network timeouts or HTTP 5xx errors encountered during mock execution. |
| **Retries Dispatched** | **0** | Retry loop was not triggered in mock execution. |
| **TTS Generation Calls** | **10** | Generated via `scripts/gen_utterances.py` in mock mode. |

---

## 3. Special Forensic Investigation: The 0.480-Second Latency

The previous report published a constant latency of `0.480s` across multiple tables.

### Source Code Tracing:
1. In `calllens/gnani_client.py:221`:
   ```python
   def _generate_mock_stt(payload: dict[str, Any]) -> dict[str, Any]:
       ...
       return {
           "success": True,
           "request_id": f"mock-{hashlib.md5(str(audio).encode()).hexdigest()[:12]}",
           "transcript": transcript,
           "model": model,
           "format": fmt,
           "processing_time": 0.35,
           "end_to_end_latency": 0.48,  # <-- HARDCODED MOCK FIXTURE
           "mock": True,
       }
   ```
2. In `calllens/benchmark.py:195`:
   `lat = res.get("end_to_end_latency", 0.5)`
3. When the benchmark was executed with `live=False`, every record received `latency_sec = 0.480`.

### Forensic Verdict on Latency:
The value `0.480s` is a **static mock fixture**. It represents the client-side simulated response time, **NOT** the live Gnani ASR inference latency. Presenting 0.480s as measured provider latency would be scientifically false.

---

## 4. Special Forensic Investigation: The Zero-WER Rows

The previous report published an exact `0.0000` WER for both Prisma v2.5 and v3.0 on `clean` and `tel` conditions.

### Source Code Tracing:
1. In `calllens/benchmark.py:168`:
   ```python
   mock_text = raw_ref
   if cond == "tel_snr10":
       ...
   elif cond == "tel_snr0":
       ...
   payload = {
       ...
       "mock_transcript": mock_text,
   }
   ```
2. For conditions `clean` and `tel`, `mock_text` was assigned directly from `raw_ref` (the ground truth raw transcription from FLEURS).
3. In `calllens/metrics.py:64`:
   `compute_wer(raw_ref, mock_text)` evaluated identical strings, resulting in an exact mathematical WER of `0.0000`.

### Forensic Verdict on Accuracy:
The `0.0000` WER is an artifact of the deterministic mock generator reproducing the ground truth reference text. It confirms that the metric normalization pipeline behaves deterministically on clean text, but it is **NOT** empirical proof of live model accuracy.

---

## 5. Statistical Integrity & Methodology Audit

1. **Bootstrap Resampling Unit:** Verified in `calllens/metrics.py:140-156` that resampling occurs at the **clip level** (random seed 0, 1000 iterations), not at the word level. This prevents clustering bias.
2. **Confidence Intervals:** 95% CIs reported in `tests/results.md` are mathematically consistent with the clip-level observations.
3. **FLEURS Diversity:** The 30 FLEURS clips contain 30 distinct audio files representing 17 unique text sentences read across male and female speakers. This sample size ($N=30$) is sufficient for a demonstration pilot, but insufficient for statistical significance across the Hindi language.

---

## 6. Resume-Safe Claims vs Unverified Claims

| Metric / Claim | Status | Permissibility for Technical Resume |
| :--- | :---: | :--- |
| **Pipeline Engineering & Architecture** | **VERIFIED** | **Permissible:** Fully implemented, modular architecture, signal degradation, caching, rate limits, 89 passing unit tests. |
| **Audio Processing Mechanics** | **VERIFIED** | **Permissible:** G.711 $\mu$-law, Butterworth bandpass, SNR calibration verified within $\pm 0.5$ dB. |
| **Entity Extraction Engine** | **VERIFIED** | **Permissible:** Regex & rule-based parser verified across required lakh/crore and date cases. |
| **0.480s Inference Latency** | **MOCK ARTIFACT** | **PROHIBITED:** Must NOT claim Prisma v2.5/v3.0 has 0.48s inference latency. Must specify "Simulated in test harness". |
| **0.0000 WER / 100% Accuracy** | **MOCK ARTIFACT** | **PROHIBITED:** Must NOT claim Prisma models achieve 0% error on telephony Hindi. Live evaluation pending credentials. |
