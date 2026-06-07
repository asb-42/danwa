"""TTSOutputPlugin — renders DebateArtifact as MP3/WAV podcast via edge-tts + ffmpeg."""

from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field

from backend.models.artifact import DebateArtifact
from backend.services.output.base import OutputPlugin, ProgressCallback, _noop_progress
from backend.services.output.plugins.tts_script_engine import TTSScriptEngine
from backend.services.output.registry import register_plugin

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config Schema
# ---------------------------------------------------------------------------


class TTSEngine(StrEnum):
    """TTSEngine class."""

    EDGE_TTS = "edge_tts"
    MIMO_TTS = "mimo_tts"
    PYTTSX3 = "pyttsx3"


class AudioFormat(StrEnum):
    """AudioFormat class."""

    MP3 = "mp3"
    WAV = "wav"


class TTSPluginConfig(BaseModel):
    """Configuration schema for the TTS Podcast output plugin."""

    engine: TTSEngine = TTSEngine.EDGE_TTS
    voice_mapping: dict[str, str] = Field(
        default_factory=dict,
        description="agent_name → voice_id mapping",
        json_schema_extra={"hidden": True},
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
    # API base URL, key env, and model are auto-resolved from the
    # TTS LLM profile in the DB (profile_type="tts", provider="xiaomi").
    # These fields serve as overrides if no matching profile exists.
    mimo_api_key_env: str = Field(
        default="",
        description="Override env var for MiMo API key (auto-resolved from LLM profile)",
        json_schema_extra={"hidden": True},
    )
    mimo_api_base: str = Field(
        default="",
        description="Override MiMo TTS API base URL (auto-resolved from LLM profile)",
        json_schema_extra={"hidden": True},
    )
    mimo_model: str = Field(
        default="",
        description="Override MiMo TTS model ID (auto-resolved from LLM profile)",
        json_schema_extra={"hidden": True},
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
        *,
        progress_callback: ProgressCallback = _noop_progress,
    ) -> list[Path]:
        """Render artifact to MP3/WAV audio file.

        Args:
            artifact: The debate artifact.
            config: Validated ``TTSPluginConfig``.
            job_id: Render job ID.
            output_dir: Root output directory.
            progress_callback: Async callback ``(current, total)`` for
                tracking render progress.

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

        # Resolve MiMo TTS config from LLM profile (profile_type="tts", provider="xiaomi")
        mimo_api_base = config.mimo_api_base
        mimo_api_key_env = config.mimo_api_key_env
        mimo_model = config.mimo_model
        if config.engine == TTSEngine.MIMO_TTS:
            if not mimo_api_base or not mimo_api_key_env or not mimo_model:
                try:
                    from backend.blueprints.repository import BlueprintRepository

                    repo = BlueprintRepository()
                    for profile in repo.list_llm_profiles(limit=500):
                        if profile.profile_type == "tts" and profile.provider == "xiaomi":
                            if not mimo_api_base:
                                mimo_api_base = (profile.api_base or "").rstrip("/")
                                if not mimo_api_base.endswith("/v1"):
                                    mimo_api_base = f"{mimo_api_base}/v1"
                            if not mimo_api_key_env:
                                mimo_api_key_env = profile.api_key_env or "XIAOMI_API_KEY"
                            if not mimo_model:
                                mimo_model = profile.model or "mimo-v2.5-tts"
                            logger.info(
                                "Auto-resolved MiMo TTS config from LLM profile %s: api_base=%s, api_key_env=%s, model=%s",
                                profile.id,
                                mimo_api_base,
                                mimo_api_key_env,
                                mimo_model,
                            )
                            break
                except Exception:
                    logger.debug("Could not auto-resolve MiMo TTS config from LLM profiles", exc_info=True)
            # Final fallback defaults
            if not mimo_api_base:
                mimo_api_base = "https://api.xiaomimimo.com/v1"
            if not mimo_api_key_env:
                mimo_api_key_env = "XIAOMI_API_KEY"
            if not mimo_model:
                mimo_model = "mimo-v2.5-tts"

        # Resolve default_voice for MiMo engine (edge-tts voice names are invalid)
        default_voice = config.default_voice
        if config.engine == TTSEngine.MIMO_TTS:
            mimo_valid = {"Mia", "Chloe", "Milo", "Dean", "冰糖", "茉莉", "苏打", "白桦"}
            if default_voice not in mimo_valid:
                # Pick language-appropriate default
                zh_voices = {"冰糖", "茉莉", "苏打", "白桦"}
                if config.language and config.language.startswith("zh") and zh_voices:
                    default_voice = "bing_tang"
                else:
                    default_voice = "Mia"
                logger.info(
                    "MiMo TTS: overriding default_voice from '%s' to '%s' (language=%s)",
                    config.default_voice,
                    default_voice,
                    config.language,
                )

        # 1. Transform artifact → TTSScript
        script_engine = TTSScriptEngine()
        script = script_engine.transform(
            artifact,
            voice_mapping=voice_mapping,
            default_voice=default_voice,
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

            renderer = MiMoTTSRenderer(
                api_base=mimo_api_base,
                api_key_env=mimo_api_key_env,
                model=mimo_model,
            )
            output_path = await renderer.render(
                script=script,
                job_id=job_id,
                output_dir=output_dir,
                output_format="wav",
                bitrate=config.bitrate,
                keep_segments=config.keep_segments,
                progress_callback=progress_callback,
            )

            # Convert WAV → MP3 if user requested MP3
            if config.output_format == AudioFormat.MP3:
                from backend.services.output.plugins.audio_helpers import check_ffmpeg

                ffmpeg = check_ffmpeg()
                mp3_path = output_path.with_suffix(".mp3")
                import asyncio

                proc = await asyncio.create_subprocess_exec(
                    str(ffmpeg),
                    "-y",
                    "-i",
                    str(output_path),
                    "-codec:a",
                    "libmp3lame",
                    "-b:a",
                    config.bitrate,
                    str(mp3_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await proc.communicate()
                if proc.returncode == 0:
                    output_path.unlink(missing_ok=True)
                    output_path = mp3_path
                    logger.info("Converted WAV → MP3: %s", mp3_path)
                else:
                    logger.warning(
                        "WAV→MP3 conversion failed (returning WAV): %s",
                        stderr.decode()[:200],
                    )

        elif config.engine == TTSEngine.PYTTSX3:
            from backend.services.output.plugins.pyttsx3_renderer import Pyttsx3Renderer

            renderer = Pyttsx3Renderer()
            output_path = await renderer.render(
                script=script,
                job_id=job_id,
                output_dir=output_dir,
                output_format=config.output_format,
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
