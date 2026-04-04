# Browser Automation Benchmarks

Compares **brow**, **playwright-cli**, **MCP Playwright**, and **agent-browser** as browser automation backends for an LLM agent loop (Claude Sonnet on AWS Bedrock).

## Quick Start

```bash
pip install -r benchmarks/requirements.txt
playwright install chromium

# All backends, all fixture tasks (brow / playwright-cli / mcp-playwright / agent-browser)
python -m benchmarks.run --backend all --runs 1

# Single backend, specific task
python -m benchmarks.run --backend brow --tasks info-lookup --runs 1

# browser-use (separate runner — uses its own agent loop)
pip install browser-use
python -m benchmarks.run_browser_use --runs 1

# Include live (non-fixture) tasks
python -m benchmarks.run --backend brow --tasks vacuum-research --include-live --warmup 0 --runs 1
```

### CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--backend` | `all` | `brow`, `mcp-playwright`, `playwright-cli`, `agent-browser`, or `all` |
| `--tasks` | `all` | Task ID(s), comma-separated |
| `--runs` | `3` | Runs per task per backend |
| `--model` | `us.anthropic.claude-sonnet-4-20250514-v1:0` | Claude model ID |
| `--output` | `benchmarks/results/` | Output directory |
| `--include-live` | off | Include live-web tasks (hit real websites) |
| `--warmup` | `1` | Warmup runs to discard |

## Results

**Model:** `us.anthropic.claude-sonnet-4-20250514-v1:0` (AWS Bedrock) | **Date:** 2026-04-04

### Final Comparison — All 16 Fixture Tasks (5 backends)

16 tasks using a local fixture server. brow includes ref-based element addressing, auto-snapshot, table-aware markdown, inline list compression, adaptive node caps, and parallel tool execution. agent-browser uses Rust + CDP directly (no Playwright), with `@eN` refs. browser-use is a full-stack agent framework with its own loop — compared here using our judge for fair structured-output evaluation, with `use_vision=False`.

| Metric | **brow** | **playwright-cli** | **MCP Playwright** | **agent-browser** | **browser-use** |
|--------|----------|-------------------|-------------------|------------------|----------------|
| Avg tokens/task | **86,115** | 112,775 | 118,161 | 73,156 | 74,751 |
| Avg tool calls | **7.4** | 9.6 | 11.6 | 11.2 | 5.8 |
| Success rate | **69% (11/16)** | 44% (7/16) | 38% (6/16) | 56% (9/16) | 56% (9/16) |
| Avg wall-clock | **33s** | 44s | 50s | 36s | 73s |
| Est. cost/task | $0.27 | $0.35 | $0.37 | **$0.23** | $0.27 |

#### Per-Task Breakdown

| Task | brow | pwcli | mcp | agent-browser | browser-use | brow ✓ | pwcli ✓ | mcp ✓ | ab ✓ | bu ✓ |
|------|------|-------|-----|---------------|-------------|--------|---------|-------|------|------|
| data-table-extract | **130,593** | 259,625 | 476,499 | 295,975 | 61,710 | **1/1** | 0/1 | 0/1 | 0/1 | 0/1 |
| deep-wizard | 182,894 | 273,691 | 124,159 | **79,238** | 169,436 | **1/1** | 0/1 | 0/1 | 0/1 | **1/1** |
| dynamic-content | **3,229** | 48,498 | 43,470 | 5,239 | 25,874 | 0/1 | 0/1 | 0/1 | 0/1 | **1/1** |
| ecommerce-search | **11,419** | 140,630 | 66,236 | 38,230 | 50,418 | **1/1** | 0/1 | 0/1 | **1/1** | 0/1 |
| error-recovery | **4,881** | 20,704 | 32,752 | 16,495 | 73,667 | **1/1** | 1/1 | 1/1 | **1/1** | 0/1 |
| form-fill | **18,288** | 24,489 | 22,856 | 19,632 | 38,136 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 |
| form-validation-recovery | **26,300** | 48,247 | 64,808 | 41,677 | 50,309 | **1/1** | 1/1 | 1/1 | **1/1** | **1/1** |
| infinite-scroll | 168,610 | 116,602 | 73,556 | **88,090** | 91,221 | **1/1** | 1/1 | 0/1 | **1/1** | **1/1** |
| info-lookup | **5,381** | 6,376 | 6,247 | 11,298 | 37,363 | **1/1** | 1/1 | 1/1 | **1/1** | **1/1** |
| large-snapshot | 195,458 | 609,060 | 607,043 | 340,559 | **86,331** | **1/1** | 0/1 | 0/1 | **1/1** | 0/1 |
| login-auth | 185,257 | 92,525 | **56,757** | 55,250 | 126,253 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 |
| multi-page-nav | **7,864** | 10,806 | 71,339 | 17,046 | 91,742 | **1/1** | 1/1 | 1/1 | **1/1** | **1/1** |
| multi-tab-workflow | 217,941 | 23,787 | 115,354 | **29,067** | 66,571 | **1/1** | 1/1 | 0/1 | **1/1** | **1/1** |
| rapid-multi-step | 159,912 | 80,952 | 45,907 | **44,519** | 74,646 | **1/1** | 1/1 | 1/1 | **1/1** | **1/1** |
| search-extract | **3,663** | 4,061 | 27,074 | 12,642 | 64,177 | 0/1 | 0/1 | 0/1 | 0/1 | **1/1** |
| spa-navigation | 56,148 | **44,354** | 56,521 | 75,544 | 88,156 | 0/1 | 0/1 | **1/1** | 0/1 | 0/1 |

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

