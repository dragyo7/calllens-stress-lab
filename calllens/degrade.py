"""Audio signal processing and telephony degradation pipeline.

Conditions:
- clean: Original normalized 16 kHz mono PCM16 audio.
- tel:
  1. Bandpass filter: 300–3400 Hz (telephony bandwidth)
  2. Resample to 8 kHz (G.711 standard)
  3. Mu-law companding encode/decode (8-bit PCM)
  4. Resample back to 16 kHz (STT model contract)
- tel_snr10:
  Deterministic white Gaussian noise at 10 dB SNR + telephony chain
- tel_snr0:
  Deterministic white Gaussian noise at 0 dB SNR + telephony chain
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Literal

import numpy as np
import scipy.signal as signal
import soundfile as sf

ConditionType = Literal["clean", "tel", "tel_snr10", "tel_snr0"]


def normalize_audio(audio: np.ndarray) -> np.ndarray:
    """Normalize audio to peak amplitude between -1.0 and 1.0."""
    max_val = np.max(np.abs(audio))
    if max_val > 1e-6:
        return audio / max_val * 0.95
    return audio


def compute_rms(audio: np.ndarray) -> float:
    """Computes Root-Mean-Square (RMS) amplitude of audio array."""
    if len(audio) == 0:
        return 0.0
    return float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))


def compute_snr_db(signal_arr: np.ndarray, noise_arr: np.ndarray) -> float:
    """Computes measured Signal-to-Noise Ratio (SNR) in decibels."""
    s_rms = compute_rms(signal_arr)
    n_rms = compute_rms(noise_arr)
    if n_rms < 1e-12:
        return 100.0  # Essentially infinite SNR
    if s_rms < 1e-12:
        return -100.0
    return float(20.0 * np.log10(s_rms / n_rms))


def generate_gaussian_noise(signal_arr: np.ndarray, target_snr_db: float, seed: int) -> np.ndarray:
    """Generates white Gaussian noise scaled to achieve target SNR against the signal."""
    rng = np.random.RandomState(seed)
    raw_noise = rng.standard_normal(len(signal_arr)).astype(np.float32)

    signal_rms = compute_rms(signal_arr)
    noise_rms = compute_rms(raw_noise)

    if signal_rms < 1e-6 or noise_rms < 1e-6:
        return np.zeros_like(signal_arr)

    # target_snr_db = 20 * log10(signal_rms / target_noise_rms)
    # target_noise_rms = signal_rms / (10 ** (target_snr_db / 20))
    target_noise_rms = signal_rms / (10.0 ** (target_snr_db / 20.0))
    scaling = target_noise_rms / noise_rms
    return (raw_noise * scaling).astype(np.float32)


def mulaw_encode_decode(audio: np.ndarray, mu: int = 255) -> np.ndarray:
    """Applies standard G.711 mu-law 8-bit companding encode and decode using NumPy.

    F = f(x) = sgn(x) * ln(1 + mu * |x|) / ln(1 + mu)
    quantized to 8 bits [-128, 127] and expanded back.
    """
    x = np.clip(audio, -1.0, 1.0)
    sign = np.sign(x)
    # Mu-law compression
    compressed = sign * np.log1p(mu * np.abs(x)) / np.log1p(mu)
    # 8-bit quantization (256 discrete levels)
    quantized = np.round(compressed * 127.0).astype(np.int8)
    # De-quantize
    dequant = quantized.astype(np.float32) / 127.0
    # Mu-law expansion
    expanded = np.sign(dequant) * (1.0 / mu) * ((1.0 + mu) ** np.abs(dequant) - 1.0)
    return expanded.astype(np.float32)


def apply_bandpass_filter(audio: np.ndarray, sr: int = 16000, low_hz: float = 300.0, high_hz: float = 3400.0) -> np.ndarray:
    """Butterworth bandpass filter for telephony passband 300–3400 Hz."""
    nyq = 0.5 * sr
    low = low_hz / nyq
    high = high_hz / nyq
    # 4th-order butterworth bandpass
    b, a = signal.butter(4, [low, high], btype="band")
    filtered = signal.filtfilt(b, a, audio)
    return filtered.astype(np.float32)


def apply_telephony_channel(audio_16k: np.ndarray) -> np.ndarray:
    """Executes the telephony degradation pipeline:

    1. Bandpass 300-3400 Hz at 16 kHz
    2. Resample to 8 kHz
    3. Apply G.711 mu-law 8-bit companding round-trip
    4. Resample back to 16 kHz for STT engine contract
    """
    # 1. Bandpass filter
    bp = apply_bandpass_filter(audio_16k, sr=16000, low_hz=300.0, high_hz=3400.0)

    # 2. Resample to 8 kHz (polyphase resampling: down by 2)
    audio_8k = signal.resample_poly(bp, up=1, down=2).astype(np.float32)

    # 3. Mu-law round-trip at 8 kHz
    mulaw_8k = mulaw_encode_decode(audio_8k)

    # 4. Resample back to 16 kHz (up by 2)
    audio_16k_out = signal.resample_poly(mulaw_8k, up=2, down=1).astype(np.float32)

    # Align length in case polyphase resample drifted by 1 sample
    if len(audio_16k_out) > len(audio_16k):
        audio_16k_out = audio_16k_out[:len(audio_16k)]
    elif len(audio_16k_out) < len(audio_16k):
        audio_16k_out = np.pad(audio_16k_out, (0, len(audio_16k) - len(audio_16k_out)))

    # Clip to valid audio range [-1.0, 1.0] to prevent filter ringing overshoot
    audio_16k_out = np.clip(audio_16k_out, -1.0, 1.0)

    return audio_16k_out



def get_deterministic_seed(clip_id: str) -> int:
    """Generates a stable integer seed from clip ID."""
    md5_hash = hashlib.md5(clip_id.encode("utf-8")).hexdigest()
    return int(md5_hash[:8], 16)


def degrade_audio(
    audio: np.ndarray,
    condition: ConditionType,
    clip_id: str = "sample",
    sr: int = 16000,
) -> np.ndarray:
    """Applies specified degradation condition to 16 kHz mono audio array."""
    if audio.ndim > 1:
        audio = np.mean(audio, axis=-1)  # Convert to mono if needed

    audio = audio.astype(np.float32)

    if condition == "clean":
        return normalize_audio(audio)

    seed = get_deterministic_seed(clip_id)

    if condition == "tel":
        norm = normalize_audio(audio)
        return apply_telephony_channel(norm)

    elif condition == "tel_snr10":
        norm = normalize_audio(audio)
        noise = generate_gaussian_noise(norm, target_snr_db=10.0, seed=seed)
        noisy = norm + noise
        return apply_telephony_channel(noisy)

    elif condition == "tel_snr0":
        norm = normalize_audio(audio)
        noise = generate_gaussian_noise(norm, target_snr_db=0.0, seed=seed)
        noisy = norm + noise
        return apply_telephony_channel(noisy)

    else:
        raise ValueError(f"Unknown condition: {condition}. Must be one of clean, tel, tel_snr10, tel_snr0")


def process_audio_file(
    input_path: Path | str,
    output_path: Path | str,
    condition: ConditionType,
    clip_id: str | None = None,
) -> Path:
    """Reads audio file, converts to 16kHz mono PCM16, degrades, and writes output."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if clip_id is None:
        clip_id = input_path.stem

    audio, sr = sf.read(str(input_path), dtype="float32")

    # Resample to 16kHz if needed
    if sr != 16000:
        num_samples = int(round(len(audio) * 16000 / sr))
        audio = signal.resample(audio, num_samples)
        sr = 16000

    if audio.ndim > 1:
        audio = np.mean(audio, axis=-1)

    # Enforce 30-second duration limit
    max_samples = 30 * sr
    if len(audio) > max_samples:
        audio = audio[:max_samples]

    degraded = degrade_audio(audio, condition=condition, clip_id=clip_id, sr=sr)

    # Write as standard 16kHz mono PCM16 WAV
    sf.write(str(output_path), degraded, sr, subtype="PCM_16")
    return output_path


