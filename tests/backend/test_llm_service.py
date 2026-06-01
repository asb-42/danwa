"""Tests for the LLM service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.profiles import LLMProfile, LLMProvider
from backend.services.llm_service import GenerationResult, LLMService
from backend.services.profile_service import ProfileService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_profile_service():
    """ProfileService that returns a test LLM profile (cloud/openrouter)."""
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
def mock_local_profile_service():
    """ProfileService that returns a local LLM profile (LM Studio)."""
    service = MagicMock(spec=ProfileService)
    local_profile = LLMProfile(
        id="local-test",
        name="Local Test LLM",
        provider=LLMProvider.LOCAL,
        model="test/model",
        api_base="http://localhost:1234/v1",
        api_key_env="LOCAL_TEST_KEY",
        temperature=0.5,
        max_tokens=2048,
        timeout=60,
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0,
    )
    service.get_llm_profile.return_value = local_profile
    service.list_llm_profiles.return_value = [local_profile]
    return service


@pytest.fixture()
def llm_service(mock_profile_service):
    """LLMService with mocked profile service (cloud)."""
    return LLMService(profile_id="test-llm", profile_service=mock_profile_service)


@pytest.fixture()
def local_llm_service(mock_local_profile_service):
    """LLMService with mocked local profile service."""
    return LLMService(profile_id="local-test", profile_service=mock_local_profile_service)


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

                assert isinstance(result, GenerationResult)
                assert result.content == "Test response"
                assert result.tokens_in == 10
                assert result.tokens_out == 20
                assert result.model == "openrouter/test-model"
                assert result.duration_ms >= 0
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

                assert isinstance(result, GenerationResult)
                assert result.content == "Override response"
                assert result.tokens_in == 0
                assert result.tokens_out == 0
                call_kwargs = mock_ac.call_args[1]
                assert call_kwargs["temperature"] == 0.3
                assert call_kwargs["max_tokens"] == 1024


class TestLLMServiceLocal:
    """Tests for the local provider path (direct HTTP via httpx)."""

    @pytest.mark.asyncio
    async def test_local_generate_uses_httpx(self, local_llm_service):
        """Local providers should call httpx.post, not litellm."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.raise_for_status = MagicMock()
        mock_http_response.json.return_value = {
            "choices": [{"message": {"content": "Local response"}}],
            "usage": {"prompt_tokens": 15, "completion_tokens": 25},
        }

        with patch("backend.services.llm_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_http_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await local_llm_service.generate(
                prompt="Test local prompt",
                system_prompt="You are local.",
            )

            assert isinstance(result, GenerationResult)
            assert result.content == "Local response"
            assert result.tokens_in == 15
            assert result.tokens_out == 25
            assert result.model == "test/model"
            assert result.duration_ms >= 0
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            # URL should be the chat completions endpoint
            assert "/chat/completions" in call_args[0][0]
            # Payload should contain the model name as-is
            payload = call_args[1]["json"]
            assert payload["model"] == "test/model"
            assert payload["temperature"] == 0.5
            assert payload["max_tokens"] == 2048

    @pytest.mark.asyncio
    async def test_local_generate_no_api_key_needed(self, local_llm_service):
        """Local providers should work without an API key."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.raise_for_status = MagicMock()
        mock_http_response.json.return_value = {
            "choices": [{"message": {"content": "No key response"}}],
        }

        with patch.dict("os.environ", {}, clear=True):
            with patch("backend.services.llm_service.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_http_response
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                result = await local_llm_service.generate("Test")
                assert isinstance(result, GenerationResult)
                assert result.content == "No key response"
                assert result.tokens_in == 0
                assert result.tokens_out == 0

    @pytest.mark.asyncio
    async def test_local_generate_raises_without_api_base(self, mock_local_profile_service):
        """Local profile without api_base should raise ValueError."""
        profile = LLMProfile(
            id="local-no-base",
            name="Local No Base",
            provider=LLMProvider.LOCAL,
            model="test/model",
            api_base=None,
            api_key_env="X",
            temperature=0.5,
            max_tokens=2048,
            timeout=60,
        )
        mock_local_profile_service.get_llm_profile.return_value = profile
        service = LLMService(profile_id="local-no-base", profile_service=mock_local_profile_service)

        with pytest.raises(ValueError, match="requires api_base"):
            await service.generate("Test")


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


# ---------------------------------------------------------------------------
# Tool-calling support
# ---------------------------------------------------------------------------


class TestGenerationResultToolCalls:
    def test_tool_calls_field_default_none(self):
        result = GenerationResult(content="hello")
        assert result.tool_calls is None

    def test_tool_calls_field_with_data(self):
        tc = [{"id": "call_1", "type": "function", "function": {"name": "test", "arguments": "{}"}}]
        result = GenerationResult(content=None, tool_calls=tc)
        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["function"]["name"] == "test"


class TestGenerateWithTools:
    @pytest.mark.asyncio
    async def test_tools_parameter_accepted(self, mock_profile_service):
        """generate() should accept a tools parameter without error."""
        llm = LLMService(profile_id="test-llm", profile_service=mock_profile_service)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Here is the result"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.model = "test-model"

        tools = [{"type": "function", "function": {"name": "test_fn", "parameters": {}}}]

        with patch.dict("os.environ", {"TEST_API_KEY": "sk-test-key"}):
            with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
                result = await llm.generate(
                    prompt="test",
                    system_prompt="system",
                    tools=tools,
                )
        assert result.content == "Here is the result"
        assert result.tool_calls is None

    @pytest.mark.asyncio
    async def test_tool_calls_parsed_from_response(self, mock_profile_service):
        """generate() should parse tool_calls from the LLM response."""
        llm = LLMService(profile_id="test-llm", profile_service=mock_profile_service)

        mock_tc = MagicMock()
        mock_tc.id = "call_123"
        mock_tc.type = "function"
        mock_tc.function.name = "list_debates"
        mock_tc.function.arguments = '{"status": "all"}'

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [mock_tc]
        mock_response.choices[0].message.role = "assistant"
        mock_response.choices[0].message.refusal = None
        mock_response.choices[0].message.provider_specific_fields = {}
        mock_response.choices[0].finish_reason = "tool_calls"
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 10
        mock_response.model = "test-model"

        with patch.dict("os.environ", {"TEST_API_KEY": "sk-test-key"}):
            with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
                result = await llm.generate(
                    prompt="list my debates",
                    system_prompt="system",
                    tools=[{"type": "function", "function": {"name": "list_debates", "parameters": {}}}],
                )

        # Content is None in the response, but LLMService may extract from
        # provider_specific_fields or set to empty string — the important
        # assertion is that tool_calls are correctly parsed.
        assert result.tool_calls is not None
        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["id"] == "call_123"
        assert result.tool_calls[0]["function"]["name"] == "list_debates"

    @pytest.mark.asyncio
    async def test_no_tools_parameter_omitted_from_request(self, mock_profile_service):
        """When tools=None, no tools key should be in the kwargs."""
        llm = LLMService(profile_id="test-llm", profile_service=mock_profile_service)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ok"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 5
        mock_response.model = "test-model"

        with patch.dict("os.environ", {"TEST_API_KEY": "sk-test-key"}):
            with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as mock_ac:
                await llm.generate(prompt="test", system_prompt="system")

        call_kwargs = mock_ac.call_args[1]
        assert "tools" not in call_kwargs
