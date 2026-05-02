"""Tests for the LLM service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.profiles import LLMProfile, LLMProvider
from backend.services.llm_service import LLMService
from backend.services.profile_service import ProfileService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_profile_service():
    """ProfileService that returns a test LLM profile."""
    service = MagicMock(spec=ProfileService)
    test_profile = LLMProfile(
        id="test-llm",
        name="Test LLM",
        provider=LLMProvider.OPENROUTER,
        model="openrouter/test-model",
        api_key_env="TEST_API_KEY",
        temperature=0.7,
        max_tokens=4096,
        timeout=30,
        cost_per_1k_input=0.001,
        cost_per_1k_output=0.002,
    )
    service.get_llm_profile.return_value = test_profile
    service.list_llm_profiles.return_value = [test_profile]
    return service


@pytest.fixture()
def llm_service(mock_profile_service):
    """LLMService with mocked profile service."""
    return LLMService(profile_id="test-llm", profile_service=mock_profile_service)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLLMServiceInit:
    def test_init_with_profile_id(self, mock_profile_service):
        service = LLMService(profile_id="test-llm", profile_service=mock_profile_service)
        assert service.profile is not None
        assert service.profile.id == "test-llm"

    def test_init_with_nonexistent_profile(self, mock_profile_service):
        mock_profile_service.get_llm_profile.return_value = None
        with pytest.raises(ValueError, match="not found"):
            LLMService(profile_id="nonexistent", profile_service=mock_profile_service)

    def test_init_without_profile_id_uses_first(self, mock_profile_service):
        service = LLMService(profile_service=mock_profile_service)
        assert service.profile is not None
        assert service.profile.id == "test-llm"

    def test_init_without_profiles(self):
        empty_service = MagicMock(spec=ProfileService)
        empty_service.list_llm_profiles.return_value = []
        service = LLMService(profile_service=empty_service)
        assert service.profile is None


class TestLLMServiceGenerate:
    @pytest.mark.asyncio
    async def test_generate_raises_without_profile(self):
        empty_service = MagicMock(spec=ProfileService)
        empty_service.list_llm_profiles.return_value = []
        service = LLMService(profile_service=empty_service)
        with pytest.raises(RuntimeError, match="No LLM profile"):
            await service.generate("test prompt")

    @pytest.mark.asyncio
    async def test_generate_raises_without_api_key(self, llm_service):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="API key not found"):
                await llm_service.generate("test prompt")

    @pytest.mark.asyncio
    async def test_generate_calls_litellm(self, llm_service):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20

        with patch.dict("os.environ", {"TEST_API_KEY": "sk-test-key"}):
            import litellm
            with patch.object(litellm, "acompletion", new_callable=AsyncMock, return_value=mock_response) as mock_ac:
                result = await llm_service.generate(
                    prompt="Test prompt",
                    system_prompt="You are a test agent.",
                )

                assert result == "Test response"
                mock_ac.assert_called_once()
                call_kwargs = mock_ac.call_args[1]
                assert call_kwargs["model"] == "openrouter/test-model"
                assert call_kwargs["temperature"] == 0.7
                assert call_kwargs["max_tokens"] == 4096

    @pytest.mark.asyncio
    async def test_generate_with_overrides(self, llm_service):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Override response"
        mock_response.usage = None

        with patch.dict("os.environ", {"TEST_API_KEY": "sk-test-key"}):
            import litellm
            with patch.object(litellm, "acompletion", new_callable=AsyncMock, return_value=mock_response) as mock_ac:
                result = await llm_service.generate(
                    prompt="Test",
                    temperature=0.3,
                    max_tokens=1024,
                )

                call_kwargs = mock_ac.call_args[1]
                assert call_kwargs["temperature"] == 0.3
                assert call_kwargs["max_tokens"] == 1024


class TestLLMServiceCostEstimation:
    def test_estimate_cost(self, llm_service):
        cost = llm_service.estimate_cost(input_tokens=1000, output_tokens=500)
        # 1000/1000 * 0.001 + 500/1000 * 0.002 = 0.001 + 0.001 = 0.002
        assert abs(cost - 0.002) < 0.0001

    def test_estimate_cost_no_costs(self):
        """Profile without cost fields should return 0."""
        service = MagicMock(spec=ProfileService)
        profile = LLMProfile(
            id="free-llm",
            name="Free LLM",
            provider=LLMProvider.LOCAL,
            model="local/model",
            cost_per_1k_input=None,
            cost_per_1k_output=None,
        )
        service.get_llm_profile.return_value = profile
        service.list_llm_profiles.return_value = [profile]

        llm = LLMService(profile_id="free-llm", profile_service=service)
        cost = llm.estimate_cost(input_tokens=1000, output_tokens=500)
        assert cost == 0.0
