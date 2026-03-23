# Agent Benchmark: brow vs MCP Playwright

Research-grade benchmark measuring agent performance when using **brow CLI** vs **MCP Playwright** for browser automation tasks.

## Metrics

Ranked by priority:

| # | Metric | Description |
|---|--------|-------------|
| 1 | Token efficiency | Total input + output tokens per task |
| 2 | Tool call count | Agent-to-tool round trips |
| 3 | Task success rate | Binary pass/fail per task |
| 4 | Error recovery | Recoveries / errors encountered |
| 5 | Wall-clock time | End-to-end seconds per task |

Derived: cost estimate (tokens x model pricing), avg response size per tool call.

## Quick Start

```bash
pip install -r benchmarks/requirements.txt
playwright install chromium
export ANTHROPIC_API_KEY=sk-...

# Run all tasks, both backends, 3 runs each
python -m benchmarks --backend all --tasks all --runs 3

# Single backend, single task
python -m benchmarks --backend brow --tasks search-extract --runs 1
```

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--backend` | `all` | `brow`, `mcp-playwright`, or `all` |
| `--tasks` | `all` | Task ID(s), comma-separated |
| `--runs` | `3` | Runs per task per backend |
| `--model` | `claude-sonnet-4-20250514` | Claude model ID |
| `--output` | `benchmarks/results/` | Output directory |
| `--include-live` | off | Include optional live-web tasks |
| `--warmup` | `1` | Warmup runs to discard |

## Task Suite (10 tasks)

All tasks use a local fixture server for full reproducibility.

| Task | Category | Description |
|------|----------|-------------|
| search-extract | extraction | Search page, extract top 5 results as structured data |
| form-fill | interaction | Fill form fields, submit, verify confirmation |
| multi-page-nav | navigation | Visit 3 pages, extract specific data from each |
| login-auth | auth | Login, perform action behind authentication |
| dynamic-content | extraction | Wait for JS-rendered content, extract data |
| ecommerce-search | search | Find product matching criteria in catalog |
| info-lookup | research | Find specific fact across wiki-style pages |
| large-snapshot | stress | Page with 500+ elements, measures verbose output handling |
| error-recovery | resilience | Intermittent missing elements, measures retry behavior |
| rapid-multi-step | throughput | 10+ sequential interactions, measures overhead |

## Architecture

```
benchmarks/
  run.py              CLI entry point
  harness/
    config.py          Model pricing, API keys, defaults
    metrics.py         RunResult dataclass + aggregation
    agent.py           Claude API wrapper with tool call interception
    tools_brow.py      brow tool definitions
    tools_mcp.py       MCP Playwright tool definitions
    tools_common.py    submit_answer tool (shared)
    judge.py           Success criteria evaluation
    runner.py          Orchestrates runs (randomization, alternation)
    reporter.py        Markdown tables + raw JSON output
    server.py          Local fixture server lifecycle
  fixtures/            FastAPI app + static HTML pages
  tasks/               YAML task definitions
  results/             Generated reports and raw JSON
```

## How It Works

1. Fixture server starts on a random port
2. Agent receives system prompt + task via Claude API
3. Agent makes tool calls — harness executes via subprocess (brow) or MCP client
4. Each call logged: tokens, latency, response size, success/failure
5. Agent calls `submit_answer` when done (or hits max steps/timeout)
6. Judge evaluates success criteria
7. Reporter generates markdown comparison tables + raw JSON

Backends alternate between runs (brow run 1, mcp run 1, brow run 2, ...) to distribute temporal confounds. Warmup runs are discarded.

## Output

Results are saved to `benchmarks/results/`:
- `report.md` — summary table + per-task breakdown with mean +/- stddev
- Per-run JSON logs for programmatic analysis

## Design Spec

Full design document: [docs/superpowers/specs/2026-03-23-agent-benchmark-design.md](../docs/superpowers/specs/2026-03-23-agent-benchmark-design.md)
