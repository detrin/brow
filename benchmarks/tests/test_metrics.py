from benchmarks.harness.metrics import RunResult, ToolCallRecord, aggregate_results

def test_tool_call_record():
    rec = ToolCallRecord(
        name="navigate", input_tokens=100, output_tokens=50,
        latency_ms=500, response_bytes=1024, success=True, error=None
    )
    assert rec.name == "navigate"
    assert rec.success is True

def test_run_result_total_tokens():
    r = RunResult(
        task_id="test", backend="brow", model="claude-sonnet-4-20250514",
        success=True, total_input_tokens=1000, total_output_tokens=500,
        tool_calls=3, tool_call_log=[], wall_clock_ms=5000,
        errors=[], error_recoveries=0, final_output={},
        run_id="r1", timestamp="2026-03-23T00:00:00", brow_version="0.1.4",
        conversation_turns=5
    )
    assert r.total_tokens == 1500

def test_aggregate_results():
    results = [
        RunResult(
            task_id="t1", backend="brow", model="m", success=True,
            total_input_tokens=1000, total_output_tokens=500, tool_calls=5,
            tool_call_log=[], wall_clock_ms=3000, errors=[], error_recoveries=0,
            final_output={}, run_id="r1", timestamp="t", brow_version="v",
            conversation_turns=5
        ),
        RunResult(
            task_id="t1", backend="brow", model="m", success=True,
            total_input_tokens=1200, total_output_tokens=600, tool_calls=7,
            tool_call_log=[], wall_clock_ms=4000, errors=[], error_recoveries=0,
            final_output={}, run_id="r2", timestamp="t", brow_version="v",
            conversation_turns=6
        ),
    ]
    agg = aggregate_results(results)
    assert agg["mean_tokens"] == 1650.0
    assert agg["mean_tool_calls"] == 6.0
    assert agg["success_rate"] == 1.0
    assert agg["n"] == 2
