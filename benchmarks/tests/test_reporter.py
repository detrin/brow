from benchmarks.harness.reporter import generate_report, save_results_json
from benchmarks.harness.metrics import RunResult
from benchmarks.harness.config import BenchmarkConfig

def _make_result(task_id, backend, tokens_in, tokens_out, calls, success, wall_ms):
    return RunResult(
        task_id=task_id, backend=backend, model="claude-sonnet-4-20250514",
        success=success, total_input_tokens=tokens_in, total_output_tokens=tokens_out,
        tool_calls=calls, tool_call_log=[], wall_clock_ms=wall_ms,
        errors=[], error_recoveries=0, final_output={},
        run_id="r1", timestamp="t", brow_version="v", conversation_turns=calls,
    )

def test_generate_report():
    results = [
        _make_result("t1", "brow", 1000, 500, 5, True, 3000),
        _make_result("t1", "brow", 1200, 600, 6, True, 3500),
        _make_result("t1", "mcp-playwright", 3000, 1500, 12, True, 8000),
        _make_result("t1", "mcp-playwright", 3200, 1600, 14, False, 9000),
    ]
    cfg = BenchmarkConfig()
    report = generate_report(results, cfg)
    assert "Summary" in report
    assert "brow" in report
    assert "mcp-playwright" in report or "MCP" in report

def test_save_results_json(tmp_path):
    results = [_make_result("t1", "brow", 1000, 500, 5, True, 3000)]
    save_results_json(results, tmp_path / "results.json")
    assert (tmp_path / "results.json").exists()
