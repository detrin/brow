# Browser Automation Benchmarks

Compares **brow**, **playwright-cli**, **MCP Playwright**, **agent-browser**, and **browser-use** as browser automation backends for an LLM agent loop (Claude Sonnet on AWS Bedrock).

22 tasks total: 19 fixture tasks (local server, fully reproducible) and 3 live tasks (real websites, `--include-live`).

## Quick Start

```bash
pip install -r benchmarks/requirements.txt
patchright install chromium

# All backends, all fixture tasks
python -m benchmarks.run --backend all --runs 1

# Single backend, specific task
python -m benchmarks.run --backend brow --tasks info-lookup --runs 1

# browser-use (separate runner — uses its own agent loop)
pip install browser-use
python -m benchmarks.run_browser_use --runs 1

# Include live tasks (hit real websites)
python -m benchmarks.run --backend all --include-live --runs 1
```

### CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--backend` | `all` | `brow`, `mcp-playwright`, `playwright-cli`, `agent-browser`, or `all` |
| `--tasks` | `all` | Task ID(s), comma-separated |
| `--runs` | `3` | Runs per task per backend |
| `--model` | `us.anthropic.claude-sonnet-4-20250514-v1:0` | Claude model ID |
| `--output` | `benchmarks/results/` | Output directory |
| `--include-live` | off | Include live-web tasks |
| `--warmup` | `1` | Warmup runs to discard |

## Results

**Model:** `us.anthropic.claude-sonnet-4-20250514-v1:0` (AWS Bedrock) | **Date:** 2026-04-04

brow includes ref-based element addressing, auto-snapshot, table-aware markdown, inline list compression, adaptive node caps, and parallel tool execution. agent-browser uses Rust + CDP directly, with `@eN` refs. browser-use is a full-stack agent framework compared using our judge with `use_vision=False`.

### Summary — All 22 Tasks

| Metric | **brow** | **agent-browser** | **browser-use** | **playwright-cli** | **MCP Playwright** |
|--------|----------|-------------------|-----------------|--------------------|--------------------|
| Success rate (16 fixture) | **88% (14/16)** | 63% (10/16) | 63% (10/16) | 50% (8/16) | 44% (7/16) |
| Success rate (6 new) | 67% (4/6) | 67% (4/6) | 67% (4/6) | 67% (4/6) | 17% (1/6) |
| **Success rate (22 total)** | **82% (18/22)** | 64% (14/22) | 64% (14/22) | 55% (12/22) | 36% (8/22) |
| Avg tokens/task (16 fixture) | **68,255** | 73,156 | 74,751 | 112,775 | 118,161 |
| Avg tokens/task (6 new) | 139,949 | **57,731** | 95,929 | 51,262 | 170,096 |
| **Avg tokens/task (22 total)** | 87,808 | **68,949** | 80,527 | 95,998 | 132,325 |
| Avg tool calls | 9.6 | 11.2 | **5.8** | 9.6 | 11.6 |
| Avg wall-clock (fixture) | 41s | **36s** | 73s | 44s | 50s |
| Est. cost/task (16 fixture) | **$0.22** | $0.23 | $0.27 | $0.35 | $0.37 |
| Est. cost/task (6 new) | $0.45 | $0.19 | $0.36 | **$0.16** | $0.53 |

## Per-Task Results

### Success Grid

✅ = passed, ❌ = failed

