import statistics
from dataclasses import dataclass, field

@dataclass
class ToolCallRecord:
    name: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    response_bytes: int
    success: bool
    error: str | None

@dataclass
class RunResult:
    task_id: str
    backend: str
    model: str
    success: bool
    total_input_tokens: int
    total_output_tokens: int
    tool_calls: int
    tool_call_log: list[ToolCallRecord]
    wall_clock_ms: int
    errors: list[str]
    error_recoveries: int
    final_output: dict
    run_id: str
    timestamp: str
    brow_version: str
    conversation_turns: int

    @property
    def total_tokens(self):
        return self.total_input_tokens + self.total_output_tokens

def aggregate_results(results: list[RunResult]) -> dict:
    tokens = [r.total_tokens for r in results]
    input_tokens = [r.total_input_tokens for r in results]
    output_tokens = [r.total_output_tokens for r in results]
    calls = [r.tool_calls for r in results]
    times = [r.wall_clock_ms for r in results]
    successes = [r.success for r in results]
    n = len(results)
    return {
        "n": n,
        "mean_tokens": statistics.mean(tokens),
        "stddev_tokens": statistics.stdev(tokens) if n > 1 else 0.0,
        "mean_input_tokens": statistics.mean(input_tokens),
        "mean_output_tokens": statistics.mean(output_tokens),
        "mean_tool_calls": statistics.mean(calls),
        "stddev_tool_calls": statistics.stdev(calls) if n > 1 else 0.0,
        "mean_wall_clock_ms": statistics.mean(times),
        "stddev_wall_clock_ms": statistics.stdev(times) if n > 1 else 0.0,
        "success_rate": sum(successes) / n,
        "mean_errors": statistics.mean([len(r.errors) for r in results]),
        "mean_recoveries": statistics.mean([r.error_recoveries for r in results]),
    }