def suppress_noise(
    audio: np.ndarray,
    sr: int = 16000,
    alpha: float = 1.8,
    beta: float = 0.05,
) -> np.ndarray:
    """Applies frequency-domain spectral subtraction noise suppression to an audio signal.

    Parameters:
    - audio: 1D NumPy array representing audio samples.
    - sr: Sample rate (default 16000 Hz).
    - alpha: Over-subtraction factor (controls aggressiveness of noise reduction).
    - beta: Spectral floor coefficient (prevents negative spectral power and musical noise).

    Returns:
    - Cleaned 1D float32 audio array bounded to [-1.0, 1.0].
    """
    if audio.ndim > 1:
        audio = np.mean(audio, axis=-1)

    if len(audio) < 512:
        return audio.astype(np.float32)

    # 512-point STFT with 75% overlap for fine temporal/spectral resolution
    f, times, Zxx = signal.stft(audio, fs=sr, nperseg=512, noverlap=384)
    mag = np.abs(Zxx)
    phase = np.angle(Zxx)

    # Estimate noise spectrum from the lowest 10% energy frames (stationary background noise floor)
    frame_energy = np.mean(mag ** 2, axis=0)
    k_frames = max(1, len(frame_energy) // 10)
    noise_frames = np.argsort(frame_energy)[:k_frames]
    noise_profile = np.mean(mag[:, noise_frames], axis=1, keepdims=True)

    # Spectral subtraction with spectral floor
    clean_mag = np.maximum(mag - alpha * noise_profile, beta * mag)
    Zxx_clean = clean_mag * np.exp(1j * phase)

    _, cleaned = signal.istft(Zxx_clean, fs=sr, nperseg=512, noverlap=384)

    # Align length to match input array exactly
    if len(cleaned) > len(audio):
        cleaned = cleaned[:len(audio)]
    elif len(cleaned) < len(audio):
        cleaned = np.pad(cleaned, (0, len(audio) - len(cleaned)))

    return np.clip(cleaned, -1.0, 1.0).astype(np.float32)
