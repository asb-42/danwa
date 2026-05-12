"""EdgeTTSRenderer — renders TTSScript to audio via edge-tts + ffmpeg.

Pipeline:
  1. For each segment: edge_tts.Communicate → temp .mp3 file
  2. Generate silence files for pauses via ffmpeg anullsrc
  3. Build concat_list.txt with all segments + silences in order
  4. ffmpeg -f concat → final audio file
  5. Optionally clean up segment files
"""

from __future__ import annotations

import logging
import shutil as sh
from pathlib import Path

from backend.services.output.plugins.audio_helpers import (
    check_ffmpeg,
    concat_audio,
    generate_silence,
)
from backend.services.output.plugins.tts_models import TTSScript
from backend.services.output.plugins.tts_plugin import AudioFormat

logger = logging.getLogger(__name__)


class EdgeTTSRenderer:
    """Renders a ``TTSScript`` to audio using edge-tts + ffmpeg.

    Stateless — a fresh instance is created per render call.
    """

    async def render(
        self,
        script: TTSScript,
        job_id: str,
        output_dir: Path,
        output_format: AudioFormat = AudioFormat.MP3,
        bitrate: str = "128k",
        keep_segments: bool = False,
    ) -> Path:
        """Render the TTS script to an audio file.

        Args:
            script: The TTS script with ordered segments.
            job_id: Render job ID.
            output_dir: Root output directory.
            output_format: Target audio format (mp3/wav).
            bitrate: Audio bitrate (e.g. "128k").
            keep_segments: Whether to keep individual segment files.

        Returns:
            Path to the generated audio file.
        """
        job_dir = output_dir / job_id
        segments_dir = job_dir / "segments"
        segments_dir.mkdir(parents=True, exist_ok=True)

        ffmpeg = check_ffmpeg()

        # 1. Render each segment
        segment_files: list[Path] = []
        for i, seg in enumerate(script.segments):
            seg_file = segments_dir / f"{seg.id}.mp3"

            # Generate speech via edge-tts
            await self._render_segment(seg.text, seg.voice_id, seg_file)
            segment_files.append(seg_file)

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
        ext = output_format.value
        output_path = job_dir / f"debate_podcast.{ext}"
        await concat_audio(concat_file, output_path, ffmpeg, bitrate)

        # 4. Cleanup segments
        if not keep_segments:
            sh.rmtree(segments_dir, ignore_errors=True)
            logger.info("Segment files cleaned up for job %s", job_id)

        logger.info("Audio file generated: %s", output_path)
        return output_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _render_segment(text: str, voice: str, output_path: Path) -> None:
        """Render a single text segment to MP3 via edge-tts."""
        try:
            import edge_tts

            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(output_path))
        except ImportError:
            raise RuntimeError("edge-tts is not installed. Install with: pip install edge-tts")
