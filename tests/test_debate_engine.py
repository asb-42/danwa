import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
from src.core.debate_engine import DebateEngine
from src.core.trace_logger import TraceLogger
import tempfile

MOCK_RESPONSE = {
    "content": "Mock-Antwort",
    "tokens_used": 100,
    "model": "test-model",
    "finish_reason": "stop"
}

@pytest.fixture
def engine():
    with tempfile.TemporaryDirectory() as tmpdir:
        Path("config/prompts").mkdir(parents=True, exist_ok=True)
        # Minimal-Prompts für Test
        for role in ["strategist", "critic", "optimizer", "moderator"]:
            (Path("config/prompts") / f"{role}.md").write_text(f"---\nversion: v1\n---\nDu bist {role}.")
        
        eng = DebateEngine(profile_name="local_lm_studio", max_rounds=1, threshold=0.9, enable_memory=False, enable_fact_check=False)
        eng.logger = TraceLogger(tmpdir)
        return eng

@pytest.mark.asyncio
async def test_debate_runs_to_completion(engine):
    with patch.object(engine.router, "call", new_callable=AsyncMock) as mock_call:
        # Moderator liefert Konsens >= threshold
        async def side_effect(*args, **kwargs):
            if args[0].startswith("Du bist Moderator"):
                return {"content": "0.95", "tokens_used": 50, "model": "test", "finish_reason": "stop"}
            return MOCK_RESPONSE
        mock_call.side_effect = side_effect

        state = await engine.run("Test-Sachverhalt")
        assert state.final_consensus == 0.95
        assert len(state.rounds) == 1
        assert "Mock-Antwort" in state.output