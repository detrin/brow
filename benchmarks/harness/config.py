import os
from dataclasses import dataclass, field
from pathlib import Path

BENCHMARKS_DIR = Path(__file__).parent.parent

@dataclass
class BenchmarkConfig:
    model: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"
    runs: int = 3
    warmup: int = 1
    backends: list = field(default_factory=lambda: ["brow", "mcp-playwright"])
    tasks_dir: Path = field(default_factory=lambda: BENCHMARKS_DIR / "tasks")
    output_dir: Path = field(default_factory=lambda: BENCHMARKS_DIR / "results")
    include_live: bool = False
    fixture_port: int = 0
    pricing: dict = field(default_factory=lambda: {
        "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
        "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
        "claude-haiku-4-20250514": {"input": 0.25, "output": 1.25},
    })

    aws_profile: str = "bedrock-api"
    aws_region: str = "us-east-1"

    @property
    def api_key(self):
        return os.environ.get("ANTHROPIC_API_KEY", "")

    def estimate_cost(self, input_tokens, output_tokens):
        rates = self.pricing.get(self.model, {"input": 3.0, "output": 15.0})
        return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