| Task | brow | pwcli | mcp | agent-browser | browser-use |
|------|------|-------|-----|---------------|-------------|
| **— original 16 fixture tasks —** | | | | | |
| data-table-extract | ✅ | ❌ | ❌ | ❌ | ❌ |
| deep-wizard | ❌ | ❌ | ❌ | ❌ | ✅ |
| dynamic-content | ✅ | ❌ | ❌ | ❌ | ✅ |
| ecommerce-search | ✅ | ❌ | ❌ | ✅ | ❌ |
| error-recovery | ✅ | ✅ | ✅ | ✅ | ❌ |
| form-fill | ✅ | ✅ | ✅ | ✅ | ✅ |
| form-validation-recovery | ✅ | ✅ | ✅ | ✅ | ✅ |
| infinite-scroll | ❌ | ✅ | ❌ | ✅ | ✅ |
| info-lookup | ✅ | ✅ | ✅ | ✅ | ✅ |
| large-snapshot | ✅ | ❌ | ❌ | ✅ | ❌ |
| login-auth | ✅ | ❌ | ❌ | ❌ | ❌ |
| multi-page-nav | ✅ | ✅ | ✅ | ✅ | ✅ |
| multi-tab-workflow | ✅ | ✅ | ❌ | ✅ | ✅ |
| rapid-multi-step | ✅ | ✅ | ✅ | ✅ | ✅ |
| search-extract | ✅ | ❌ | ❌ | ❌ | ✅ |
| spa-navigation | ✅ | ❌ | ✅ | ❌ | ❌ |
| **— 3 new fixture tasks —** | | | | | |
| paginated-news | ✅ | ✅ | ❌ | ✅ | ✅ |
| price-comparison | ✅ | ✅ | ❌ | ✅ | ✅ |
| tech-stack-graph | ✅ | ✅ | ❌ | ✅ | ✅ |
| **— 3 new live tasks —** | | | | | |
| github-trending-python | ✅ | ✅ | ✅ | ✅ | ✅ |
| hacker-news-ask | ✅ | ❌ | ❌ | ✅ | ❌ |
| npm-http-clients | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Total** | **18/22** | **12/22** | **8/22** | **14/22** | **14/22** |

### Token Cost Per Task

⚠️ marks outliers explained in the Analysis section below.

| Task | brow | pwcli | mcp | agent-browser | browser-use |
|------|------|-------|-----|---------------|-------------|
| **— original 16 fixture tasks —** | | | | | |
| data-table-extract | **63,962** | 259,625 | 476,499 | 295,975 | 61,710 |
| deep-wizard | 293,672 | 273,691 | 124,159 | **79,238** | 169,436 |
| dynamic-content | 34,925 | 48,498 | 43,470 | **5,239** | 25,874 |
| ecommerce-search | 46,006 | 140,630 | 66,236 | **38,230** | 50,418 |
| error-recovery | 60,504 | **20,704** | 32,752 | 16,495 | 73,667 |
| form-fill | 31,067 | **24,489** | 22,856 | 19,632 | 38,136 |
| form-validation-recovery | **34,493** | 48,247 | 64,808 | 41,677 | 50,309 |
| infinite-scroll | 120,127 | 116,602 | 73,556 | **88,090** | 91,221 |
| info-lookup | **7,816** | 6,376 | 6,247 | 11,298 | 37,363 |
| large-snapshot | **80,295** | 609,060 | 607,043 | 340,559 | 86,331 |
| login-auth | **54,919** | 92,525 | 56,757 | 55,250 | 126,253 |
| multi-page-nav | **11,140** | 10,806 | 71,339 | 17,046 | 91,742 |
| multi-tab-workflow | 44,570 | **23,787** | 115,354 | 29,067 | 66,571 |
| rapid-multi-step | 124,400 | 80,952 | **45,907** | 44,519 | 74,646 |
| search-extract | **9,179** | 4,061 | 27,074 | 12,642 | 64,177 |
| spa-navigation | 74,999 | **44,354** | 56,521 | 75,544 | 88,156 |
| **Avg (16 fixture)** | **68,255** | 112,775 | 118,161 | 73,156 | 74,751 |
| **— 3 new fixture tasks —** | | | | | |
| paginated-news | **16,356** | 19,427 | 145,694 | 58,162 | 100,587 |
| price-comparison | 43,774 | **8,913** | 86,215 | 12,994 | 69,884 |
| tech-stack-graph | 173,318 | **87,169** | 98,161 | 126,828 | 154,209 |
| **— 3 new live tasks —** | | | | | |
| github-trending-python | 383,096 ⚠️ | **11,130** | 12,813 | 9,902 | 14,819 |
| hacker-news-ask | **54,866** | 1,580 ⚠️ | 626,068 ⚠️ | 76,884 | 36,844 |
| npm-http-clients | 168,282 | 179,350 | **51,625** | 61,618 | 199,229 |
| **Avg (6 new)** | 139,949 | **51,262** | 170,096 | 57,731 | 95,929 |
| **Avg (22 total)** | 87,808 | 95,998 | 132,325 | **68,949** | 80,527 |

