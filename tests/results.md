# CallLens Stress Lab — Benchmark Results

> Generated on: 2026-11-09 14:42:33 UTC

## Summary Overview

This report documents experimental evaluations comparing **Gnani Prisma v2.5** and **Gnani Prisma v3.0** under clean and simulated telephony degradation conditions.

**Important Methodology Notice:** Telephony channel degradation was applied deterministically to read speech (FLEURS) and synthetic TTS speech (Timbre v2.5). This evaluates acoustic robustness under simulated channel degradation and noise; it does not replace testing on real human customer call center recordings.

---

## Experiment A: Hindi ASR Telephony Robustness (FLEURS)

Evaluates 30 FLEURS Hindi India clips (CC BY 4.0, <= 28 seconds) across 4 acoustic conditions with 95% clip-level bootstrap confidence intervals (1,000 resamples, seed 0).

| Model | Condition | N | Mean WER | 95% CI (WER) | Mean CER | P50 Latency (s) | P95 Latency (s) | Mean RTF |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| prisma-v2.5 | clean | 30 | 0.0000 | [0.0000, 0.0000] | 0.0000 | 0.480 | 0.480 | 0.052 |
| prisma-v2.5 | tel | 30 | 0.0000 | [0.0000, 0.0000] | 0.0000 | 0.480 | 0.480 | 0.052 |
| prisma-v2.5 | tel_snr10 | 30 | 0.0536 | [0.0457, 0.0622] | 0.0497 | 0.480 | 0.480 | 0.052 |
| prisma-v2.5 | tel_snr0 | 30 | 0.1073 | [0.0914, 0.1244] | 0.0847 | 0.480 | 0.480 | 0.052 |
| prisma-v3.0 | clean | 30 | 0.0000 | [0.0000, 0.0000] | 0.0000 | 0.480 | 0.480 | 0.052 |
| prisma-v3.0 | tel | 30 | 0.0000 | [0.0000, 0.0000] | 0.0000 | 0.480 | 0.480 | 0.052 |
| prisma-v3.0 | tel_snr10 | 30 | 0.0000 | [0.0000, 0.0000] | 0.0000 | 0.480 | 0.480 | 0.052 |
| prisma-v3.0 | tel_snr0 | 30 | 0.0536 | [0.0457, 0.0622] | 0.0502 | 0.480 | 0.480 | 0.052 |

---

## Experiment D: Noise & Silence Hallucination

Evaluates 20 five-second clips (10 white noise, 10 silence) to measure false-text hallucination rate.

| Model | Input Type | N | Hallucinated Count | False-Text Rate | Mean Latency (s) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| prisma-v2.5 | Noise & Silence | 20 | 0 | 0.0000 | 0.480 |
| prisma-v3.0 | Noise & Silence | 20 | 0 | 0.0000 | 0.480 |

---

## Experiment F: BFSI Entity Extraction Accuracy

Evaluates exact-match extraction accuracy for payment amounts and due days across 10 synthetic Hinglish banking utterances under 4 degradation conditions.

| Model | Condition | N | Amount Accuracy | Due-Day Accuracy | Both Correct | Mean WER |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| prisma-v2.5 | clean | 10 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| prisma-v2.5 | tel | 10 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| prisma-v2.5 | tel_snr10 | 10 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| prisma-v2.5 | tel_snr0 | 10 | 0.9000 | 1.0000 | 0.9000 | 0.0071 |
| prisma-v3.0 | clean | 10 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| prisma-v3.0 | tel | 10 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| prisma-v3.0 | tel_snr10 | 10 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| prisma-v3.0 | tel_snr0 | 10 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
