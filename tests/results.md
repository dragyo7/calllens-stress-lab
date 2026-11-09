# CallLens Stress Lab — Benchmark Results (LIVE DATA)

> Generated on: 2026-11-09 18:57:41 UTC
> Data Provenance: LIVE (Strict Isolation - No Mock Data Mixed)

## Summary Overview

This report documents experimental evaluations comparing **Gnani Prisma v2.5** and **Gnani Prisma v3.0** under clean and simulated telephony degradation conditions (LIVE provenance).

**Important Methodology Notice:** Telephony channel degradation was applied deterministically to read speech (FLEURS) and synthetic TTS speech (Timbre v2.5). This evaluates acoustic robustness under simulated channel degradation and noise; it does not replace testing on real human customer call center recordings.

---

## Experiment A: Hindi ASR Telephony Robustness (FLEURS)

Evaluates 30 FLEURS Hindi India clips (CC BY 4.0, <= 28 seconds) across 4 acoustic conditions with 95% clip-level bootstrap confidence intervals (1,000 resamples, seed 0).

| Model | Condition | N | Mean WER | 95% CI (WER) | Mean CER | P50 Latency (s) | P95 Latency (s) | Mean RTF |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| prisma-v2.5 | clean | 30 | 0.0818 | [0.0549, 0.1161] | 0.0296 | 0.194 | 0.293 | 0.021 |
| prisma-v2.5 | tel | 30 | 0.0820 | [0.0549, 0.1153] | 0.0282 | 0.197 | 0.301 | 0.022 |
| prisma-v2.5 | tel_snr10 | 30 | 0.1132 | [0.0703, 0.1680] | 0.0510 | 0.179 | 0.292 | 0.020 |
| prisma-v2.5 | tel_snr0 | 30 | 0.1892 | [0.1282, 0.2581] | 0.1028 | 0.193 | 0.281 | 0.021 |
| prisma-v3.0 | clean | 30 | 0.0665 | [0.0481, 0.0867] | 0.0245 | 0.214 | 0.290 | 0.022 |
| prisma-v3.0 | tel | 30 | 0.0784 | [0.0578, 0.1016] | 0.0301 | 0.210 | 0.307 | 0.022 |
| prisma-v3.0 | tel_snr10 | 30 | 0.1303 | [0.0898, 0.1750] | 0.0620 | 0.213 | 0.337 | 0.022 |
| prisma-v3.0 | tel_snr0 | 30 | 0.2582 | [0.1926, 0.3319] | 0.1546 | 0.209 | 0.279 | 0.022 |

---

## Experiment D: Noise & Silence Hallucination

Evaluates 20 five-second clips (10 white noise, 10 silence) to measure false-text hallucination rate.

| Model | Input Type | N | Hallucinated Count | False-Text Rate | Mean Latency (s) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| prisma-v2.5 | Noise & Silence | 20 | 0 | 0.0000 | 0.137 |
| prisma-v3.0 | Noise & Silence | 20 | 0 | 0.0000 | 0.027 |

---

## Experiment F: BFSI Entity Extraction Accuracy

Evaluates exact-match extraction accuracy for payment amounts and due days across 10 synthetic Hinglish banking utterances under 4 degradation conditions.

| Model | Condition | N | Amount Accuracy | Due-Day Accuracy | Both Correct | Mean WER |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| prisma-v2.5 | clean | 10 | 1.0000 | 1.0000 | 1.0000 | 0.4051 |
| prisma-v2.5 | tel | 10 | 1.0000 | 1.0000 | 1.0000 | 0.3996 |
| prisma-v2.5 | tel_snr10 | 10 | 0.9000 | 1.0000 | 0.9000 | 0.4497 |
| prisma-v2.5 | tel_snr0 | 10 | 0.9000 | 0.9000 | 0.8000 | 0.5018 |
| prisma-v3.0 | clean | 10 | 1.0000 | 1.0000 | 1.0000 | 0.3223 |
| prisma-v3.0 | tel | 10 | 1.0000 | 1.0000 | 1.0000 | 0.3160 |
| prisma-v3.0 | tel_snr10 | 10 | 1.0000 | 1.0000 | 1.0000 | 0.3285 |
| prisma-v3.0 | tel_snr0 | 10 | 0.8000 | 0.9000 | 0.8000 | 0.4630 |
