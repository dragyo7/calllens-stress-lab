"""Tests for audio degradation and telephony signal processing."""

from pathlib import Path
import numpy as np
import pytest
import soundfile as sf

from calllens.degrade import (
    apply_bandpass_filter,
    apply_telephony_channel,
    compute_rms,
    compute_snr_db,
    degrade_audio,
    generate_gaussian_noise,
    mulaw_encode_decode,
    normalize_audio,
    process_audio_file,
)


@pytest.fixture
def test_signals():
    """Generates three distinct signals for SNR validation."""
    sr = 16000
    duration = 2.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False, dtype=np.float32)

    # Signal 1: Pure 1 kHz sine wave
    s1 = 0.5 * np.sin(2 * np.pi * 1000 * t)

    # Signal 2: Harmonic multi-tone (300Hz, 800Hz, 2500Hz)
    s2 = 0.3 * np.sin(2 * np.pi * 300 * t) + 0.2 * np.sin(2 * np.pi * 800 * t) + 0.1 * np.sin(2 * np.pi * 2500 * t)

    # Signal 3: Modulated chirp signal (500Hz to 3000Hz)
    freqs = np.linspace(500, 3000, len(t))
    s3 = 0.4 * np.sin(2 * np.pi * freqs * t)

    return [s1, s2, s3]


def test_snr_tolerance_on_three_signals(test_signals):
    """Verify that generated white noise matches target SNR within +/-0.5 dB across 3 signals."""
    for idx, sig in enumerate(test_signals, 1):
        for target_snr in [10.0, 0.0]:
            noise = generate_gaussian_noise(sig, target_snr_db=target_snr, seed=100 + idx)
            measured_snr = compute_snr_db(sig, noise)
            diff = abs(measured_snr - target_snr)
            assert diff <= 0.5, f"Signal {idx} target {target_snr}dB measured {measured_snr:.2f}dB (diff {diff:.2f}dB > 0.5dB)"


def test_mulaw_roundtrip():
    """Verify mu-law compression and expansion maintains signal integrity."""
    sr = 16000
    t = np.linspace(0, 1.0, sr, endpoint=False, dtype=np.float32)
    orig = 0.6 * np.sin(2 * np.pi * 440 * t)
    processed = mulaw_encode_decode(orig)
    # RMS error from 8-bit quantization should be small (< -35 dB)
    err_rms = compute_rms(orig - processed)
    orig_rms = compute_rms(orig)
    assert err_rms / orig_rms < 0.05


def test_telephony_channel_shape_and_range():
    """Verify telephony channel output matches input length and 16 kHz sample count."""
    arr = np.random.RandomState(42).randn(16000).astype(np.float32) * 0.5
    out = apply_telephony_channel(arr)
    assert len(out) == len(arr)
    assert not np.isnan(out).any()
    assert np.max(np.abs(out)) <= 1.0


def test_deterministic_degrade():
    """Verify that degrade_audio with same clip_id is perfectly deterministic."""
    arr = np.random.RandomState(42).randn(8000).astype(np.float32) * 0.5
    out1 = degrade_audio(arr, condition="tel_snr10", clip_id="clip_001")
    out2 = degrade_audio(arr, condition="tel_snr10", clip_id="clip_001")
    out3 = degrade_audio(arr, condition="tel_snr10", clip_id="clip_002")

    assert np.allclose(out1, out2)
    assert not np.allclose(out1, out3), "Different clip IDs must generate different noise"


def test_process_audio_file(tmp_path):
    """Verify file processing adheres to audio contract (16kHz, mono, PCM16, <=30s)."""
    in_file = tmp_path / "in.wav"
    out_file = tmp_path / "out.wav"

    # Write 35 seconds of 44.1 kHz stereo audio
    sr = 44100
    t = np.linspace(0, 35.0, int(sr * 35.0), endpoint=False)
    stereo = np.column_stack([np.sin(2 * np.pi * 440 * t), np.cos(2 * np.pi * 440 * t)]).astype(np.float32)
    sf.write(str(in_file), stereo, sr)

    # Process to tel_snr0
    process_audio_file(in_file, out_file, condition="tel_snr0", clip_id="test_clip")

    # Verify output properties
    info = sf.info(str(out_file))
    assert info.samplerate == 16000, "Output must be 16kHz"
    assert info.channels == 1, "Output must be mono"
    assert info.subtype == "PCM_16", "Output must be PCM16"
    assert info.duration <= 30.0, "Output duration must not exceed 30 seconds"
