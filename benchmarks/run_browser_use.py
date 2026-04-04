"""
browser-use benchmark runner.

Runs the same fixture tasks as the main harness but using browser-use's own
agent loop (with Claude via Anthropic API or AWS Bedrock as the LLM).

Results are saved to benchmarks/results/ and printed as a Markdown table
comparable to the main harness output.

Usage:
  python -m benchmarks.run_browser_use --runs 1 --warmup 0
  python -m benchmarks.run_browser_use --tasks info-lookup,ecommerce-search --runs 1
"""

import argparse
import asyncio
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import boto3
import yaml

from benchmarks.harness.config import BenchmarkConfig, BENCHMARKS_DIR
from benchmarks.harness.judge import evaluate_all
from benchmarks.harness.metrics import RunResult, aggregate_results
from benchmarks.harness.reporter import save_report
from benchmarks.harness.server import FixtureServer


def _build_llm(config: BenchmarkConfig):
    if config.api_key:
        from browser_use.llm.anthropic.chat import ChatAnthropic
        # Map Bedrock cross-region model ID to plain Anthropic model ID
        model = config.model
        model = re.sub(r'^(us|eu|ap)\.', '', model)   # strip region prefix
        model = re.sub(r'-v\d+:\d+$', '', model)       # strip -v1:0 suffix
        return ChatAnthropic(model=model, api_key=config.api_key, max_tokens=4096)
    else:
        from browser_use.llm.aws.chat_bedrock import ChatAWSBedrock
        session = boto3.Session(profile_name=config.aws_profile)
        creds = session.get_credentials().get_frozen_credentials()
        return ChatAWSBedrock(
            model=config.model,
            max_tokens=4096,
            aws_access_key_id=creds.access_key,
            aws_secret_access_key=creds.secret_key,
            aws_session_token=creds.token,
            aws_region=config.aws_region,
        )


def _parse_final_result(history) -> dict:
    """Try to parse browser-use's text final_result into a dict for the judge."""
    text = history.final_result() or ""
    # Try JSON block first
    match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```', text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Try bare JSON
    match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Return as plain text answer for any text-match criteria
    return {"result": text}


async def run_browser_use_task(task: dict, llm, fixture_url: str | None) -> RunResult:
    from browser_use import Agent, BrowserProfile

    description = task["description"]
    if fixture_url:
        description = description.replace("FIXTURE_URL", fixture_url)

    profile = BrowserProfile(headless=True)
    agent = Agent(
        task=description,
        llm=llm,
        browser_profile=profile,
        use_vision=False,       # fair comparison: no screenshots
        calculate_cost=True,
        max_failures=3,
        enable_signal_handler=False,
    )

    start = time.time()
    try:
        history = await agent.run(max_steps=task.get("max_steps", 15))
    except Exception as e:
        wall_ms = int((time.time() - start) * 1000)
        return RunResult(
            task_id=task["id"],
            backend="browser-use",
            model=str(llm),
            success=False,
            total_input_tokens=0,
            total_output_tokens=0,
            tool_calls=0,
            tool_call_log=[],
            wall_clock_ms=wall_ms,
            errors=[str(e)],
            error_recoveries=0,
            final_output={},
            run_id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(timezone.utc).isoformat(),
            brow_version="n/a",
            conversation_turns=0,
        )
    wall_ms = int((time.time() - start) * 1000)

    # Token counts
    usage = getattr(history, 'usage', None)
    input_tokens = usage.total_prompt_tokens if usage else 0
    output_tokens = usage.total_completion_tokens if usage else 0

    # Steps = number of agent steps taken
    steps = history.number_of_steps() if hasattr(history, 'number_of_steps') else 0

    # Parse final answer
    final_output = _parse_final_result(history)

    # Collect errors from history
    errors = history.errors() if hasattr(history, 'errors') else []
    errors = [str(e) for e in errors] if errors else []

    # Evaluate success using our judge (same criteria as all other backends)
    browser_state = {"url": (history.urls() or [""])[-1]}
    success = evaluate_all(
        task.get("success_criteria", []),
        final_output,
        browser_state,
        errors=errors,
    )

    return RunResult(
        task_id=task["id"],
        backend="browser-use",
        model=str(type(llm).__name__),
        success=success,
        total_input_tokens=input_tokens,
        total_output_tokens=output_tokens,
        tool_calls=steps,
        tool_call_log=[],
        wall_clock_ms=wall_ms,
        errors=errors,
        error_recoveries=0,
        final_output=final_output,
        run_id=str(uuid.uuid4())[:8],
        timestamp=datetime.now(timezone.utc).isoformat(),
        brow_version="n/a",
        conversation_turns=steps,
    )


def load_all_tasks(task_ids=None, include_live=False):
    tasks_dir = BENCHMARKS_DIR / "tasks"
    tasks = []
    for p in sorted(tasks_dir.glob("*.yaml")):
        with open(p) as f:
            task = yaml.safe_load(f)
        if task_ids and task["id"] not in task_ids:
            continue
        if not include_live and not task.get("requires_fixture", True):
            continue
        tasks.append(task)
    return tasks


async def run_benchmark(config: BenchmarkConfig, task_ids=None):
    tasks = load_all_tasks(task_ids, config.include_live)
    if not tasks:
        print("No tasks found")
        return []

    llm = _build_llm(config)

    server = None
    fixture_url = None
    if any(t.get("requires_fixture") for t in tasks):
        server = FixtureServer()
        await server.start()
        fixture_url = server.base_url

    results = []
    total = len(tasks) * config.runs
    i = 0

    for run_idx in range(config.runs):
        for task in tasks:
            i += 1
            print(f"  [{i}/{total}] {task['id']} / browser-use (run {run_idx + 1})")
            result = await run_browser_use_task(task, llm, fixture_url)
            results.append(result)

    if server:
        await server.stop()

    return results


def main():
    parser = argparse.ArgumentParser(description="browser-use benchmark")
    parser.add_argument("--tasks", default="all")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--model", default="us.anthropic.claude-sonnet-4-20250514-v1:0")
    parser.add_argument("--output", default=None)
    parser.add_argument("--include-live", action="store_true")
    parser.add_argument("--warmup", type=int, default=0)
    args = parser.parse_args()

    task_ids = None if args.tasks == "all" else args.tasks.split(",")

    config = BenchmarkConfig(
        model=args.model,
        runs=args.runs,
        warmup=args.warmup,
        backends=["browser-use"],
        include_live=args.include_live,
    )
    if args.output:
        config.output_dir = Path(args.output)

    if not config.api_key:
        print("No ANTHROPIC_API_KEY set, using AWS Bedrock")

    print(f"Running browser-use benchmark: {config.model}, {config.runs} runs")
    results = asyncio.run(run_benchmark(config, task_ids))

    if results:
        save_report(results, config)
    else:
        print("No results collected")


if __name__ == "__main__":
    main()