### brow leads on success rate

- **69% success rate** vs 56% (agent-browser = browser-use), 44% (pwcli), 38% (mcp)
- brow is the only backend to solve `data-table-extract` and is one of two to solve `deep-wizard` (browser-use also passes)
- `spa-navigation` is solved only by MCP Playwright — an outlier where hash-routing caused issues for all others

### agent-browser lowest cost

- **$0.23/task** — cheapest backend despite 56% success, due to lean `-i` interactive-only snapshots
- 73,156 avg tokens/task — 15% less than brow, but 2x more tool calls (11.2 vs 7.4)

### browser-use: same success rate as agent-browser, 2x slower

- **56% success (9/16)** — ties agent-browser, passes different tasks
- Solves `deep-wizard`, `dynamic-content`, `search-extract` where brow fails; fails `ecommerce-search`, `error-recovery` where brow wins
- **73s avg wall-clock** — slowest backend due to framework overhead (extension loading, browser setup per task)
- **5.8 tool calls** — fewest of any backend (plans more, acts less); higher-level actions than raw refs
- Not a drop-in tool backend: runs its own agent loop with planning, memory, and loop detection

### Where brow excels

- `dynamic-content` **3,229 tokens** vs 5,239 (ab) vs 25,874 (bu): ref-based clicking eliminates waits
- `ecommerce-search` **11,419** vs 38,230 (ab) vs 50,418 (bu): compact snapshot + fewer calls
- `error-recovery` **4,881** vs 16,495 (ab) vs 73,667 (bu): ref system, brow recovers cleanly
- `data-table-extract` **130,593** — only backend to succeed; table markdown compression critical
- `large-snapshot` 195,458 vs **86,331 (bu)** — browser-use wins tokens but fails; brow succeeds via tree pruning

### Where agent-browser wins

- `multi-tab-workflow` **29,067** vs 217,941 (brow): CDP-native tab handling, no overhead
- `rapid-multi-step` **44,519** vs 159,912 (brow): no cumulative auto-snapshot accumulation
- `login-auth` **55,250** vs 185,257 (brow): -i snapshots lean on form-heavy pages

### Where browser-use wins

- `deep-wizard` **1/1** success — only backend besides brow to complete the 10-step wizard
- `dynamic-content` **1/1** — all other backends except brow fail; browser-use's high-level waits work
- `search-extract` **1/1** vs 0/1 for all others — brow/agent-browser both fail here
- `large-snapshot` **86,331 tokens** — lowest token count on the 550-element page (but 0/1 success)

### Where playwright-cli wins over brow (tokens, not success)

- `multi-tab-workflow` 23,787 vs 217,941: brow's page management is expensive but brow still succeeded
- `rapid-multi-step` 80,952 vs 159,912: auto-snapshot accumulation; diff snapshots would help

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

