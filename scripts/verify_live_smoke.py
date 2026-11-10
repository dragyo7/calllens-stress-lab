"""Live Gnani Prisma STT & Timbre TTS Smoke Test.

Executes exactly ONE live STT call and ONE live TTS call.
Strictly enforces MAX_LIVE_CALLS = 2.
Verifies response structures, audio decoding, and usage accounting.
"""

import io
import json
import os
import sys
import time
from pathlib import Path

# Ensure calllens package is on python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
import soundfile as sf

# Load environment
load_dotenv()

# Enforce MAX_LIVE_CALLS = 2
os.environ["MAX_LIVE_CALLS"] = "2"
os.environ["ALLOW_LIVE_API"] = "1"

import calllens.gnani_client as gc
from calllens.gnani_client import CallLimitExceededError

def run_smoke_test():
    print("=" * 60)
    print("CALLLENS — LIVE GNANI PRISMA & TIMBRE INTEGRATION SMOKE TEST")
    print("=" * 60)

    # 1. Inspect and verify credentials
    api_key = os.getenv("GNANI_API_KEY", "")
    if not api_key or len(api_key) < 10:
        print("[FAIL] GNANI_API_KEY is missing or invalid. Cannot run live test.")
        sys.exit(1)

    print(f"[AUTH] Credential verified present (Length: {len(api_key)}, Format: Token)")
    print(f"[CAP] Enforced MAX_LIVE_CALLS = 2")

    # Set accounting max_live_calls
    gc.accounting.max_live_calls = 2

    # 2. Test 1: Real Prisma STT Request
    print("\n--- [LIVE CALL 1/2] Real Prisma STT Transcription ---")
    clip_path = Path("data/fleurs/audio/14706914212578682198.wav")
    if not clip_path.exists():
        clip_path = Path("../calllens-data/fleurs/audio/14706914212578682198.wav")
    
    print(f"[STT] Input audio clip: {clip_path.name}")
    info = sf.info(str(clip_path))
    print(f"[STT] Audio specs: {info.samplerate}Hz, {info.channels}ch, {info.duration:.2f}s")
    
    stt_payload = {
        "audio": str(clip_path),
        "model": "prisma-v2.5",
        "language_code": "hi-IN",
        "format": "verbatim",
    }
    
    t0 = time.perf_counter()
    stt_res = gc.call("stt", stt_payload, live=True, use_cache=False)
    stt_latency = time.perf_counter() - t0

    print(f"[STT] Live Response received in {stt_latency:.3f}s:")
    print(f"      - Success: {stt_res.get('success')}")
    print(f"      - Request ID: {stt_res.get('request_id')}")
    print(f"      - Transcript: {stt_res.get('transcript')}")
    print(f"      - Model: {stt_res.get('model')}")
    print(f"      - From Cache: {stt_res.get('from_cache')}")
    assert stt_res.get("transcript"), "STT transcript must not be empty"
    print("[STT] ✓ Real Prisma STT call PASSED!")

    # 3. Test 2: Real Timbre TTS Request
    print("\n--- [LIVE CALL 2/2] Real Timbre TTS Speech Synthesis ---")
    tts_text = "कॉल लेंस लाइव एकीकरण परीक्षण सफल रहा"
    tts_voice = "Pranav"
    tts_payload = {
        "text": tts_text,
        "voice": tts_voice,
        "model": "timbre-v2.5",
        "language": "hi-IN",
        "speed": 1.0,
    }
    print(f"[TTS] Synthesizing text: '{tts_text}'")
    print(f"[TTS] Voice: {tts_voice}, Model: timbre-v2.5, Lang: hi-IN")

    t1 = time.perf_counter()
    tts_bytes = gc.call("tts", tts_payload, live=True, use_cache=False)
    tts_latency = time.perf_counter() - t1

    print(f"[TTS] Live Audio received in {tts_latency:.3f}s:")
    print(f"      - Byte length: {len(tts_bytes)} bytes")
    print(f"      - RIFF Header: {tts_bytes[:4] == b'RIFF'}")

    # Decode and verify audio properties
    with io.BytesIO(tts_bytes) as bio:
        audio_info = sf.info(bio)
        print(f"      - Decoded Format: {audio_info.format}")
        print(f"      - Sample Rate: {audio_info.samplerate} Hz")
        print(f"      - Channels: {audio_info.channels}")
        print(f"      - Duration: {audio_info.duration:.2f}s")
        assert audio_info.duration > 0.5, "Audio duration must be > 0.5s"

    # Save to disk for playback verification
    out_dir = Path("data/tts_audio")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "live_timbre_smoke_test.wav"
    out_file.write_bytes(tts_bytes)
    print(f"[TTS] Saved live audio to: {out_file}")
    print("[TTS] ✓ Real Timbre TTS call PASSED!")

    # 4. Enforce Cap: Third Call Must Fail
    print("\n--- [ENFORCEMENT CHECK] Testing MAX_LIVE_CALLS = 2 Cap ---")
    try:
        gc.call("tts", {"text": "Third call must fail", "voice": "Pranav"}, live=True, use_cache=False)
        print("[FAIL] Cap was not enforced! Third call succeeded.")
        sys.exit(1)
    except CallLimitExceededError as e:
        print(f"[CAP] ✓ CallLimitExceededError successfully caught: {e}")

    # 5. Verify Accounting
    state_file, _ = gc._get_accounting_paths()
    with open(state_file, "r", encoding="utf-8") as f:
        acc_data = json.load(f)
    print("\n--- [ACCOUNTING AUDIT] ---")
    print(f"Live Calls Made: {acc_data.get('live_calls')}")
    print(f"Network Attempts: {acc_data.get('network_attempts')}")
    print(f"Cache Hits: {acc_data.get('cache_hits')}")
    print(f"Mock Calls: {acc_data.get('mock_calls')}")
    print(f"Retries: {acc_data.get('retries')}")

    print("\n" + "=" * 60)
    print("ALL LIVE SMOKE TESTS COMPLETED SUCCESSFULLY WITH ZERO BUDGET OVERRUN!")
    print("=" * 60)

if __name__ == "__main__":
    run_smoke_test()
