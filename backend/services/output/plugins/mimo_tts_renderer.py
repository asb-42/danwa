"""MiMoTTSRenderer — renders TTSScript to audio via MiMo-V2.5-TTS API.

MiMo TTS uses an OpenAI-compatible /v1/chat/completions endpoint:
  - user message: style hint (natural language tone/style control)
  - assistant message: target text to synthesize
  - audio: { format: "wav", voice: "Mia" | "Chloe" | "Milo" | "Dean" }

Pipeline:
  1. For each segment: POST to MiMo API → base64 WAV
  2. Decode base64 → .wav file
  3. Generate silence files for pauses via ffmpeg
  4. Build concat_list.txt with all segments + silences
  5. ffmpeg -f concat → final audio file
  6. Optionally clean up segment files
"""

from __future__ import annotations

import logging
import os
import shutil as sh
from pathlib import Path

import httpx

from backend.services.output.base import ProgressCallback, _noop_progress
from backend.services.output.plugins.audio_helpers import (
    check_ffmpeg,
    concat_audio,
    decode_base64_audio,
    generate_silence,
)
from backend.services.output.plugins.tts_models import TTSScript

logger = logging.getLogger(__name__)

# Default MiMo TTS configuration
_DEFAULT_API_BASE = "https://api.xiaomimimo.com/v1"
_DEFAULT_MODEL = "mimo-v2.5-tts"
_DEFAULT_VOICE = "Mia"

# Maximum text length per segment (MiMo may have limits)
_MAX_TEXT_LENGTH = 3000


