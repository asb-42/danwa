"""TTSOutputPlugin — renders DebateArtifact as MP3/WAV podcast via edge-tts + ffmpeg."""

from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field

from backend.models.artifact import DebateArtifact
from backend.services.output.base import OutputPlugin
from backend.services.output.plugins.tts_script_engine import TTSScriptEngine
from backend.services.output.registry import register_plugin

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config Schema
# ---------------------------------------------------------------------------


class TTSEngine(StrEnum):
    EDGE_TTS = "edge_tts"
    MIMO_TTS = "mimo_tts"


class AudioFormat(StrEnum):
    MP3 = "mp3"
    WAV = "wav"


class TTSPluginConfig(BaseModel):
    """Configuration schema for the TTS Podcast output plugin."""

    engine: TTSEngine = TTSEngine.EDGE_TTS
    voice_mapping: dict[str, str] = Field(
        default_factory=dict,
        description="agent_name → voice_id mapping",
    )
    default_voice: str = "de-DE-KatjaNeural"
    segment_pause_ms: int = Field(default=800, ge=0, le=5000)
    turn_pause_ms: int = Field(default=300, ge=0, le=5000)
    intro_text: str | None = None
    outro_text: str | None = None
    output_format: AudioFormat = AudioFormat.MP3
    bitrate: str = Field(default="128k", pattern=r"^\d+k$")
    language: str = Field(default="de", description="Language for spoken hints")
    keep_segments: bool = Field(
        default=False,
        description="Keep individual segment files after concatenation",
    )
    # MiMo TTS specific (only used when engine="mimo_tts")
    mimo_api_key_env: str = Field(
        default="MIMO_API_KEY",
        description="Environment variable containing MiMo API key",
    )
    mimo_api_base: str = Field(
        default="https://api.xiaomimimo.com/v1",
        description="MiMo TTS API base URL",
    )
    mimo_model: str = Field(
        default="mimo-v2.5-tts",
        description="MiMo TTS model ID",
    )
    default_style_hint: str = Field(
        default="",
        description="Default style hint for MiMo TTS (natural language tone/style)",
    )


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------


@register_plugin
class TTSOutputPlugin(OutputPlugin):
    """Renders a DebateArtifact as an audio podcast via edge-tts + ffmpeg.

    Transforms the transcript into a TTSScript, renders each segment
    with edge-tts, and concatenates them with ffmpeg.
    """

    plugin_key: ClassVar[str] = "tts"
    plugin_name: ClassVar[str] = "TTS Podcast / Interview"
    supported_formats: ClassVar[list[str]] = ["mp3", "wav"]
    config_schema: ClassVar[type[BaseModel]] = TTSPluginConfig

    async def render(
        self,
        artifact: DebateArtifact,
        config: BaseModel,
        job_id: str,
        output_dir: Path,
    ) -> list[Path]:
        """Render artifact to MP3/WAV audio file.

        Args:
            artifact: The debate artifact.
            config: Validated ``TTSPluginConfig``.
            job_id: Render job ID.
            output_dir: Root output directory.

        Returns:
            List containing the generated audio file path.
        """
        assert isinstance(config, TTSPluginConfig)
        job_dir = output_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        # Resolve voice_mapping from blueprints if empty
        voice_mapping = dict(config.voice_mapping)
        if not voice_mapping:
            try:
                from backend.blueprints.repository import BlueprintRepository
                repo = BlueprintRepository()
                blueprints = repo.list_blueprints(active_only=True, limit=500)
                for bp in blueprints:
                    if bp.tts_voice_id:
                        voice_mapping[bp.name] = bp.tts_voice_id
                if voice_mapping:
                    logger.info(
                        "Resolved %d voice mappings from AgentBlueprints",
                        len(voice_mapping),
                    )
            except Exception:
                logger.debug("Could not resolve voice mappings from blueprints", exc_info=True)

        # 1. Transform artifact → TTSScript
        script_engine = TTSScriptEngine()
        script = script_engine.transform(
            artifact,
            voice_mapping=voice_mapping,
            default_voice=config.default_voice,
            segment_pause_ms=config.segment_pause_ms,
            turn_pause_ms=config.turn_pause_ms,
            intro_text=config.intro_text,
            outro_text=config.outro_text,
            language=config.language,
            default_style_hint=config.default_style_hint,
            engine=config.engine.value,
        )

        logger.info(
            "TTS script generated: %d segments for job %s (engine=%s)",
            len(script.segments),
            job_id,
            config.engine.value,
        )

        # 2. Render audio — engine router
        if config.engine == TTSEngine.MIMO_TTS:
            from backend.services.output.plugins.mimo_tts_renderer import MiMoTTSRenderer

            # For MiMo, output_format is always wav (API returns wav)
            renderer = MiMoTTSRenderer(
                api_base=config.mimo_api_base,
                api_key_env=config.mimo_api_key_env,
                model=config.mimo_model,
            )
            output_path = await renderer.render(
                script=script,
                job_id=job_id,
                output_dir=output_dir,
                output_format="wav",
                bitrate=config.bitrate,
                keep_segments=config.keep_segments,
            )
        else:
            from backend.services.output.plugins.edge_tts_renderer import EdgeTTSRenderer

            renderer = EdgeTTSRenderer()
            output_path = await renderer.render(
                script=script,
                job_id=job_id,
                output_dir=output_dir,
                output_format=config.output_format,
                bitrate=config.bitrate,
                keep_segments=config.keep_segments,
            )

        logger.info("TTSOutputPlugin rendered audio for job %s: %s", job_id, output_path)
        return [output_path]
