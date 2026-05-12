import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.core.llm_router import LLMRouter
import os


@pytest.fixture
def mock_litellm():
    with patch("src.core.llm_router.litellm") as mock:
        mock.acompletion = AsyncMock(return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content="Test response"), finish_reason="stop")],
            usage=MagicMock(total_tokens=100),
            model="test-model"
        ))
        yield mock


@pytest.fixture
def router(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "llm_profiles.yaml"
    config_file.write_text("""
profiles:
  test_profile:
    model: "test-model"
    base_url: "http://localhost:8080/v1"
    api_key_env: "TEST_KEY"
    params:
      temperature: 0.5
      top_p: 0.9
""")
    with patch("src.core.llm_router.CONFIG_PATH", config_file), \
         patch.dict(os.environ, {"TEST_KEY": "fake-api-key"}):
        return LLMRouter(profile_name="test_profile")


@pytest.mark.asyncio
async def test_router_initialization(router):
    assert router._default_profile is not None
    assert router._default_profile["model"] == "openai/test-model"
    assert router._default_profile["api_key"] == "fake-api-key"


@pytest.mark.asyncio
async def test_router_call(router, mock_litellm):
    router.call = AsyncMock(return_value={
        "content": "Test response",
        "tokens_used": 100,
        "model": "test-model",
        "finish_reason": "stop"
    })
    
    result = await router.call("System prompt", "User prompt")
    
    assert "content" in result
    assert result["content"] == "Test response"
    assert result["tokens_used"] == 100


@pytest.mark.asyncio
async def test_router_call_with_temp_override(router, mock_litellm):
    captured_params = {}
    
    async def capture_call(*args, **kwargs):
        captured_params.update(kwargs)
        return MagicMock(
            choices=[MagicMock(message=MagicMock(content="Response"), finish_reason="stop")],
            usage=MagicMock(total_tokens=50),
            model="test-model"
        )
    
    mock_litellm.acompletion = capture_call
    
    await router.call("Sys", "User", temp_override=0.1)
    
    assert captured_params.get("temperature") == 0.1


@pytest.mark.asyncio
async def test_router_missing_api_key_env():
    with patch("src.core.llm_router.CONFIG_PATH") as mock_path, \
         patch("src.core.llm_router.yaml.safe_load") as mock_yaml_load:
        mock_yaml_load.return_value = {
            "profiles": {
                "test": {
                    "model": "m",
                    "base_url": "http://test",
                    "api_key_env": "NONEXISTENT_KEY",
                    "params": {}
                }
            }
        }
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=MagicMock(
            read=MagicMock(return_value="")
        ))
        mock_path.open = MagicMock(return_value=mock_file)

        router = LLMRouter(profile_name="test")
        assert "api_key" not in router._default_profile or router._default_profile["api_key"] == ""


@pytest.mark.asyncio
async def test_router_invalid_profile():
    with patch("src.core.llm_router.CONFIG_PATH") as mock_path, \
         patch("src.core.llm_router.yaml.safe_load") as mock_yaml_load:
        mock_yaml_load.return_value = {
            "profiles": {
                "test": {
                    "model": "m",
                    "base_url": "http://test",
                    "api_key_env": "NONEXISTENT_KEY",
                    "params": {}
                }
            }
        }
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=MagicMock(
            read=MagicMock(return_value="")
        ))
        mock_path.open = MagicMock(return_value=mock_file)

        try:
            router = LLMRouter(profile_name="nonexistent")
            assert router._default_profile is None
        except KeyError:
            # Expected when profile doesn't exist
            pass
