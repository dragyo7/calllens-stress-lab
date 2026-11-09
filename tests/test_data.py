"""Tests for dataset and synthetic data validation."""

import json
import os
from pathlib import Path
import pytest
import soundfile as sf


@pytest.fixture
def data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", "../calllens-data"))


def test_data_dir_is_outside_repo():
    """Verify that the data directory is located outside the Git repository."""
    repo_root = Path(__file__).resolve().parent.parent
    data_dir = Path(os.getenv("DATA_DIR", "../calllens-data")).resolve()
    # Confirm data_dir is not within repo_root
    assert not data_dir.is_relative_to(repo_root), f"DATA_DIR {data_dir} must be outside {repo_root}"


def test_fleurs_manifest_and_audio(data_dir):
    """Verify FLEURS dataset manifest, audio format, and attribution."""
    manifest_path = data_dir / "fleurs" / "manifest.json"
    assert manifest_path.exists(), "FLEURS manifest must exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert len(manifest) == 30, "Must contain exactly 30 clips"

    for clip in manifest:
        assert "raw_transcription" in clip and len(clip["raw_transcription"]) > 0
        assert "CC BY 4.0" in clip.get("attribution", "")
        file_path = Path(clip["file_path"])
        assert file_path.exists()

        info = sf.info(str(file_path))
        assert info.samplerate == 16000
        assert info.channels == 1
        assert info.subtype == "PCM_16"
        assert info.duration <= 28.0


def test_noise_and_silence_dataset(data_dir):
    """Verify Experiment D noise and silence clips."""
    manifest_path = data_dir / "noise_silence" / "manifest.json"
    assert manifest_path.exists()

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert len(manifest) == 20
    noise_count = sum(1 for c in manifest if c["type"] == "noise")
    silence_count = sum(1 for c in manifest if c["type"] == "silence")
    assert noise_count == 10
    assert silence_count == 10

    for clip in manifest:
        info = sf.info(clip["file_path"])
        assert info.samplerate == 16000
        assert info.channels == 1
        assert info.subtype == "PCM_16"
        assert abs(info.duration - 5.0) < 0.1


def test_bfsi_utterances_and_ground_truth(data_dir):
    """Verify Experiment F synthetic utterances and ground truth."""
    manifest_path = data_dir / "bfsi" / "manifest.json"
    gt_path = data_dir / "bfsi" / "ground_truth.json"

    # Prior to Gate G2 live regeneration, fallback to bfsi_mock if separated
    if not manifest_path.exists() and (data_dir / "bfsi_mock" / "manifest.json").exists():
        manifest_path = data_dir / "bfsi_mock" / "manifest.json"
        gt_path = data_dir / "bfsi_mock" / "ground_truth.json"

    assert manifest_path.exists()
    assert gt_path.exists()

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    with open(gt_path, "r", encoding="utf-8") as f:
        gt = json.load(f)

    assert len(manifest) == 10
    assert len(gt) == 10

    for m, g in zip(manifest, gt):
        assert m["clip_id"] == g["clip_id"]
        assert m["amount"] == g["amount"]
        assert m["due_day"] == g["due_day"]
        audio_p = Path(m["file_path"])
        if not audio_p.exists() and (data_dir / "bfsi_mock" / audio_p.name).exists():
            audio_p = data_dir / "bfsi_mock" / audio_p.name
        assert audio_p.exists()
