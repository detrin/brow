import os
from benchmarks.harness.config import BenchmarkConfig

def test_default_config():
    cfg = BenchmarkConfig()
    assert cfg.model == "claude-sonnet-4-20250514"
    assert cfg.runs == 3
    assert cfg.warmup == 1
    assert cfg.backends == ["brow", "mcp-playwright"]
    assert cfg.tasks_dir.name == "tasks"
    assert isinstance(cfg.pricing, dict)

def test_config_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    cfg = BenchmarkConfig()
    assert cfg.api_key == "test-key"

def test_config_cost_estimate():
    cfg = BenchmarkConfig()
    cost = cfg.estimate_cost(input_tokens=1000, output_tokens=500)
    assert isinstance(cost, float)
    assert cost > 0
