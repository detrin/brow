import argparse
import asyncio
import sys

from benchmarks.harness.config import BenchmarkConfig
from benchmarks.harness.runner import run_benchmark
from benchmarks.harness.reporter import save_report

def main():
    parser = argparse.ArgumentParser(description="brow vs MCP Playwright benchmark")
    parser.add_argument("--backend", default="all", choices=["brow", "mcp-playwright", "all"])
    parser.add_argument("--tasks", default="all", help="Task IDs (comma-separated) or 'all'")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--model", default="claude-sonnet-4-20250514")
    parser.add_argument("--output", default=None)
    parser.add_argument("--include-live", action="store_true")
    parser.add_argument("--warmup", type=int, default=1)
    args = parser.parse_args()

    if args.backend == "all":
        backends = ["brow", "mcp-playwright"]
    else:
        backends = [args.backend]

    task_ids = None if args.tasks == "all" else args.tasks.split(",")

    config = BenchmarkConfig(
        model=args.model,
        runs=args.runs,
        warmup=args.warmup,
        backends=backends,
        include_live=args.include_live,
    )
    if args.output:
        from pathlib import Path
        config.output_dir = Path(args.output)

    if not config.api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    print(f"Running benchmark: {config.model}, {config.runs} runs, backends: {backends}")
    results = asyncio.run(run_benchmark(config, task_ids))

    if results:
        save_report(results, config)
    else:
        print("No results collected")

if __name__ == "__main__":
    main()
