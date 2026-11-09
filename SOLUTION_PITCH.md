# CallLens Stress Lab — Solution Pitch

### The Problem: Speech AI Fragility on India's Telephony Channels
Enterprise speech recognition systems in India frequently underperform in production call centers despite achieving near-perfect Word Error Rates (WER) on public benchmark datasets. Clean, studio-recorded audio (such as FLEURS) hides the brutal reality of telephony acoustics: bandpass truncation (300–3400 Hz), 8 kHz sampling, lossy G.711 $\mu$-law companding, and aggressive background noise (traffic, crowds, packet jitter). For high-stakes domains like BFSI (Banking, Financial Services, and Insurance), minor phonetic inaccuracies directly corrupt debt amounts, due dates, and compliance disclosures—costing Indian enterprises crores in failed collections and regulatory penalties.

---

### The Solution: CallLens Stress Lab
**CallLens Stress Lab** is an end-to-end speech recognition benchmarking platform and interactive evaluation laboratory designed for **The Great Indian Internship Challenge by Gnani.ai**. It establishes an empirical, reproducible stress-testing methodology comparing **Gnani Prisma v2.5** (production baseline) against **Gnani Prisma v3.0** (next-generation multilingual model) on Hindi speech.

Instead of testing models solely on clean audio, CallLens subjects identical speech inputs to a calibrated, ITU-T G.712/G.711 standard-compliant degradation pipeline across four controlled acoustic conditions:
1. `clean`: 16 kHz studio-quality baseline.
2. `tel`: 8th-order Butterworth bandpass (300–3400 Hz) $\rightarrow$ 8 kHz downsampling $\rightarrow$ 8-bit $\mu$-law companding $\rightarrow$ 16 kHz reconstruction.
3. `tel_snr10`: 10 dB Signal-to-Noise Ratio calibrated Gaussian noise + telephony chain.
4. `tel_snr0`: 0 dB SNR severe Gaussian noise + telephony chain.

---

### Key Innovations & BFSI Business Impact
- **Head-to-Head Model Empirical Evaluation:** Measures exact transcript divergence, Word Error Rate (WER), Character Error Rate (CER), Real-Time Factor (RTF), and P50/P95 latency trade-offs between Prisma v2.5 and v3.0, backed by 95% clip-level bootstrap confidence intervals (1,000 resamples).
- **Downstream BFSI Entity Extraction:** Speech recognition is only as valuable as the downstream decisions it drives. CallLens incorporates an independent rule/regex extraction engine that parses Indian Rupee amounts (Western digits, Devanagari numerals, mixed words like *₹2.25 lakh*) and repayment due dates from Hinglish collection calls voiced by Gnani Timbre v2.5, directly evaluating joint business accuracy.
- **Hallucination Detection on Non-Speech:** Quantifies false-text generation rates when models ingest pure digital silence and white Gaussian noise.

---

### Production Engineering Architecture
- **Centralized Provider Gateway (`gnani_client.py`):** Single chokepoint enforcing credential redaction, token bucket rate limiting (concurrency limit = 2), and SHA-256 content-addressable disk caching for zero-redundancy network calls.
- **Persistent Global Safety Cap:** A thread-safe, inter-process file-locked counter enforcing a hard ceiling of 434 cumulative network attempts across all scripts, eliminating runaway API spending risks.
- **Provenance Isolation & Replay:** A strict database-level separation (`provenance = 'live'` vs `'mock'`) ensuring synthetic and live benchmark results are never mixed. The interactive Web UI features instant, zero-cost replay of stored live evaluations.

---

### Expected Impact
CallLens transforms speech AI procurement and deployment from subjective intuition into rigorous, data-driven engineering. Evaluators gain transparent, evidence-backed proof of model robustness boundaries, enabling enterprises to deploy Gnani Prisma with quantifiable accuracy, lower latency, and zero guesswork on India's live telephony networks.

