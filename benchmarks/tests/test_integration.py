from unittest.mock import patch, MagicMock
from pathlib import Path

from benchmarks.harness.config import BenchmarkConfig
from benchmarks.harness.runner import load_all_tasks, build_run_plan
from benchmarks.harness.reporter import generate_report
from benchmarks.harness.metrics import RunResult

def test_full_pipeline_mocked():
    tasks_dir = Path(__file__).parent.parent / "tasks"
    tasks = load_all_tasks(tasks_dir)
    assert len(tasks) == 19

    plan = build_run_plan(tasks, ["brow", "mcp-playwright"], runs=1)
    assert len(plan) == 38

    results = []
    for item in plan:
        results.append(RunResult(
            task_id=item["task"]["id"], backend=item["backend"],
            model="claude-sonnet-4-20250514", success=True,
            total_input_tokens=2000, total_output_tokens=800,
            tool_calls=6, tool_call_log=[], wall_clock_ms=5000,
            errors=[], error_recoveries=0, final_output={},
            run_id="test", timestamp="t", brow_version="v",
            conversation_turns=6,
        ))

    cfg = BenchmarkConfig(runs=1)
    report = generate_report(results, cfg)
    assert "Summary" in report
    assert "brow" in report
    assert "search-extract" in report

def test_tasks_all_have_required_fields():
    tasks_dir = Path(__file__).parent.parent / "tasks"
    tasks = load_all_tasks(tasks_dir)
    required = ["id", "name", "category", "description", "max_steps", "timeout_seconds", "success_criteria"]
    for task in tasks:
        for field in required:
            assert field in task, f"Task {task.get('id', 'unknown')} missing field: {field}"
