"""Tests for Service LLM eligibility and title generation (Plan 016)."""

from __future__ import annotations

from backend.core.config import is_service_llm_eligible
from backend.services.debate_workflow import _fallback_title, _post_process_title, validate_title


class FakeProfile:
    """Minimal LLM profile mock for eligibility tests."""

    def __init__(
        self,
        model: str = "claude-3.5-sonnet",
        provider_value: str = "openrouter",
        context_window: int | None = 8192,
        profile_type: str = "text",
        service_eligible: bool = True,
    ):
        self.id = "test-profile"
        self.name = "Test Profile"
        self.model = model
        self.context_window = context_window
        self.profile_type = profile_type
        self.service_eligible = service_eligible

        class Provider:
            value = provider_value

        self.provider = Provider()


class TestServiceLLMEligibility:
    """Tests for is_service_llm_eligible()."""

    def test_eligible_text_profile(self):
        profile = FakeProfile()
        eligible, reason = is_service_llm_eligible(profile)
        assert eligible is True
        assert "Eignung bestätigt" in reason

    def test_ineligible_tts_profile(self):
        profile = FakeProfile(profile_type="tts")
        eligible, reason = is_service_llm_eligible(profile)
        assert eligible is False
        assert "tts" in reason.lower()

    def test_ineligible_stt_profile(self):
        profile = FakeProfile(profile_type="stt")
        eligible, reason = is_service_llm_eligible(profile)
        assert eligible is False
        assert "stt" in reason.lower()

    def test_ineligible_small_context(self):
        profile = FakeProfile(context_window=2048)
        eligible, reason = is_service_llm_eligible(profile)
        assert eligible is False
        assert "zu klein" in reason.lower()

    def test_ineligible_blacklisted_model(self):
        profile = FakeProfile(model="gpt-3.5-turbo")
        eligible, reason = is_service_llm_eligible(profile)
        assert eligible is False
        assert "blacklist" in reason.lower()

    def test_ineligible_not_marked_eligible(self):
        profile = FakeProfile(service_eligible=False)
        eligible, reason = is_service_llm_eligible(profile)
        assert eligible is False
        assert "markiert" in reason.lower()

    def test_returns_tuple(self):
        profile = FakeProfile()
        result = is_service_llm_eligible(profile)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)


class TestValidateTitle:
    """Tests for validate_title()."""

    def test_valid_title(self):
        valid, reason = validate_title("Klimawandel und Wirtschaft: Ein Widerspruch?", "test")
        assert valid is True
        assert reason == "OK"

    def test_too_short(self):
        valid, reason = validate_title("Zu kurz", "test case text")
        assert valid is False
        assert "kurz" in reason.lower()

    def test_too_long(self):
        long_title = "A" * 200
        valid, reason = validate_title(long_title, "test")
        assert valid is False
        assert "lang" in reason.lower()

    def test_meta_text_the_user(self):
        valid, reason = validate_title("The user wants a debate about climate", "test")
        assert valid is False
        assert "Meta" in reason

    def test_meta_text_ich_schlage(self):
        valid, reason = validate_title("Ich schlage vor: Klimawandel", "test")
        assert valid is False
        assert "Meta" in reason

    def test_matches_case_text(self):
        case = "This is a very specific debate topic about something"
        valid, reason = validate_title("This is a very specific", case)
        assert valid is False
        assert "identisch" in reason.lower()

    def test_only_special_chars(self):
        valid, reason = validate_title("-----", "test")
        assert valid is False


class TestFallbackTitle:
    """Tests for _fallback_title()."""

    def test_returns_string(self):
        result = _fallback_title("This is a test case for the debate. It should work.")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_short_case(self):
        result = _fallback_title("Short")
        assert result == "Short"

    def test_truncates_long_case(self):
        long_case = "A" * 300
        result = _fallback_title(long_case)
        assert len(result) <= 150


class TestPostProcessTitle:
    """Tests for _post_process_title()."""

    def test_removes_quotes(self):
        result = _post_process_title('"Climate Change Debate"', "test")
        assert '"' not in result

    def test_removes_intro_text(self):
        result = _post_process_title("Here is the title: Climate Change", "test")
        assert "Here is" not in result

    def test_fallback_on_empty(self):
        result = _post_process_title("", "This is a test case.")
        assert result == _fallback_title("This is a test case.")

    def test_fallback_on_reflection(self):
        result = _post_process_title("Based on the description about climate", "test")
        assert result == _fallback_title("test")
