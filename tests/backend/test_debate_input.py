"""Tests for DebateInput and InputAttachment models."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.models.debate_input import DebateInput, InputAttachment


class TestInputAttachment:
    def test_minimal(self) -> None:
        a = InputAttachment(content_ref="/tmp/test.pdf", mime_type="application/pdf")
        assert a.content_ref == "/tmp/test.pdf"
        assert a.id  # auto-generated
        assert a.extracted_text is None

    def test_with_extracted_text(self) -> None:
        a = InputAttachment(
            content_ref="/tmp/ocr.pdf",
            mime_type="application/pdf",
            extracted_text="OCR text content",
        )
        assert a.extracted_text == "OCR text content"


class TestDebateInput:
    def test_minimal(self) -> None:
        d = DebateInput(
            source_plugin_key="standard_text",
            topic="Should AI be regulated?",
        )
        assert d.topic == "Should AI be regulated?"
        assert d.session_id is None
        assert d.source_plugin_key == "standard_text"
        assert d.input_hash  # auto-computed

    def test_with_attachments(self) -> None:
        att = InputAttachment(content_ref="/tmp/doc.pdf", mime_type="application/pdf")
        d = DebateInput(
            source_plugin_key="standard_text",
            topic="Test topic",
            attachments=[att],
        )
        assert len(d.attachments) == 1
        assert d.input_hash

    def test_hash_deterministic(self) -> None:
        d1 = DebateInput(source_plugin_key="standard_text", topic="Same topic")
        d2 = DebateInput(source_plugin_key="standard_text", topic="Same topic")
        assert d1.input_hash == d2.input_hash

    def test_hash_differs_for_different_topics(self) -> None:
        d1 = DebateInput(source_plugin_key="standard_text", topic="Topic A")
        d2 = DebateInput(source_plugin_key="standard_text", topic="Topic B")
        assert d1.input_hash != d2.input_hash

    def test_hash_length(self) -> None:
        d = DebateInput(source_plugin_key="standard_text", topic="Test")
        assert len(d.input_hash) == 64  # SHA-256 hex

    def test_full_model(self) -> None:
        d = DebateInput(
            session_id="s1",
            source_plugin_key="stt",
            source_metadata={"model": "whisper-large-v3", "confidence": 0.95},
            topic="AI Ethics debate",
            attachments=[
                InputAttachment(
                    content_ref="/audio/recording.wav",
                    mime_type="audio/wav",
                    description="Original recording",
                )
            ],
            context_overrides={"tone_profile": "academic"},
            timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        )
        assert d.session_id == "s1"
        assert d.source_metadata["model"] == "whisper-large-v3"
        assert len(d.attachments) == 1
        assert d.context_overrides["tone_profile"] == "academic"
