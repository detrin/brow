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

### Fixture Tasks — brow v2 vs playwright-cli

10 tasks using a local fixture server for full reproducibility. brow v2 adds ref-based element addressing, auto-snapshot on mutations, and combined session+navigate.

| Task | brow tokens | pwcli tokens | &Delta; | brow calls | pwcli calls | brow time | pwcli time |
|------|------------|-------------|---------|-----------|------------|----------|-----------|
| dynamic-content | 3,245 | 42,983 | **-92%** | 2 | 12 | 8s | 42s |
| ecommerce-search | 18,554 | 137,294 | **-86%** | 5 | 12 | 16s | 43s |
| error-recovery | 4,871 | 16,295 | **-70%** | 3 | 6 | 13s | 21s |
| form-fill | 25,251 | 22,865 | +10% | 7 | 7 | 21s | 22s |
| info-lookup | 5,385 | 6,405 | **-16%** | 3 | 3 | 9s | 9s |
| large-snapshot | 225,821 | 607,963 | **-63%** | 10 | 8 | 39s | 118s |
| login-auth | 137,351 | 93,678 | +47% | 8 | 19 | 28s | 64s |
| multi-page-nav | 7,824 | 10,793 | **-28%** | 4 | 4 | 12s | 13s |
| rapid-multi-step | 114,508 | 62,173 | +84% | 12 | 12 | 35s | 42s |
| search-extract | 3,663 | 4,050 | **-10%** | 2 | 2 | 6s | 9s |
| **Average** | **54,647** | **100,450** | **-46%** | **5.6** | **8.5** | **19s** | **38s** |

Success rates: brow 60% (6/10), playwright-cli 50% (5/10).

### brow v3 — All 16 Fixture Tasks (Phase 2: Smart Snapshots)

brow v3 adds table-aware markdown output, inline list compression, and adaptive node caps. Run on all 16 tasks (10 original + 6 new harder tasks).

| Task | Tokens | Calls | Success | Time (s) |
|------|--------|-------|---------|----------|
| dynamic-content | 5,038 | 3 | 0/1 | 9s |
| ecommerce-search | 43,603 | 7 | 1/1 | 25s |
| error-recovery | 6,754 | 4 | 1/1 | 16s |
| form-fill | 18,290 | 6 | 0/1 | 15s |
| info-lookup | 5,353 | 3 | 1/1 | 29s |
| large-snapshot | 181,958 | 10 | 0/1 | 65s |
| login-auth | 135,157 | 8 | 0/1 | 26s |
| multi-page-nav | 7,838 | 4 | 1/1 | 9s |
| rapid-multi-step | 136,685 | 13 | 1/1 | 43s |
| search-extract | 3,662 | 2 | 0/1 | 6s |
| **deep-wizard** | 214,266 | 9 | 1/1 | 129s |
| **data-table-extract** | 177,739 | 15 | 0/1 | 66s |
| **spa-navigation** | 58,050 | 9 | 0/1 | 28s |
| **multi-tab-workflow** | 325,331 | 11 | 1/1 | 46s |
| **infinite-scroll** | 273,693 | 13 | 1/1 | 47s |
| **form-validation-recovery** | 26,485 | 10 | 1/1 | 28s |
| **Average** | **101,244** | **7.9** | **56% (9/16)** | **37s** |

v3 vs v2 on original 10 tasks: `large-snapshot` -19% (182K vs 226K), `form-fill` -28% (18K vs 25K). New hard tasks: 4/6 success — deep-wizard, multi-tab-workflow, infinite-scroll, and form-validation-recovery all passed.

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

### brow v2 dominates on token efficiency

- `dynamic-content` **-92%** (3K vs 43K): ref-based clicking + auto-snapshot eliminates 10 tool calls
- `ecommerce-search` **-86%** (19K vs 137K): compact snapshot + fewer calls (5 vs 12)
- `error-recovery` **-70%** (5K vs 16K): ref system simplifies retry logic
- `large-snapshot` **-63%** (226K vs 608K): tree pruning + dedup on massive pages
- `multi-page-nav` **-28%**: combined session+navigate removes setup overhead
- Average **-46% tokens**, **-34% tool calls**, **-50% wall clock**

### Phase 2 (v3) — smart snapshot impact

- `large-snapshot` **-19%** (182K vs 226K): table-aware markdown compresses tabular data
- `form-fill` **-28%** (18K vs 25K): adaptive node cap reduces non-interactive noise
- `login-auth` **-2%**: marginal improvement, still dominated by large auth page snapshots
- Single-run variance is high; structural improvements are best measured over multiple runs

### Where playwright-cli still wins

- `login-auth` +47%: brow's auto-snapshot returns large snapshots after each form fill
- `rapid-multi-step` +84%: multi-step wizard generates cumulative snapshot data

### Key v1 → v2 improvements

| Optimization | Impact |
|-------------|--------|
| Ref-based element addressing (`[N]` refs) | Eliminates CSS selector guessing, fewer retries |
| Auto-snapshot on mutations | Removes explicit snapshot calls (avg -34% tool calls) |
| Combined `session new --url` | One call instead of two for session + navigate |
| Semantic message compression | Aggressive for confirmations, lenient for data |
| Session ID auto-injection | Prevents KeyError failures |

### MCP Playwright issues

- SSE response parsing fragile (JSON decode errors under load)
- Highest token consumption (1.4M on live task)
- Server stability problems

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
| deep-wizard | interaction | 10-step registration wizard with varied input types |
| data-table-extract | extraction | Filter and extract from 100-row product table |
| spa-navigation | navigation | Hash-based SPA with 4 views, cross-view data |
| multi-tab-workflow | workflow | Product comparison across tabs with detail views |
| infinite-scroll | extraction | Scroll-loaded news feed, extract from 50 items |
| form-validation-recovery | resilience | Form with client-side validation error recovery |

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
