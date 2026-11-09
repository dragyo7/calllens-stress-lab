"""Unit tests for calllens/metrics.py."""

import pytest
from calllens.metrics import (
    compute_bootstrap_ci,
    compute_cer,
    compute_false_text_rate,
    compute_latency_stats,
    compute_wer,
    normalize_text,
)


def test_wer_specification_example():
    """Verify exact WER on brief requirement: Reference: a b c, Hypothesis: a x c -> 0.333..."""
    ref = "a b c"
    hyp = "a x c"
    wer = compute_wer(ref, hyp)
    assert pytest.approx(1 / 3, rel=1e-3) == wer


def test_text_normalization():
    """Verify Unicode NFC, punctuation stripping (including danda), and whitespace normalization."""
    raw = "  नमस्ते,  दुनिया! यह एक   परीक्षण है।  "
    norm = normalize_text(raw)
    assert norm == "नमस्ते दुनिया यह एक परीक्षण है"
    assert "।" not in norm
    assert "," not in norm
    assert "!" not in norm


def test_cer_calculation():
    """Verify Character Error Rate (CER)."""
    ref = "नमस्ते"
    hyp = "नमस्ते"
    assert compute_cer(ref, hyp) == 0.0

    hyp_diff = "नमस्तेजी"
    assert compute_cer(ref, hyp_diff) > 0.0


def test_false_text_rate():
    """Verify false-text rate computation for noise/silence hallucination."""
    hypotheses = ["", "   ", "कुछ शब्द", "  ", "hallucination"]
    # 2 out of 5 non-empty
    ftr = compute_false_text_rate(hypotheses)
    assert ftr == 0.4


def test_latency_statistics():
    """Verify P50, P95 and RTF calculation."""
    latencies = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    durations = [2.0] * 10
    stats = compute_latency_stats(latencies, durations)
    assert stats["n"] == 10
    assert 0.5 <= stats["p50"] <= 0.6
    assert stats["p95"] >= 0.9
    assert stats["rtf"] > 0


def test_bootstrap_confidence_intervals():
    """Verify clip-level bootstrap with seed 0 produces deterministic 95% CI."""
    values = [0.10, 0.12, 0.11, 0.15, 0.09, 0.13, 0.14, 0.11, 0.10, 0.12]
    mean, lower, upper = compute_bootstrap_ci(values, n_resamples=1000, seed=0)

    assert lower <= mean <= upper
    assert 0.09 <= lower <= 0.12
    assert 0.11 <= upper <= 0.14

    # Rerun with same seed must be 100% deterministic
    mean2, lower2, upper2 = compute_bootstrap_ci(values, n_resamples=1000, seed=0)
    assert (mean, lower, upper) == (mean2, lower2, upper2)
