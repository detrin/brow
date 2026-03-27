import asyncio
import json
import random
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from benchmarks.harness.agent import AgentLoop
from benchmarks.harness.config import BenchmarkConfig
from benchmarks.harness.judge import evaluate_all
from benchmarks.harness.metrics import RunResult
from benchmarks.harness.server import FixtureServer
from benchmarks.harness.tools_brow import execute_brow_tool

def load_task(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)

def load_all_tasks(tasks_dir: Path, task_ids=None, include_live=False) -> list[dict]:
    tasks = []
    for p in sorted(tasks_dir.glob("*.yaml")):
        task = load_task(p)
        if task_ids and task["id"] not in task_ids:
            continue
        if not include_live and not task.get("requires_fixture", True):
            continue
        tasks.append(task)
    return tasks

def build_run_plan(tasks, backends, runs):
    plan = []
    for run_idx in range(runs):
        shuffled = list(tasks)
        random.shuffle(shuffled)
        for task in shuffled:
            for backend in backends:
                plan.append({"task": task, "backend": backend, "run_idx": run_idx})
    return plan

async def _get_browser_state(agent):
    state = {"url": ""}
    if agent.backend == "brow" and agent._brow_session_id:
        try:
            result = await execute_brow_tool("brow_url", {"session": agent._brow_session_id})
            state["url"] = result.get("output", "").strip()
        except Exception:
            pass
    return state

def _get_brow_version():
    try:
        import subprocess
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"

async def run_single(task, backend, config: BenchmarkConfig, fixture_url=None):
    url = task.get("url", "")
    if task.get("requires_fixture") and fixture_url:
        url = url.replace("FIXTURE_URL", fixture_url)
        task = {**task, "url": url, "description": task["description"].replace("FIXTURE_URL", fixture_url)}

    agent = AgentLoop(config=config, backend=backend, task_description=task["description"])
    start = time.time()
    final_output = await agent.run(
        max_steps=task.get("max_steps", 15),
        timeout_seconds=task.get("timeout_seconds", 120),
    )
    wall_clock_ms = int((time.time() - start) * 1000)

    browser_state = await _get_browser_state(agent)
    success = evaluate_all(
        task.get("success_criteria", []),
        final_output,
        browser_state,
        errors=agent.errors,
    )

    return RunResult(
        task_id=task["id"],
        backend=backend,
        model=config.model,
        success=success,
        total_input_tokens=agent.total_input_tokens,
        total_output_tokens=agent.total_output_tokens,
        tool_calls=len(agent.tool_call_log),
        tool_call_log=agent.tool_call_log,
        wall_clock_ms=wall_clock_ms,
        errors=agent.errors,
        error_recoveries=agent.error_recoveries,
        final_output=final_output,
        run_id=str(uuid.uuid4())[:8],
        timestamp=datetime.now(timezone.utc).isoformat(),
        brow_version=_get_brow_version(),
        conversation_turns=agent.conversation_turns,
    )

async def run_benchmark(config: BenchmarkConfig, task_ids=None):
    tasks = load_all_tasks(config.tasks_dir, task_ids, config.include_live)
    if not tasks:
        print("No tasks found")
        return []

    needs_fixture = any(t.get("requires_fixture") for t in tasks)
    server = None
    fixture_url = None

    if needs_fixture:
        server = FixtureServer()
        await server.start()
        fixture_url = server.base_url

    plan = build_run_plan(tasks, config.backends, config.runs)

    warmup_plan = build_run_plan(tasks[:1], config.backends, config.warmup)
    for item in warmup_plan:
        print(f"  warmup: {item['task']['id']} / {item['backend']}")
        await run_single(item["task"], item["backend"], config, fixture_url)

    results = []
    total = len(plan)
    for i, item in enumerate(plan, 1):
        print(f"  [{i}/{total}] {item['task']['id']} / {item['backend']} (run {item['run_idx'] + 1})")
        result = await run_single(item["task"], item["backend"], config, fixture_url)
        results.append(result)

    if server:
        await server.stop()

    return results
