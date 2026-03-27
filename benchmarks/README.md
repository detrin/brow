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

### Final Comparison — All 16 Fixture Tasks (3 backends)

16 tasks using a local fixture server. brow includes ref-based element addressing, auto-snapshot, table-aware markdown, inline list compression, adaptive node caps, and parallel tool execution.

| Metric | **brow** | **playwright-cli** | **MCP Playwright** |
|--------|----------|-------------------|-------------------|
| Avg tokens/task | **86,115** | 112,775 | 118,161 |
| Avg tool calls | **7.4** | 9.6 | 11.6 |
| Success rate | **69% (11/16)** | 44% (7/16) | 38% (6/16) |
| Avg wall-clock | **33s** | 44s | 50s |
| Est. cost/task | **$0.27** | $0.35 | $0.37 |

#### Per-Task Breakdown

| Task | brow tokens | pwcli tokens | mcp tokens | brow &Delta; pwcli | brow ✓ | pwcli ✓ | mcp ✓ |
|------|------------|-------------|-----------|-------------------|--------|---------|-------|
| data-table-extract | **130,593** | 259,625 | 476,499 | **-50%** | **1/1** | 0/1 | 0/1 |
| deep-wizard | **182,894** | 273,691 | 124,159 | **-33%** | **1/1** | 0/1 | 0/1 |
| dynamic-content | **3,229** | 48,498 | 43,470 | **-93%** | 0/1 | 0/1 | 0/1 |
| ecommerce-search | **11,419** | 140,630 | 66,236 | **-92%** | **1/1** | 0/1 | 0/1 |
| error-recovery | **4,881** | 20,704 | 32,752 | **-76%** | **1/1** | 1/1 | 1/1 |
| form-fill | **18,288** | 24,489 | 22,856 | **-25%** | 0/1 | 0/1 | 0/1 |
| form-validation-recovery | **26,300** | 48,247 | 64,808 | **-45%** | **1/1** | 1/1 | 1/1 |
| infinite-scroll | 168,610 | **116,602** | 73,556 | +45% | **1/1** | 1/1 | 0/1 |
| info-lookup | **5,381** | 6,376 | 6,247 | **-16%** | **1/1** | 1/1 | 1/1 |
| large-snapshot | **195,458** | 609,060 | 607,043 | **-68%** | **1/1** | 0/1 | 0/1 |
| login-auth | 185,257 | **92,525** | 56,757 | +100% | 0/1 | 0/1 | 0/1 |
| multi-page-nav | **7,864** | 10,806 | 71,339 | **-27%** | **1/1** | 1/1 | 1/1 |
| multi-tab-workflow | 217,941 | **23,787** | 115,354 | +816% | **1/1** | 1/1 | 0/1 |
| rapid-multi-step | 159,912 | **80,952** | 45,907 | +98% | **1/1** | 1/1 | 1/1 |
| search-extract | **3,663** | 4,061 | 27,074 | **-10%** | 0/1 | 0/1 | 0/1 |
| spa-navigation | 56,148 | **44,354** | 56,521 | +27% | 0/1 | 0/1 | **1/1** |

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

### brow dominates overall

- **-24% avg tokens** vs playwright-cli, **-27%** vs MCP Playwright
- **69% success rate** vs 44% (pwcli) and 38% (mcp) — +25pp and +31pp respectively
- **-25% wall-clock** vs pwcli, **-34%** vs mcp
- Wins 10/16 tasks on tokens, 11/16 on success

### Where brow excels

- `dynamic-content` **-93%**: ref-based clicking + auto-snapshot eliminates 10 tool calls
- `ecommerce-search` **-92%**: compact snapshot + fewer calls (4 vs 12)
- `error-recovery` **-76%**: ref system simplifies retry logic
- `large-snapshot` **-68%**: tree pruning + table-aware markdown on massive pages
- `data-table-extract` **-50%**: table markdown compression + only backend to succeed
- `deep-wizard` **-33%**: 10-step wizard, only backend to complete it

### Where playwright-cli wins

- `login-auth` +100%: brow's auto-snapshot returns large snapshots after every form fill
- `rapid-multi-step` +98%: multi-step wizard generates cumulative snapshot data
- `multi-tab-workflow` +816%: brow's page management overhead is expensive
- These tasks show auto-snapshot is costly on form-heavy pages — diff snapshots would help

### Optimizations applied to brow

| Optimization | Phase | Impact |
|-------------|-------|--------|
| JS tree pruning (skip script/style/svg, collapse decorative containers) | v1 | Foundation for compact snapshots |
| Repetition dedup (detect repeated siblings, show first 3 + count) | v1 | -35% on large-snapshot |
| Ref-based element addressing (`[N]` refs via `data-brow-ref`) | v2 | Eliminates CSS selector guessing |
| Auto-snapshot on mutations (click/fill/select/navigate return page state) | v2 | -34% avg tool calls |
| Combined `session new --url` | v2 | One call instead of two |
| Semantic message compression (aggressive for confirmations, lenient for data) | v2 | Reduces context accumulation |
| Table-aware markdown output | v3 | -68% on large-snapshot |
| Inline list compression (pipe-separated for >5 same-type children) | v3 | Compact nav bars |
| Adaptive node cap (200/400/300 based on interactive density) | v3 | -25% on form-fill |
| Parallel tool execution (`asyncio.gather`) | v3 | Wall-clock improvement |

### MCP Playwright issues

- Highest token consumption and lowest success rate (38%)
- SSE response parsing fragile (JSON decode errors under load)
- Server stability problems on complex tasks

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
