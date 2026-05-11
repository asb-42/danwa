"""TTS data structures — models for the TTS Podcast plugin."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TTSSegment(BaseModel):
    """A single audio segment in the TTS script."""

    id: str
    speaker_name: str
    speaker_role: str
    voice_id: str
    text: str
    pause_after_ms: int = 0
    is_intro: bool = False
    is_outro: bool = False
    injection_reference: str | None = None  # ID of injection being referenced
    style_hint: str = ""  # Natural language style hint for MiMo TTS


class TTSScript(BaseModel):
    """Ordered list of segments forming a complete podcast episode.

    Produced by :class:`TTSScriptEngine` and consumed by
    :class:`EdgeTTSRenderer`.
    """

    segments: list[TTSSegment] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    # metadata keys: topic, total_segments, estimated_duration_ms
