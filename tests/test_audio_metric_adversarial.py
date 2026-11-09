"""Phase F: Audio Pipeline & Metric Adversarial Edge-Case Tests."""

import numpy as np
import pytest

from calllens import degrade, extract, metrics


def test_audio_edge_case_all_zero_silence():
    """Verify degrade_audio handles pure digital silence without NaN or crash."""
    silence = np.zeros(16000, dtype=np.float32)
    for cond in ["clean", "tel", "tel_snr10", "tel_snr0"]:
        out = degrade.degrade_audio(silence, condition=cond, clip_id="silence_test")
        assert len(out) == 16000
        assert not np.isnan(out).any()
        assert not np.isinf(out).any()


def test_audio_edge_case_very_low_amplitude():
    """Verify degrade_audio handles near-zero amplitude signal (1e-6) gracefully."""
    low_amp = np.ones(16000, dtype=np.float32) * 1e-6
    out = degrade.degrade_audio(low_amp, condition="tel", clip_id="low_amp_test")
    assert not np.isnan(out).any()


def test_audio_edge_case_clipping_full_scale():
    """Verify audio with values >= 1.0 or <= -1.0 does not produce overflow or NaN."""
    clipped = np.array([2.5, -3.0, 1.8, -1.9] * 4000, dtype=np.float32)
    out = degrade.degrade_audio(clipped, condition="tel", clip_id="clipped_test")
    assert np.max(np.abs(out)) <= 1.0
    assert not np.isnan(out).any()


def test_audio_edge_case_stereo_input_downmixed():
    """Verify 2D stereo input (N, 2) is automatically converted to mono 1D array."""
    stereo = np.column_stack([np.sin(np.linspace(0, 1, 16000)), np.cos(np.linspace(0, 1, 16000))]).astype(np.float32)
    out = degrade.degrade_audio(stereo, condition="clean")
    assert out.ndim == 1
    assert len(out) == 16000


def test_audio_edge_case_odd_sample_length():
    """Verify odd sample count (e.g. 15999 samples) resamples and returns matched length."""
    odd_arr = np.random.RandomState(42).randn(15999).astype(np.float32) * 0.1
    out = degrade.degrade_audio(odd_arr, condition="tel", clip_id="odd_test")
    assert len(out) == 15999
    assert not np.isnan(out).any()


def test_five_hand_calculated_wer_examples():
    """Independently verify 5 hand-calculated WER cases:

    1. Single substitution: ref='a b c', hyp='a x c' -> 1/3 (0.333...)
    2. Single insertion: ref='a b c', hyp='a b c d' -> 1/3 (0.333...)
    3. Single deletion: ref='a b c', hyp='a c' -> 1/3 (0.333...)
    4. Complete deletion: ref='a b c', hyp='' -> 3/3 (1.0)
    5. Complete substitution: ref='one two', hyp='three four' -> 2/2 (1.0)
    """
    assert pytest.approx(1 / 3, rel=1e-3) == metrics.compute_wer("a b c", "a x c")
    assert pytest.approx(1 / 3, rel=1e-3) == metrics.compute_wer("a b c", "a b c d")
    assert pytest.approx(1 / 3, rel=1e-3) == metrics.compute_wer("a b c", "a c")
    assert metrics.compute_wer("a b c", "") == 1.0
    assert metrics.compute_wer("one two", "three four") == 1.0


def test_wer_empty_reference_handling():
    """Verify empty reference behavior."""
    assert metrics.compute_wer("", "") == 0.0
    assert metrics.compute_wer("", "some hallucinated text") == 1.0


def test_wer_repeated_words():
    """Verify repeated words penalization: ref='namaste namaste', hyp='namaste' -> WER = 0.5."""
    assert pytest.approx(0.5, rel=1e-3) == metrics.compute_wer("namaste namaste", "namaste")


def test_bootstrap_ci_clip_level_unit():
    """Verify bootstrap resamples at the clip level, not word level."""
    # 5 clips with WERs
    clip_wers = [0.0, 0.1, 0.2, 0.3, 0.4]
    mean, lower, upper = metrics.compute_bootstrap_ci(clip_wers, n_resamples=1000, seed=0)
    assert lower <= mean <= upper
    assert 0.05 <= lower <= 0.25
    assert 0.25 <= upper <= 0.40


def test_extract_adversarial_amounts_and_dates():
    """Verify entity extraction on complex/ambiguous adversarial strings."""
    # Multiple numbers, take the principal amount
    assert extract.extract_amount("लोन 50,000 रुपये है और ब्याज 500 रुपये") == 50000
    # Ambiguous date with extraneous numbers
    assert extract.extract_due_day("खाता 9876543210 का बिल 15 तारीख तक देय") == 15
    # Decimal crore
    assert extract.extract_amount("प्रोजेक्ट फंड ₹0.5 crore") == 5000000