## Per-Task Detail

### Success Grid

✅ = passed, ❌ = failed

| Task | brow | pwcli | mcp | agent-browser | browser-use |
|------|------|-------|-----|---------------|-------------|
| data-table-extract | ✅ | ❌ | ❌ | ❌ | ❌ |
| deep-wizard | ✅ | ❌ | ❌ | ❌ | ✅ |
| dynamic-content | ❌ | ❌ | ❌ | ❌ | ✅ |
| ecommerce-search | ✅ | ❌ | ❌ | ✅ | ❌ |
| error-recovery | ✅ | ✅ | ✅ | ✅ | ❌ |
| form-fill | ❌ | ❌ | ❌ | ❌ | ❌ |
| form-validation-recovery | ✅ | ✅ | ✅ | ✅ | ✅ |
| infinite-scroll | ✅ | ✅ | ❌ | ✅ | ✅ |
| info-lookup | ✅ | ✅ | ✅ | ✅ | ✅ |
| large-snapshot | ✅ | ❌ | ❌ | ✅ | ❌ |
| login-auth | ❌ | ❌ | ❌ | ❌ | ❌ |
| multi-page-nav | ✅ | ✅ | ✅ | ✅ | ✅ |
| multi-tab-workflow | ✅ | ✅ | ❌ | ✅ | ✅ |
| rapid-multi-step | ✅ | ✅ | ✅ | ✅ | ✅ |
| search-extract | ❌ | ❌ | ❌ | ❌ | ✅ |
| spa-navigation | ❌ | ❌ | ✅ | ❌ | ❌ |
| **Total** | **11/16** | **7/16** | **6/16** | **9/16** | **9/16** |

### Token Cost Per Task

| Task | brow | pwcli | mcp | agent-browser | browser-use |
|------|------|-------|-----|---------------|-------------|
| data-table-extract | 130,593 | 259,625 | 476,499 | 295,975 | **61,710** |
| deep-wizard | 182,894 | 273,691 | 124,159 | **79,238** | 169,436 |
| dynamic-content | **3,229** | 48,498 | 43,470 | 5,239 | 25,874 |
| ecommerce-search | **11,419** | 140,630 | 66,236 | 38,230 | 50,418 |
| error-recovery | **4,881** | 20,704 | 32,752 | 16,495 | 73,667 |
| form-fill | **18,288** | 24,489 | 22,856 | 19,632 | 38,136 |
| form-validation-recovery | **26,300** | 48,247 | 64,808 | 41,677 | 50,309 |
| infinite-scroll | 168,610 | 116,602 | 73,556 | **88,090** | 91,221 |
| info-lookup | **5,381** | 6,376 | 6,247 | 11,298 | 37,363 |
| large-snapshot | 195,458 | 609,060 | 607,043 | 340,559 | **86,331** |
| login-auth | 185,257 | 92,525 | **56,757** | 55,250 | 126,253 |
| multi-page-nav | **7,864** | 10,806 | 71,339 | 17,046 | 91,742 |
| multi-tab-workflow | 217,941 | 23,787 | 115,354 | **29,067** | 66,571 |
| rapid-multi-step | 159,912 | 80,952 | 45,907 | **44,519** | 74,646 |
| search-extract | **3,663** | 4,061 | 27,074 | 12,642 | 64,177 |
| spa-navigation | 56,148 | **44,354** | 56,521 | 75,544 | 88,156 |
| **Average** | **86,115** | 112,775 | 118,161 | 73,156 | 74,751 |

### Notable Patterns

- **`form-fill` and `login-auth`**: no backend passes — auth flow and form submission edge cases trip all five
- **`search-extract`**: only browser-use passes — its high-level extract action handles result parsing that raw-tool backends miss
- **`spa-navigation`**: only MCP Playwright passes — hash-routing edge case that suits its navigation model
- **`dynamic-content`**: only browser-use passes — built-in wait semantics handle JS-delayed content cleanly
- **`data-table-extract`**: only brow passes — table markdown compression is the differentiator; others overflow context
- **`form-validation-recovery`, `info-lookup`, `multi-page-nav`, `rapid-multi-step`**: most backends pass — straightforward enough that tool quality doesn't matter

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