## Analysis

### Overall picture

brow leads on success rate across both suites: **88% on the 16-task fixture suite** and **82% across all 22 tasks**. agent-browser and browser-use tie at 64%. playwright-cli is competitive on the new tasks (67%) but weak on fixture tasks (50%). MCP Playwright is unreliable on any multi-page task — 36% overall, dropping to 17% on the new suite.

On token efficiency the rankings flip between suites. brow leads on fixtures (68K avg) but agent-browser leads across all 22 tasks (69K avg). brow's 22-task average is inflated by a single live task where the agent didn't use snapshot filtering (see outliers below).

### Where brow leads

- **`data-table-extract`** — only backend to succeed; table markdown compression prevents context overflow that fails others (pwcli: 259K, mcp: 476K)
- **`login-auth`** — only backend to succeed; `brow_goto` preserves session cookies across navigations
- **`large-snapshot`** — 80K vs 609K (pwcli), 607K (mcp): tree pruning dominates on 550-element pages
- **`search-extract`** — passes via `brow_eval`; other tool backends fail
- **`dynamic-content`** — `brow_wait` provides explicit selector-based waiting; raw backends don't recover from hidden content
- **`paginated-news`** — most token-efficient at 16K (vs 58K agent-browser, 100K browser-use)

### Where agent-browser leads

- Fastest wall-clock: **36s avg** — no per-session startup overhead
- Most token-efficient across all 22 tasks: **69K avg total**
- `multi-tab-workflow` **29K** vs 44K (brow): CDP-native tab handling
- `rapid-multi-step` **44K** vs 124K (brow): no snapshot accumulation between steps

### Where browser-use leads

- **`deep-wizard`** — only backend to reliably complete the 10-step wizard; brow fails on timeout
- **`infinite-scroll`** — built-in scroll semantics handle the feed cleanly

### Where playwright-cli leads

- **`npm-http-clients`** — only backend to pass; somehow navigates Cloudflare on npmjs.com where others are blocked
- Token-efficient on simple tasks: `price-comparison` at 8.9K, `multi-page-nav` at 10.8K
- Cheapest on the new task suite at **$0.16/task avg**

### Token outliers

**brow on `github-trending-python`: 383K tokens** — every other backend used 10–15K. The agent re-read the full GitHub page repeatedly instead of using `brow_snapshot --search`. Tool capability was fine; agent behavior was inefficient. Without this outlier, brow's new-tasks average drops from 140K to ~91K.

**playwright-cli on `hacker-news-ask`: 1,580 tokens** — barely started; session likely stalled during initialization (101s wall clock, empty output). Suppresses the pwcli average significantly — its 51K new-tasks avg is not representative of real efficiency on this task.

**MCP on `hacker-news-ask`: 626K tokens** — entered a JSON parse error loop (7 errors), spending 626K tokens going nowhere. Neither succeeds nor bails fast.

### MCP Playwright issues

MCP fails all 3 new fixture tasks and 2 of 3 new live tasks, all due to JSON parse errors from its SSE transport. Its 36% overall success rate is the lowest of the five backends. Reliable only on simple, single-page tasks.

### Optimizations applied to brow

| Optimization | Impact |
|-------------|--------|
| JS tree pruning (skip script/style/svg, collapse decorative containers) | Foundation for compact snapshots |
| Repetition dedup (detect repeated siblings, show first 3 + count) | −35% on large-snapshot |
| Ref-based element addressing (`[N]` refs via `data-brow-ref`) | Eliminates CSS selector guessing |
| Auto-snapshot on mutations (click/fill/select/navigate return page state) | −34% avg tool calls |
| Semantic message compression (aggressive for confirmations, lenient for data) | Reduces context accumulation |
| Table-aware markdown output | −68% on large-snapshot |
| Inline list compression (pipe-separated for >5 same-type children) | Compact nav bars |
| Adaptive node cap (200/400/300 based on interactive density) | −25% on form-fill |
| Parallel tool execution (`asyncio.gather`) | Wall-clock improvement |
| `brow_goto` / `brow_wait` / `brow_eval` tools added to agent harness | Enables session-preserving nav, dynamic waits, JS extraction |

