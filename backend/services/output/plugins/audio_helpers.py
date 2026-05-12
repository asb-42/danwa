"""Audio helpers — shared utilities for TTS renderers.

Extracted from EdgeTTSRenderer to be shared with MiMoTTSRenderer
and any future TTS engines.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


async def generate_silence(duration_ms: int, output_path: Path, ffmpeg: str) -> None:
    """Generate a silence file of the given duration using ffmpeg.

    Args:
        duration_ms: Duration in milliseconds.
        output_path: Output file path (.mp3).
        ffmpeg: Path to ffmpeg binary.
    """
    duration_s = duration_ms / 1000.0
    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=24000:cl=mono",
        "-t",
        str(duration_s),
        "-c:a",
        "libmp3lame",
        "-q:a",
        "9",
        str(output_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg silence generation failed: {stderr.decode()}")


async def concat_audio(
    concat_file: Path,
    output_path: Path,
    ffmpeg: str,
    bitrate: str = "128k",
) -> None:
    """Concatenate segment files into a single audio file.

    Args:
        concat_file: Path to ffmpeg concat list file.
        output_path: Output audio file path.
        ffmpeg: Path to ffmpeg binary.
        bitrate: Audio bitrate (e.g. "128k").
    """
    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-b:a",
        bitrate,
        str(output_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg concat failed: {stderr.decode()}")


async def decode_base64_audio(b64_data: str, output_path: Path) -> None:
    """Decode a base64-encoded audio blob and write to file.

    Used by MiMo TTS renderer where the API returns audio data
    as base64 in the response JSON.

    Args:
        b64_data: Base64-encoded audio bytes.
        output_path: Output file path (.wav).
    """
    audio_bytes = base64.b64decode(b64_data)
    output_path.write_bytes(audio_bytes)
    logger.debug(
        "Decoded base64 audio: %d bytes → %s",
        len(audio_bytes),
        output_path,
    )


def check_ffmpeg() -> str:
    """Check that ffmpeg is available and return its path.

    Returns:
        Path to ffmpeg binary.

    Raises:
        RuntimeError: If ffmpeg is not found in PATH.
    """
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is not installed or not in PATH. Install it with: apt install ffmpeg / brew install ffmpeg")
    return ffmpeg