class MiMoTTSRenderer:
    """Renders a ``TTSScript`` to audio using MiMo-V2.5-TTS API.

    The MiMo TTS API is OpenAI-compatible but returns audio as base64
    in the response JSON.  Style control is done via the ``user`` message
    (natural language description of tone, pace, emotion).

    Stateless — a fresh instance is created per render call.
    """

    def __init__(
        self,
        api_base: str | None = None,
        api_key: str | None = None,
        api_key_env: str = "XIAOMI_API_KEY",
        model: str = _DEFAULT_MODEL,
    ) -> None:
        """Initialise MiMoTTSRenderer."""
        self._api_base = (api_base or _DEFAULT_API_BASE).rstrip("/")
        if not self._api_base.endswith("/v1"):
            self._api_base = f"{self._api_base}/v1"
        self._api_key = api_key or os.getenv(api_key_env, "")
        self._model = model

        if not self._api_key:
            raise ValueError(f"MiMo API key not found. Set the {api_key_env} environment variable or pass api_key directly.")

    async def render(
        self,
        script: TTSScript,
        job_id: str,
        output_dir: Path,
        output_format: str = "wav",
        bitrate: str = "128k",
        keep_segments: bool = False,
        *,
        progress_callback: ProgressCallback = _noop_progress,
    ) -> Path:
        """Render the TTS script to an audio file.

        Args:
            script: The TTS script with ordered segments.
            job_id: Render job ID.
            output_dir: Root output directory.
            output_format: Target audio format (wav/mp3).
            bitrate: Audio bitrate for ffmpeg concat (e.g. "128k").
            keep_segments: Whether to keep individual segment files.
            progress_callback: Async callback ``(current, total)`` for
                tracking render progress.

        Returns:
            Path to the generated audio file.
        """
        job_dir = output_dir / job_id
        segments_dir = job_dir / "segments"
        segments_dir.mkdir(parents=True, exist_ok=True)

        ffmpeg = check_ffmpeg()

        # 1. Render each segment
        segment_files: list[Path] = []
        total = len(script.segments)
        await progress_callback(0, total)
        for i, seg in enumerate(script.segments):
            seg_file = segments_dir / f"{seg.id}.wav"

            logger.info(
                "MiMo TTS segment %d/%d: voice=%s, text_len=%d, style=%s",
                i + 1,
                total,
                seg.voice_id or _DEFAULT_VOICE,
                len(seg.text),
                (seg.style_hint or "(none)")[:60],
            )

            # Generate speech via MiMo TTS API
            await self._render_segment(
                text=seg.text,
                voice=seg.voice_id or _DEFAULT_VOICE,
                style_hint=seg.style_hint,
                output_path=seg_file,
            )
            segment_files.append(seg_file)
            await progress_callback(i + 1, total)

            # Generate silence for pause_after_ms
            if seg.pause_after_ms > 0 and i < len(script.segments) - 1:
                silence_file = segments_dir / f"{seg.id}_silence.mp3"
                await generate_silence(seg.pause_after_ms, silence_file, ffmpeg)
                segment_files.append(silence_file)

        # 2. Build concat list
        concat_file = segments_dir / "concat_list.txt"
        with open(concat_file, "w", encoding="utf-8") as f:
            for seg_file in segment_files:
                f.write(f"file '{seg_file.name}'\n")

        # 3. Concatenate
        ext = output_format
        output_path = job_dir / f"debate_podcast.{ext}"
        await concat_audio(concat_file, output_path, ffmpeg, bitrate)

        # 4. Cleanup segments
        if not keep_segments:
            sh.rmtree(segments_dir, ignore_errors=True)
            logger.info("Segment files cleaned up for job %s", job_id)

        logger.info("MiMo TTS audio file generated: %s", output_path)
        return output_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _render_segment(
        self,
        text: str,
        voice: str,
        style_hint: str,
        output_path: Path,
    ) -> None:
        """Render a single text segment to WAV via MiMo TTS API.

        Args:
            text: The text to synthesize (assistant message).
            voice: MiMo voice name (Mia, Chloe, Milo, Dean).
            style_hint: Natural language style description (user message).
            output_path: Output .wav file path.
        """
        from backend.services.llm_activity import llm_activity

        url = f"{self._api_base}/chat/completions"

        # Build messages per MiMo TTS Call Rules
        messages: list[dict[str, str]] = []

        # Style hint goes in user message (optional, for tone control)
        if style_hint:
            messages.append(
                {
                    "role": "user",
                    "content": style_hint,
                }
            )

        # Target text MUST be in assistant message
        messages.append(
            {
                "role": "assistant",
                "content": text,
            }
        )

        payload: dict = {
            "model": self._model,
            "messages": messages,
            "audio": {
                "format": "wav",
                "voice": voice,
            },
        }

        # MiMo TTS uses "api-key" header (per API docs).
        # Also send Authorization: Bearer as fallback for compatibility.
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "api-key": self._api_key,
            "Authorization": f"Bearer {self._api_key}",
        }

        logger.debug(
            "MiMo TTS call: model=%s, voice=%s, text_len=%d, style=%s",
            self._model,
            voice,
            len(text),
            style_hint[:50] if style_hint else "(none)",
        )

        call_id = await llm_activity.start_call(
            model=self._model,
            provider="xiaomi_mimo",
            context="TTS",
        )

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code != 200:
                    body = response.text[:500]
                    raise RuntimeError(f"MiMo TTS API returned {response.status_code}: {body}")

            data = response.json()

            # Extract base64 audio from response
            try:
                message = data["choices"][0]["message"]
                audio_data = message["audio"]["data"]
            except (KeyError, IndexError) as exc:
                raise RuntimeError(f"MiMo TTS API returned unexpected response structure: {exc}. Response (truncated): {str(data)[:500]}")

            # Track usage if available
            usage = data.get("usage", {})
            tokens_in = usage.get("prompt_tokens", 0)
            tokens_out = usage.get("completion_tokens", 0)

            await llm_activity.end_call(
                call_id,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                status="completed",
            )

            # Decode and write WAV file
            await decode_base64_audio(audio_data, output_path)

            logger.debug(
                "MiMo TTS segment rendered: %s → %s",
                text[:50],
                output_path,
            )

        except Exception as exc:
            await llm_activity.end_call(
                call_id,
                status="failed",
                error=str(exc),
            )
            raise


# ---------------------------------------------------------------------------
# Available MiMo voices
# ---------------------------------------------------------------------------

MIMO_VOICES = [
    {"voice_id": "Mia", "name": "Mia", "language": "en", "gender": "Female"},
    {"voice_id": "Chloe", "name": "Chloe", "language": "en", "gender": "Female"},
    {"voice_id": "Milo", "name": "Milo", "language": "en", "gender": "Male"},
    {"voice_id": "Dean", "name": "Dean", "language": "en", "gender": "Male"},
    {"voice_id": "冰糖", "name": "冰糖", "language": "zh", "gender": "Female"},
    {"voice_id": "茉莉", "name": "茉莉", "language": "zh", "gender": "Female"},
    {"voice_id": "苏打", "name": "苏打", "language": "zh", "gender": "Male"},
    {"voice_id": "白桦", "name": "白桦", "language": "zh", "gender": "Male"},
]


def list_mimo_voices(
    language: str | None = None,
    gender: str | None = None,
) -> list[dict]:
    """Return available MiMo TTS voices, optionally filtered.

    Args:
        language: Filter by language prefix (e.g. "en").
        gender: Filter by gender ("Male" / "Female").

    Returns:
        List of voice dicts with keys: voice_id, name, language, gender.
    """
    voices = MIMO_VOICES
    if language:
        voices = [v for v in voices if v["language"].startswith(language)]
    if gender:
        voices = [v for v in voices if v["gender"].lower() == gender.lower()]
    return voices