## Task Suite

### Fixture Tasks (reproducible, local server)

| Task | Category | Description |
|------|----------|-------------|
| data-table-extract | extraction | Filter and extract from 100-row product table |
| deep-wizard | interaction | 10-step registration wizard with varied input types |
| dynamic-content | extraction | Wait for JS-rendered content, extract data |
| ecommerce-search | search | Find product matching criteria in catalog |
| error-recovery | resilience | Intermittent missing elements, measures retry |
| form-fill | interaction | Fill form fields, submit, verify confirmation |
| form-validation-recovery | resilience | Form with client-side validation error recovery |
| infinite-scroll | extraction | Scroll-loaded news feed, extract from 50 items |
| info-lookup | research | Find specific fact across wiki-style pages |
| large-snapshot | stress | Page with 550 elements, measures snapshot handling |
| login-auth | auth | Login, perform action behind authentication |
| multi-page-nav | navigation | Visit 3 pages, extract data from each |
| multi-tab-workflow | workflow | Product comparison across tabs with detail views |
| rapid-multi-step | throughput | 5-step wizard with form fills and navigation |
| search-extract | extraction | Search page, extract top 5 results |
| spa-navigation | navigation | Hash-based SPA with 4 views, cross-view data |
| paginated-news | extraction | Filter articles by author+category across 3 pages |
| price-comparison | extraction | Find shared products across 2 stores, compare prices |
| tech-stack-graph | extraction | Follow dependency links, filter by version, extract descriptions |

### Live Tasks (real websites, `--include-live`)

| Task | Description |
|------|-------------|
| github-trending-python | Top 5 trending Python repos from github.com/trending/python |
| hacker-news-ask | All "Ask HN" posts on the HN front page with points and comments |
| npm-http-clients | Top 3 HTTP client packages on npmjs.com with download counts |
| vacuum-research | Cross-reference alza.cz vacuum robots with Valetudo supported models |

### Live Task Spotlight — Vacuum Robot Research

Cross-reference vacuum robots on [alza.cz](https://www.alza.cz/roboticke-vysavace/18863907.htm) with [Valetudo supported models](https://valetudo.cloud/pages/general/supported-robots.html).

| Metric | brow | playwright-cli | MCP Playwright |
|--------|------|---------------|----------------|
| Total tokens | 371,050 | 238,290 | 1,424,281 |
| Tool calls | 15 | 4 | 10 |
| Errors | 1 | 1 | 9 |
| Wall clock | 73s | 56s | 393s |
| Got Valetudo data | Yes | No | No |
| Got alza.cz data | No (403) | No (ctx overflow) | No (MCP errors) |
| Usable output | **Partial** | None | None |

brow was the only backend to produce usable output — scraped all Valetudo-supported models before hitting alza.cz's bot protection (403). playwright-cli's unfiltered 92KB snapshot exceeded Bedrock's context window on the second turn. MCP crashed with JSON parse errors after the first navigation.

## Architecture

```
benchmarks/
  run.py                  CLI entry point (brow / playwright-cli / mcp-playwright / agent-browser)
  run_browser_use.py      Separate runner for browser-use (own agent loop)
  tasks/*.yaml            Task definitions (fixture + live)
  fixtures/               FastAPI app + static HTML pages
  harness/
    agent.py              LLM agent loop (Claude API + Bedrock)
    config.py             Model pricing, API keys, defaults
    runner.py             Task orchestration + randomization
    reporter.py           Markdown + JSON output
    judge.py              Success criteria evaluation
    metrics.py            Token/call/time tracking
    server.py             Fixture server lifecycle
    tools_brow.py         brow CLI tool definitions + async executor
    tools_playwright_cli.py  playwright-cli tool definitions
    tools_mcp.py          MCP Playwright HTTP client + tool definitions
    tools_common.py       submit_answer tool (shared)
    tools_agent_browser.py  agent-browser CLI tool definitions + async executor
  results/                Generated reports and raw JSON
```

## Design Spec

Full design document: [docs/superpowers/specs/2026-03-23-agent-benchmark-design.md](../docs/superpowers/specs/2026-03-23-agent-benchmark-design.md)
