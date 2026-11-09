"""Evaluation metrics for ASR, noise hallucination, and latency.

Provides:
- Unicode NFC and punctuation text normalization
- Word Error Rate (WER) via jiwer
- Character Error Rate (CER) via jiwer
- False-text rate for noise/silence hallucination
- Latency percentiles (P50, P95) and Real-Time Factor (RTF)
- Clip-level bootstrap confidence intervals (1,000 resamples, seed 0)
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Sequence

import jiwer
import numpy as np


# Punctuation to remove: ASCII punctuation + Devanagari danda/double danda + common symbols
PUNCT_PATTERN = re.compile(r"[\.,\?!:;\"'״׳\(\)\[\]\{\}/\\*_\-~`@#\$%\^&+=|।॥—–…«»]")
WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_text(text: str | None) -> str:
    """Normalizes Hindi and Hinglish text for fair ASR evaluation:

    1. Unicode NFC normalization
    2. Lowercase (for Latin/Hinglish characters)
    3. Remove punctuation including Devanagari danda (|) and double danda (||)
    4. Collapse contiguous whitespace and strip
    """
    if text is None:
        return ""

    # 1. Unicode NFC
    s = unicodedata.normalize("NFC", text)

    # 2. Lowercase
    s = s.lower()

    # 3. Strip punctuation
    s = PUNCT_PATTERN.sub(" ", s)

    # 4. Collapse whitespace
    s = WHITESPACE_PATTERN.sub(" ", s).strip()

    return s


def compute_wer(reference: str, hypothesis: str) -> float:
    """Computes Word Error Rate (WER) using jiwer on normalized strings.

    If reference is empty:
    - If hypothesis is also empty -> WER is 0.0
    - If hypothesis is non-empty -> WER is 1.0 (all insertions)
    """
    ref_norm = normalize_text(reference)
    hyp_norm = normalize_text(hypothesis)

    if not ref_norm:
        return 0.0 if not hyp_norm else 1.0

    return float(jiwer.wer(ref_norm, hyp_norm))


def compute_cer(reference: str, hypothesis: str) -> float:
    """Computes Character Error Rate (CER) using jiwer on normalized strings.

    If reference is empty:
    - If hypothesis is also empty -> CER is 0.0
    - If hypothesis is non-empty -> CER is 1.0
    """
    ref_norm = normalize_text(reference)
    hyp_norm = normalize_text(hypothesis)

    if not ref_norm:
        return 0.0 if not hyp_norm else 1.0

    return float(jiwer.cer(ref_norm, hyp_norm))


def compute_false_text_rate(hypotheses: Sequence[str]) -> float:
    """Computes the proportion of clips that generated non-whitespace text.

    Used for Experiment D (noise and silence hallucination).
    """
    if not hypotheses:
        return 0.0
    hallucinated = sum(1 for h in hypotheses if normalize_text(h) != "")
    return float(hallucinated / len(hypotheses))


def compute_latency_stats(latencies: Sequence[float], durations: Sequence[float] | None = None) -> dict[str, float]:
    """Computes median (P50), 95th percentile (P95), and mean Real-Time Factor (RTF)."""
    if not latencies:
        return {"p50": 0.0, "p95": 0.0, "mean": 0.0, "rtf": 0.0, "n": 0}

    arr = np.array(latencies, dtype=np.float64)
    p50 = float(np.percentile(arr, 50))
    p95 = float(np.percentile(arr, 95))
    mean = float(np.mean(arr))

    rtf = 0.0
    if durations and len(durations) == len(latencies):
        dur_arr = np.array(durations, dtype=np.float64)
        valid = dur_arr > 1e-3
        if np.any(valid):
            rtf = float(np.mean(arr[valid] / dur_arr[valid]))

    return {
        "p50": round(p50, 4),
        "p95": round(p95, 4),
        "mean": round(mean, 4),
        "rtf": round(rtf, 4),
        "n": len(latencies),
    }


def compute_bootstrap_ci(
    values: Sequence[float],
    n_resamples: int = 1000,
    seed: int = 0,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """Computes non-parametric bootstrap confidence interval at the clip level.

    Parameters
    ----------
    values : Sequence[float]
        Metric values per clip (e.g. WER per clip).
    n_resamples : int
        Number of bootstrap iterations (default: 1000).
    seed : int
        RNG seed for reproducibility (default: 0).
    alpha : float
        Significance level (default: 0.05 for 95% CI).

    Returns
    -------
    (mean, ci_lower, ci_upper)
    """
    if not values:
        return 0.0, 0.0, 0.0

    arr = np.array(values, dtype=np.float64)
    n = len(arr)
    if n == 1:
        return float(arr[0]), float(arr[0]), float(arr[0])

    rng = np.random.RandomState(seed)
    # Resample with replacement at clip level
    resampled_indices = rng.randint(0, n, size=(n_resamples, n))
    bootstrap_means = np.mean(arr[resampled_indices], axis=1)

    mean_val = float(np.mean(arr))
    ci_lower = float(np.percentile(bootstrap_means, 100.0 * (alpha / 2.0)))
    ci_upper = float(np.percentile(bootstrap_means, 100.0 * (1.0 - alpha / 2.0)))

    return round(mean_val, 4), round(ci_lower, 4), round(ci_upper, 4)
