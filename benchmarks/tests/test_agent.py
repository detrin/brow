from unittest.mock import AsyncMock, patch, MagicMock
from benchmarks.harness.agent import AgentLoop, build_system_prompt
from benchmarks.harness.config import BenchmarkConfig

def test_build_system_prompt_brow():
    prompt = build_system_prompt("brow", "Find the top 5 coffee shops")
    assert "browser automation agent" in prompt.lower()
    assert "brow" in prompt.lower()
    assert "coffee shops" in prompt

def test_build_system_prompt_mcp():
    prompt = build_system_prompt("mcp-playwright", "Fill the form")
    assert "browser automation agent" in prompt.lower()
    assert "playwright" in prompt.lower()
    assert "form" in prompt

def test_agent_loop_init():
    cfg = BenchmarkConfig()
    loop = AgentLoop(config=cfg, backend="brow", task_description="test task")
    assert loop.backend == "brow"
    assert loop.messages == []
    assert loop.total_input_tokens == 0
    assert loop.total_output_tokens == 0
