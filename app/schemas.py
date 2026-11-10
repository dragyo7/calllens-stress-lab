"""Pydantic request and response schemas for CallLens API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StressRequest(BaseModel):
    clip_id: str | None = Field(default=None, description="Clip ID from dataset")
    condition: str = Field(default="clean", description="Acoustic condition: clean, tel, tel_snr10, tel_snr0")
    live: int = Field(default=0, description="1 for live API call, 0 for replay of recorded live runs")
    audio_base64: str | None = Field(default=None, description="Optional raw audio base64 encoded")
    allow_mock: bool | None = Field(default=None, description="Allow mock fixture fallback (test-only)")
    denoise: bool = Field(default=False, description="Apply spectral subtraction noise suppression pre-filter")


class STTRequest(BaseModel):
    clip_id: str | None = Field(default=None, description="Clip ID from preloaded dataset")
    audio_base64: str | None = Field(default=None, description="Base64 encoded audio bytes")
    model: str = Field(default="prisma-v2.5", description="Prisma v2.5 or prisma-v3.0")
    language_code: str = Field(default="hi-IN", description="BCP-47 language code")
    format: str = Field(default="verbatim", description="verbatim, transcribe, or codemix")
    live: int = Field(default=0, description="1 for live API call, 0 for mock/cache")
    mock_transcript: str | None = Field(default=None, description="Optional mock transcript for testing")


class TTSRequest(BaseModel):
    text: str = Field(..., description="Text to synthesize into speech")
    voice: str = Field(default="Pranav", description="Voice identifier (e.g. Pranav, Kaveri, Ishaan)")
    model: str = Field(default="timbre-v2.5", description="TTS model (timbre-v2.5 or timbre-v2.0)")
    language: str = Field(default="hi-IN", description="Language code")
    speed: float = Field(default=1.0, description="Speaking rate (0.85 to 1.15)")
    live: int = Field(default=0, description="1 for live API call, 0 for mock/cache")


class FollowupProcessRequest(BaseModel):
    clip_id: str | None = Field(default=None, description="Preloaded clip or scenario ID")
    scenario_id: str | None = Field(default=None, description="Preloaded scenario ID alias")
    audio_base64: str | None = Field(default=None, description="Base64 encoded audio recording")
    model: str = Field(default="prisma-v3.0", description="ASR model for transcription")
    customer_name: str | None = Field(default=None, description="Optional customer name hint")
    customer: str | None = Field(default=None, description="Customer alias")
    live: int = Field(default=0, description="1 for live API call, 0 for mock/cache")
    mock_transcript: str | None = Field(default=None, description="Optional mock transcript for testing")
    transcript: str | None = Field(default=None, description="Transcript alias")
    language: str = Field(default="hi-IN", description="Language code")


class FollowupConfirmRequest(BaseModel):
    customer_name: str | None = Field(default=None, description="Customer name confirmed by operator")
    customer: str | None = Field(default=None, description="Customer alias")
    amount: int | float | None = Field(default=None, description="Confirmed outstanding amount (INR)")
    due_date: str | None = Field(default=None, description="Confirmed due date")
    ptp_date: str | None = Field(default=None, description="Confirmed promise-to-pay date")
    concern: str | None = Field(default="none", description="Confirmed customer reason or concern")
    call_summary: str | None = Field(default=None, description="Confirmed call summary")
    summary: str | None = Field(default=None, description="Call summary alias")
    reminder_text: str = Field(..., description="Reviewed reminder text for speech synthesis")
    voice: str = Field(default="Pranav", description="Timbre voice for reminder")
    speed: float = Field(default=1.0, description="Speaking rate")
    language: str = Field(default="hi-IN", description="Language")
    live: int = Field(default=0, description="1 for live API call, 0 for mock/cache")
    operator_notes: str | None = Field(default=None, description="Audit notes from operator")

