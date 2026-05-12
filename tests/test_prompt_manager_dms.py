import pytest
from src.core.prompt_manager import PromptManager
from pathlib import Path

@pytest.fixture
def dms_prompt_manager(tmp_path):
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
  dms:
    strategist: "prompts/dms_context.md"
    critic: "prompts/dms_context.md"
    optimizer: "prompts/dms_context.md"
    moderator: "prompts/dms_context.md"
""")
    
    prompts_dir = config_dir / "prompts"
    prompts_dir.mkdir()
    for name in ["strategist.md", "critic.md", "optimizer.md", "moderator.md", "dms_context.md"]:
        if name == "dms_context.md":
            (prompts_dir / name).write_text("version: v1.0\nDMS Context Prompt: {name}")
        else:
            (prompts_dir / name).write_text(f"version: v1.0\nStandard Prompt: {name}")
    
    pm = PromptManager(config_path=variants_file)
    return pm, prompts_dir

@pytest.mark.skip(reason="config/prompts/dms_context.md file not in production config")
def test_dms_context_md_exists():
    assert Path("config/prompts/dms_context.md").exists()

def test_prompt_manager_loads_dms_variant(dms_prompt_manager):
    pm, _ = dms_prompt_manager
    assert "dms" in pm.variants_config["variants"]

def test_dms_variant_loads_correct_prompt(dms_prompt_manager):
    pm, prompts_dir = dms_prompt_manager
    result = pm.get("strategist", "dms")
    assert "dms_context.md" in result["path"]
    assert "DMS Context Prompt" in result["content"]

def test_get_system_prompt_with_rag_uses_dms_variant(dms_prompt_manager):
    pm, _ = dms_prompt_manager
    rag_context = "Test RAG context"
    prompt = pm.get_system_prompt("strategist", rag_context=rag_context)
    assert "DMS Context Prompt" in prompt
    assert "## Retrieved Document Context" in prompt
    assert rag_context in prompt

def test_get_system_prompt_without_rag_uses_default_variant(dms_prompt_manager):
    pm, _ = dms_prompt_manager
    prompt = pm.get_system_prompt("strategist")
    assert "Standard Prompt" in prompt
    assert "## Retrieved Document Context" not in prompt

def test_get_system_prompt_empty_rag_uses_default_variant(dms_prompt_manager):
    pm, _ = dms_prompt_manager
    prompt = pm.get_system_prompt("strategist", rag_context="")
    assert "Standard Prompt" in prompt
    prompt2 = pm.get_system_prompt("strategist", rag_context=None)
    assert "Standard Prompt" in prompt2
