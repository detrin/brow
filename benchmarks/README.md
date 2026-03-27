# Browser Automation Benchmarks

Compares **brow**, **playwright-cli**, and **MCP Playwright** as browser automation backends for an LLM agent loop (Claude Sonnet on AWS Bedrock).

## Quick Start

```bash
pip install -r benchmarks/requirements.txt
playwright install chromium

# All backends, all fixture tasks
python -m benchmarks.run --backend all --runs 1

# Single backend, specific task
python -m benchmarks.run --backend brow --tasks info-lookup --runs 1

# Include live (non-fixture) tasks
python -m benchmarks.run --backend brow --tasks vacuum-research --include-live --warmup 0 --runs 1
```

### CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--backend` | `all` | `brow`, `mcp-playwright`, `playwright-cli`, or `all` |
| `--tasks` | `all` | Task ID(s), comma-separated |
| `--runs` | `3` | Runs per task per backend |
| `--model` | `us.anthropic.claude-sonnet-4-20250514-v1:0` | Claude model ID |
| `--output` | `benchmarks/results/` | Output directory |
| `--include-live` | off | Include live-web tasks (hit real websites) |
| `--warmup` | `1` | Warmup runs to discard |

## Results

**Model:** `us.anthropic.claude-sonnet-4-20250514-v1:0` (AWS Bedrock) | **Date:** 2026-03-27

### Fixture Tasks — brow vs playwright-cli

10 tasks using a local fixture server for full reproducibility.

| Task | brow tokens | pwcli tokens | &Delta; | brow calls | pwcli calls | brow time | pwcli time |
|------|------------|-------------|---------|-----------|------------|----------|-----------|
| dynamic-content | 29,640 | 31,954 | **-7%** | 10 | 12 | 33s | 40s |
| ecommerce-search | 19,206 | 53,292 | **-64%** | 6 | 12 | 23s | 46s |
| error-recovery | 51,630 | 12,699 | +307% | 16 | 6 | 44s | 15s |
| form-fill | 33,028 | 16,002 | +106% | 11 | 7 | 41s | 34s |
| info-lookup | 16,612 | 5,948 | +179% | 6 | 3 | 17s | 9s |
| large-snapshot | 142,170 | 217,162 | **-35%** | 10 | 10 | 40s | 46s |
| login-auth | 69,995 | 72,009 | **-3%** | 20 | 20 | 96s | 61s |
| multi-page-nav | 23,543 | 8,830 | +167% | 8 | 4 | 20s | 14s |
| rapid-multi-step | 99,919 | 34,707 | +188% | 13 | 12 | 131s | 41s |
| search-extract | 10,716 | 6,691 | +60% | 4 | 3 | 16s | 9s |
| **Average** | **49,646** | **45,929** | **+8%** | **10.4** | **8.9** | **46s** | **32s** |

### Live Task — Vacuum Robot Research

Cross-reference vacuum robots on [alza.cz](https://www.alza.cz/roboticke-vysavace/18863907.htm) with [Valetudo supported models](https://valetudo.cloud/pages/general/supported-robots.html). Extract matching products with price, rating, and review count.

| Metric | brow | playwright-cli | MCP Playwright |
|--------|------|---------------|----------------|
| Total tokens | 371,050 | 238,290 | 1,424,281 |
| Tool calls | 15 | 4 | 10 |
| Errors | 1 | 1 | 9 |
| Wall clock | 73s | 56s | 393s |
| Got Valetudo data | Yes | No | No |
| Got alza.cz data | No (403) | No (ctx overflow) | No (MCP errors) |
| Usable output | **Partial** | None | None |

**brow** was the only backend to produce usable output -- it successfully scraped all Valetudo-supported robot models (Roborock, Dreame, Xiaomi, MOVA, Viomi, Eureka, etc.) before hitting alza.cz's bot protection (403). playwright-cli's unfiltered 92KB snapshot exceeded Bedrock's context window on the second turn. MCP Playwright's server crashed with JSON parse errors after the first navigation.

## Analysis

### brow wins on complex/large pages

- `ecommerce-search` **-64% tokens**: compact snapshot eliminates decorative DOM nodes
- `large-snapshot` **-35% tokens** (142K vs 217K): repetition dedup collapses 550 items to 3 + count
- `dynamic-content` **-7%**: fewer nodes from container pruning
- Live task: only backend to return any data

### playwright-cli wins on simple pages

- `info-lookup` 3x fewer tokens: no session setup overhead, combined open+navigate+snapshot
- `multi-page-nav`: 4 calls vs 8 -- brow needs explicit `session_new` + `navigate`
- Zero errors on all fixture tasks

### MCP Playwright issues

- SSE response parsing fragile (JSON decode errors under load)
- Highest token consumption (1.4M on live task)
- Server stability problems

## Optimizations Applied to brow

1. **JS tree pruning**: skip `script`, `style`, `svg`, hidden elements; collapse decorative containers
2. **Repetition dedup**: detect repeated sibling structures, show first 3, emit count
3. **Node count cap (300)**: prevent runaway snapshots
4. **Truncation hints**: response includes `hint: "Use search param to filter"` when capped
5. **Message history compression**: old tool results >500 chars get head/tail summarized
6. **Async tool execution**: `subprocess.run` &rarr; `asyncio.create_subprocess_exec` (fixed event loop blocking)
7. **Retry with backoff**: automatic handling of 429s and context overflow (400s)

## Task Suite

### Fixture Tasks (reproducible, local server)

| Task | Category | Description |
|------|----------|-------------|
| search-extract | extraction | Search page, extract top 5 results |
| form-fill | interaction | Fill form fields, submit, verify confirmation |
| multi-page-nav | navigation | Visit 3 pages, extract data from each |
| login-auth | auth | Login, perform action behind authentication |
| dynamic-content | extraction | Wait for JS-rendered content, extract data |
| ecommerce-search | search | Find product matching criteria in catalog |
| info-lookup | research | Find specific fact across wiki-style pages |
| large-snapshot | stress | Page with 550 elements, measures snapshot handling |
| error-recovery | resilience | Intermittent missing elements, measures retry |
| rapid-multi-step | throughput | 5-step wizard with form fills and navigation |

### Live Tasks (real websites, `--include-live`)

| Task | Description |
|------|-------------|
| vacuum-research | Cross-reference alza.cz vacuum robots with Valetudo supported models |

## Architecture

```
benchmarks/
  run.py              CLI entry point
  tasks/*.yaml        Task definitions (fixture + live)
  fixtures/           FastAPI app + static HTML pages
  harness/
    agent.py          LLM agent loop (Claude API + Bedrock)
    config.py         Model pricing, API keys, defaults
    runner.py         Task orchestration + randomization
    reporter.py       Markdown + JSON output
    judge.py          Success criteria evaluation
    metrics.py        Token/call/time tracking
    server.py         Fixture server lifecycle
    tools_brow.py     brow CLI tool definitions + async executor
    tools_playwright_cli.py  playwright-cli tool definitions
    tools_mcp.py      MCP Playwright HTTP client + tool definitions
    tools_common.py   submit_answer tool (shared)
  results/            Generated reports and raw JSON
```

## Design Spec

Full design document: [docs/superpowers/specs/2026-03-23-agent-benchmark-design.md](../docs/superpowers/specs/2026-03-23-agent-benchmark-design.md)
