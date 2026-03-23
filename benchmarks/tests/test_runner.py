import yaml
from pathlib import Path
from benchmarks.harness.runner import load_task, build_run_plan

def test_load_task(tmp_path):
    task_yaml = {
        "id": "test-task",
        "name": "Test Task",
        "category": "practical",
        "url": "http://localhost/test",
        "requires_fixture": True,
        "description": "Do a test thing",
        "max_steps": 10,
        "timeout_seconds": 60,
        "success_criteria": [{"type": "no_errors"}],
        "tags": ["test"],
    }
    p = tmp_path / "test-task.yaml"
    p.write_text(yaml.dump(task_yaml))
    task = load_task(p)
    assert task["id"] == "test-task"
    assert task["max_steps"] == 10

def test_build_run_plan():
    tasks = [{"id": "t1"}, {"id": "t2"}]
    plan = build_run_plan(tasks, backends=["brow", "mcp-playwright"], runs=2)
    assert len(plan) == 8  # 2 tasks * 2 backends * 2 runs
    backends_per_task = [p["backend"] for p in plan if p["task"]["id"] == "t1"]
    assert "brow" in backends_per_task
    assert "mcp-playwright" in backends_per_task
