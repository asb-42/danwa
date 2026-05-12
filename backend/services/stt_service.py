"""STTService — Speech-to-Text transcription service.

Supports local Whisper (faster-whisper) with CPU fallback.
Cloud providers (whisper-api, azure-stt, google-stt) are stubbed
for future implementation.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class STTService:
    """Transcribes audio to text using STT profiles.

    Usage::

        service = STTService()
        text = await service.transcribe_chunk(audio_bytes, profile)
    """

    async def transcribe_chunk(
        self,
        audio_bytes: bytes,
        profile: Any,
        language: str = "de",
    ) -> str:
        """Transcribe audio bytes to text.

        Args:
            audio_bytes: Raw audio data (e.g. WebM/Opus from browser).
            profile: An LLMProfile with protocol='stt'.
            language: Language code for transcription.

        Returns:
            Transcribed text.

        Raises:
            RuntimeError: If transcription fails.
        """
        provider = getattr(profile, "provider", "whisper-local")
        model = getattr(profile, "model", "base")

        if provider == "whisper-local":
            return await self._transcribe_whisper_local(audio_bytes, model, language)
        elif provider == "whisper-api":
            return await self._transcribe_whisper_api(audio_bytes, model, language)
        else:
            raise RuntimeError(f"STT provider {provider!r} is not yet implemented. Supported: whisper-local, whisper-api")

    async def transcribe_file(
        self,
        file_path: Path,
        profile: Any,
        language: str = "de",
    ) -> str:
        """Transcribe an audio file to text.

        Args:
            file_path: Path to the audio file.
            profile: An LLMProfile with protocol='stt'.
            language: Language code.

        Returns:
            Transcribed text.
        """
        audio_bytes = file_path.read_bytes()
        return await self.transcribe_chunk(audio_bytes, profile, language)

    async def _transcribe_whisper_local(
        self,
        audio_bytes: bytes,
        model: str,
        language: str,
    ) -> str:
        """Transcribe using faster-whisper (local, CPU-capable)."""
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError("faster-whisper is not installed. Install with: pip install faster-whisper")

        # Write audio bytes to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = Path(tmp.name)

        try:
            # Load model (CPU fallback)
            whisper_model = WhisperModel(model, device="cpu", compute_type="int8")
            segments, info = whisper_model.transcribe(
                str(tmp_path),
                language=language,
                beam_size=5,
            )
            text_parts = [segment.text for segment in segments]
            result = " ".join(text_parts).strip()
            logger.info(
                "Whisper transcription complete: %d chars (model=%s, lang=%s)",
                len(result),
                model,
                language,
            )
            return result
        finally:
            tmp_path.unlink(missing_ok=True)

    async def _transcribe_whisper_api(
        self,
        audio_bytes: bytes,
        model: str,
        language: str,
    ) -> str:
        """Transcribe using OpenAI Whisper API (cloud).

        Stub — requires API key configuration.
        """
        raise RuntimeError("Whisper API transcription is not yet implemented. Use whisper-local for now.")
