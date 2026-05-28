"""Tests for TTSOutputPlugin, TTSPluginConfig, and TTSScriptEngine."""

from __future__ import annotations

from backend.models.artifact import (
    DebateArtifact,
    Injection,
    Turn,
    UserQuery,
)
from backend.services.output.plugins.tts_plugin import (
    AudioFormat,
    TTSEngine,
    TTSOutputPlugin,
    TTSPluginConfig,
)
from backend.services.output.plugins.tts_script_engine import TTSScriptEngine


class TestTTSPluginConfig:
    def test_defaults(self) -> None:
        c = TTSPluginConfig()
        assert c.engine == TTSEngine.EDGE_TTS
        assert c.default_voice == "de-DE-KatjaNeural"
        assert c.segment_pause_ms == 800
        assert c.turn_pause_ms == 300
        assert c.output_format == AudioFormat.MP3
        assert c.bitrate == "128k"

    def test_custom(self) -> None:
        c = TTSPluginConfig(
            voice_mapping={"Alice": "de-DE-ConradNeural"},
            intro_text="Welcome",
            outro_text="Goodbye",
        )
        assert c.voice_mapping["Alice"] == "de-DE-ConradNeural"
        assert c.intro_text == "Welcome"


class TestTTSScriptEngine:
    def _make_artifact(self) -> DebateArtifact:
        return DebateArtifact(
            session_id="s1",
            workflow_id="w1",
            topic="Test",
            transcript=[
                Turn(
                    id="t1",
                    round=1,
                    node_id="n1",
                    agent_name="Alice",
                    role_type="strategist",
                    content="Hello world",
                ),
                Turn(
                    id="t2",
                    round=1,
                    node_id="n2",
                    agent_name="Bob",
                    role_type="critic",
                    content="I disagree",
                ),
            ],
            interjections=[
                Injection(
                    id="ij1",
                    source="user",
                    target_node_id="n1",
                    content="Extra info",
                ),
            ],
            user_queries=[
                UserQuery(id="q1", content="Why?", response_turn_id="t1"),
            ],
        )

    def test_basic_segments(self) -> None:
        engine = TTSScriptEngine()
        script = engine.transform(
            self._make_artifact(),
            voice_mapping={},
            default_voice="de-DE-KatjaNeural",
        )
        # 2 turns + 1 injection + 1 query = 4 segments
        assert len(script.segments) == 4

    def test_intro_outro(self) -> None:
        engine = TTSScriptEngine()
        script = engine.transform(
            self._make_artifact(),
            voice_mapping={},
            default_voice="de-DE-KatjaNeural",
            intro_text="Welcome to the debate",
            outro_text="Thank you for listening",
        )
        # intro + 4 + outro = 6
        assert len(script.segments) == 6
        assert script.segments[0].is_intro is True
        assert script.segments[-1].is_outro is True

    def test_voice_resolution(self) -> None:
        engine = TTSScriptEngine()
        script = engine.transform(
            self._make_artifact(),
            voice_mapping={"Alice": "de-DE-ConradNeural"},
            default_voice="de-DE-KatjaNeural",
        )
        # Find Alice's turn
        alice_turns = [s for s in script.segments if s.speaker_name == "Alice"]
        assert len(alice_turns) == 1
        assert alice_turns[0].voice_id == "de-DE-ConradNeural"

        # Bob should get default
        bob_turns = [s for s in script.segments if s.speaker_name == "Bob"]
        assert len(bob_turns) == 1
        assert bob_turns[0].voice_id == "de-DE-KatjaNeural"

    def test_injection_hint(self) -> None:
        engine = TTSScriptEngine()
        script = engine.transform(
            self._make_artifact(),
            voice_mapping={},
            default_voice="de-DE-KatjaNeural",
        )
        inj_segments = [s for s in script.segments if s.injection_reference]
        assert len(inj_segments) == 1
        assert "Zwischenfrage" in inj_segments[0].text

    def test_metadata(self) -> None:
        engine = TTSScriptEngine()
        script = engine.transform(
            self._make_artifact(),
            voice_mapping={},
            default_voice="de-DE-KatjaNeural",
        )
        assert script.metadata["topic"] == "Test"
        assert script.metadata["total_segments"] == 4


class TestTTSOutputPlugin:
    def test_plugin_properties(self) -> None:
        assert TTSOutputPlugin.plugin_key == "tts"
        assert "mp3" in TTSOutputPlugin.supported_formats
        assert "wav" in TTSOutputPlugin.supported_formats

    def test_pyttsx3_engine_enum(self) -> None:
        """pyttsx3 engine is registered in the TTSEngine enum."""
        assert TTSEngine.PYTTSX3 == "pyttsx3"

    def test_pyttsx3_engine_config(self) -> None:
        """TTSPluginConfig accepts pyttsx3 as engine."""
        c = TTSPluginConfig(engine=TTSEngine.PYTTSX3)
        assert c.engine == TTSEngine.PYTTSX3

    def test_pyttsx3_renderer_import(self) -> None:
        """Pyttsx3Renderer can be imported without pyttsx3 installed."""
        from backend.services.output.plugins.pyttsx3_renderer import Pyttsx3Renderer

        renderer = Pyttsx3Renderer()
        assert renderer is not None
        assert hasattr(renderer, "render")
        assert hasattr(renderer, "_render_segment")
