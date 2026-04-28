import pytest
from unittest.mock import patch, MagicMock
from src.core.prompt_manager import PromptManager
from pathlib import Path
import tempfile


@pytest.fixture
def prompt_manager(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    variants_file = config_dir / "prompt_variants.yaml"
    variants_file.write_text("""
default_variant: "A"
variants:
  A:
    strategist: "prompts/strategist.md"
    critic: "prompts/critic.md"
    optimizer: "prompts/optimizer.md"
    moderator: "prompts/moderator.md"
  B:
    strategist: "prompts/strategist_v2.md"
    critic: "prompts/critic.md"
    optimizer: "prompts/optimizer.md"
    moderator: "prompts/moderator_v2.md"
""")
    
    prompts_dir = config_dir / "prompts"
    prompts_dir.mkdir()
    for name in ["strategist.md", "critic.md", "optimizer.md", "moderator.md", 
                "strategist_v2.md", "moderator_v2.md"]:
        (prompts_dir / name).write_text(f"version: v1.0\nDu bist {name}.")
    
    with patch("src.core.prompt_manager.Path", return_value=config_dir / "prompt_variants.yaml"):
        pm = PromptManager(config_path=variants_file)
        pm.config_path = variants_file
        pm.variants_config = {
            "default_variant": "A",
            "variants": {
                "A": {
                    "strategist": "prompts/strategist.md",
                    "critic": "prompts/critic.md",
                    "optimizer": "prompts/optimizer.md",
                    "moderator": "prompts/moderator.md"
                },
                "B": {
                    "strategist": "prompts/strategist_v2.md",
                    "critic": "prompts/critic.md",
                    "optimizer": "prompts/optimizer.md",
                    "moderator": "prompts/moderator_v2.md"
                }
            }
        }
        return pm, prompts_dir


def test_prompt_manager_loads_config(prompt_manager):
    pm, _ = prompt_manager
    assert pm.default_variant == "A"
    assert "A" in pm.variants_config["variants"]
    assert "B" in pm.variants_config["variants"]


def test_prompt_manager_get(prompt_manager):
    pm, prompts_dir = prompt_manager
    
    result = pm.get("strategist", "A")
    
    assert "content" in result
    assert "version" in result
    assert "hash" in result
    assert result["version"] == "v1.0"


def test_prompt_manager_get_variant_b(prompt_manager):
    pm, prompts_dir = prompt_manager
    
    result = pm.get("strategist", "B")
    
    assert "v2" in result["content"] or "v2" in result["path"]


def test_prompt_manager_get_caches(prompt_manager):
    pm, prompts_dir = prompt_manager
    
    result1 = pm.get("strategist", "A")
    result2 = pm.get("strategist", "A")
    
    assert result1["mtime"] == result2["mtime"]
    assert len(pm.cache) == 1


def test_prompt_manager_hot_reload(prompt_manager):
    pm, prompts_dir = prompt_manager
    
    result1 = pm.get("strategist", "A")
    original_mtime = result1["mtime"]
    
    import time
    time.sleep(0.1)
    prompts_dir.joinpath("strategist.md").write_text("version: v1.1\nNew content.")
    
    result2 = pm.get("strategist", "A")
    
    assert result2["mtime"] > original_mtime
    assert result2["version"] == "v1.1"


def test_prompt_manager_invalid_role(prompt_manager):
    pm, _ = prompt_manager
    
    with pytest.raises(ValueError):
        pm.get("nonexistent", "A")


def test_prompt_manager_invalid_variant(prompt_manager):
    pm, _ = prompt_manager
    
    with pytest.raises(ValueError):
        pm.get("strategist", "Z")


def test_assign_variant_deterministic(prompt_manager):
    pm, _ = prompt_manager
    
    variant1 = pm.assign_variant("session123")
    variant2 = pm.assign_variant("session123")
    
    assert variant1 == variant2


def test_assign_variant_different_sessions(prompt_manager):
    pm, _ = prompt_manager
    
    variant1 = pm.assign_variant("session123")
    variant2 = pm.assign_variant("session456")
    
    assert variant1 in pm.variants_config["variants"]
    assert variant2 in pm.variants_config["variants"]


def test_assign_variant_no_variants():
    pm = PromptManager.__new__(PromptManager)
    pm.variants_config = {"variants": {}}
    
    result = pm.assign_variant("test")
    
    assert result == "A"


def test_parse_prompt(prompt_manager):
    pm, prompts_dir = prompt_manager
    
    result = pm._parse_prompt("prompts/strategist.md")
    
    assert "content" in result
    assert "version" in result
    assert "hash" in result
    assert len(result["hash"]) == 16
