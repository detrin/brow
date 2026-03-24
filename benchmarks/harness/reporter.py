import json
from dataclasses import asdict
from pathlib import Path

from benchmarks.harness.config import BenchmarkConfig
from benchmarks.harness.metrics import RunResult, aggregate_results

def generate_report(results: list[RunResult], config: BenchmarkConfig) -> str:
    lines = [f"## Benchmark Results ({config.model}, {config.runs} runs per task)\n"]

    by_backend = {}
    for r in results:
        by_backend.setdefault(r.backend, []).append(r)

    lines.append("### Summary")
    lines.append("| Metric | " + " | ".join(by_backend.keys()) + " | Delta |")
    lines.append("|--------|" + "|".join(["--------"] * len(by_backend)) + "|-------|")

    aggs = {b: aggregate_results(rs) for b, rs in by_backend.items()}
    backends = list(aggs.keys())

    def _fmt(a, key, std_key, fmt, scale=1):
        v = a[key] / scale
        s = fmt.format(v)
        if std_key:
            s += f"+/-{fmt.format(a[std_key] / scale)}"
        return s

    def _delta(key):
        if len(backends) != 2:
            return ""
        v0, v1 = aggs[backends[0]][key], aggs[backends[1]][key]
        return f"{(v0 - v1) / v1 * 100:+.0f}%" if v1 != 0 else ""

    metrics = [
        ("Avg tokens/task", "mean_tokens", "stddev_tokens", "{:.0f}", 1),
        ("Avg tool calls/task", "mean_tool_calls", "stddev_tool_calls", "{:.1f}", 1),
        ("Success rate", "success_rate", None, "{:.0%}", 1),
        ("Avg wall-clock (s)", "mean_wall_clock_ms", "stddev_wall_clock_ms", "{:.1f}", 1000),
    ]

    for label, key, std_key, fmt, scale in metrics:
        vals = [_fmt(aggs[b], key, std_key, fmt, scale) for b in backends]
        lines.append(f"| {label} | " + " | ".join(vals) + f" | {_delta(key)} |")

    cost_line_vals = []
    for b in backends:
        a = aggs[b]
        cost = config.estimate_cost(int(a["mean_input_tokens"]), int(a["mean_output_tokens"]))
        cost_line_vals.append(f"${cost:.4f}")
    cost_delta = ""
    if len(backends) == 2 and float(cost_line_vals[1].strip("$")) != 0:
        c0, c1 = float(cost_line_vals[0].strip("$")), float(cost_line_vals[1].strip("$"))
        cost_delta = f"{(c0 - c1) / c1 * 100:+.0f}%"
    lines.append(f"| Est. cost/task | " + " | ".join(cost_line_vals) + f" | {cost_delta} |")

    lines.append("\n### Per-Task Breakdown")
    lines.append("| Task | Backend | Tokens | Calls | Success | Time (s) |")
    lines.append("|------|---------|--------|-------|---------|----------|")

    by_task_backend = {}
    for r in results:
        by_task_backend.setdefault((r.task_id, r.backend), []).append(r)

    for (task_id, backend), rs in sorted(by_task_backend.items()):
        a = aggregate_results(rs)
        n = a["n"]
        successes = sum(1 for r in rs if r.success)
        tokens = f"{a['mean_tokens']:.0f}+/-{a['stddev_tokens']:.0f}"
        calls = f"{a['mean_tool_calls']:.1f}+/-{a['stddev_tool_calls']:.1f}"
        time_s = f"{a['mean_wall_clock_ms']/1000:.1f}+/-{a['stddev_wall_clock_ms']/1000:.1f}"
        lines.append(f"| {task_id} | {backend} | {tokens} | {calls} | {successes}/{n} | {time_s} |")

    return "\n".join(lines) + "\n"


def save_results_json(results: list[RunResult], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2, default=str)


def save_report(results: list[RunResult], config: BenchmarkConfig):
    config.output_dir.mkdir(parents=True, exist_ok=True)
    report = generate_report(results, config)
    (config.output_dir / "report.md").write_text(report)
    save_results_json(results, config.output_dir / "results.json")
    print(f"Report saved to {config.output_dir / 'report.md'}")
    print(f"Raw data saved to {config.output_dir / 'results.json'}")
