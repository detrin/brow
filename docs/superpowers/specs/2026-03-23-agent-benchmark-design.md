# Agent Benchmark: brow vs MCP Playwright

## Goal

Research-grade benchmark measuring agent performance when using brow CLI vs MCP Playwright for browser automation. Results serve three purposes: engineering feedback loop, marketing (README metrics), and academic credibility for AI researchers.

## Metrics (Priority Order)

1. **Token efficiency** - total input + output tokens per task
2. **Tool call count** - number of agent-to-tool round trips
3. **Task success rate** - binary pass/fail per task run
4. **Error recovery** - recoveries / errors encountered
5. **Wall-clock time** - end-to-end seconds per task

Derived: cost estimate (tokens x model pricing, configurable via `config.yaml`), avg response size (bytes per tool call).

### Token Counting

Tokens are captured from the Claude API `usage` field per conversation turn. Each API request/response cycle reports `input_tokens` and `output_tokens`. The harness sums these across all turns for the total.

Crucially, input tokens grow as conversation history accumulates. When a tool returns a large response (e.g., a 500-element accessibility tree), that entire response becomes part of the input on the next turn. This is the primary mechanism by which brow should outperform MCP Playwright -- smaller tool responses compound into fewer input tokens over multi-turn conversations.

`tool_call_log[].input_tokens` and `output_tokens` refer to the API usage for that specific conversation turn, not the tool response size. `response_bytes` captures the raw tool response size separately.

### Error Recovery Definition

An **error** is any tool call that returns a non-success status (HTTP error, selector not found, timeout, etc.). A **recovery** is when the agent subsequently completes the same logical action successfully or achieves the task goal despite the error. The harness tracks error-recovery pairs by matching failed tool calls with subsequent successful calls to the same tool or calls that achieve the intended effect.

## Architecture

```
benchmarks/
  tasks/           # YAML task definitions
  fixtures/        # Local HTML test server + static pages
  harness/
    runner.py      # Orchestrates runs (randomization, alternation)
    agent.py       # Claude API wrapper with tool call interception
    tools_brow.py  # brow tool definitions for Claude
    tools_mcp.py   # MCP Playwright tool definitions for Claude
    metrics.py     # RunResult dataclass + aggregation
    judge.py       # Evaluates success criteria against agent output
    reporter.py    # Generates markdown comparison tables + raw JSON
    server.py      # Local fixture server lifecycle
    config.py      # Model pricing, API keys (env vars), defaults
  results/         # Output: report.md, per-run JSON logs
  run.py           # CLI entry point
```

### Run Flow

1. `run.py` loads task YAML, selects backend (brow | mcp-playwright)
2. Fixture server starts automatically if task requires it
3. `agent.py` sends system prompt + task to Claude API with tool definitions
4. Claude makes tool calls -> harness executes via subprocess (brow) or MCP client
5. Each call logged: input_tokens, output_tokens, response_bytes, latency_ms, success/failure
6. Loop until agent calls `submit_answer` tool or max_steps/timeout hit
7. `judge.py` evaluates success criteria against the `submit_answer` payload
8. `reporter.py` generates markdown tables + raw JSON
9. Fixture server stops

### Key Decision

Agent talks to Claude API directly (not Claude Code). Gives full control over token counting and tool call interception. Tool definitions mirror what Claude Code would see.

### MCP Playwright Execution

The harness runs an actual MCP Playwright server as a subprocess and communicates via the MCP protocol (stdio transport). This ensures the comparison is fair -- both backends go through their real protocol stacks. `tools_mcp.py` defines Claude tool schemas that map 1:1 to MCP Playwright's tool definitions. When Claude calls a tool, the harness translates it to an MCP request, sends it to the server, and returns the response.

Lifecycle: the MCP Playwright server is started before the first task and stopped after the last. One server instance per benchmark run.

### System Prompt

The system prompt is identical for both backends except for tool-specific instructions. Structure:

```
You are a browser automation agent. Complete the given task using the provided tools.

[Tool instructions - backend specific]
For brow: brief description of brow CLI commands available as tools.
For MCP Playwright: brief description of MCP Playwright tools available.

[Output instructions - identical]
When you have completed the task, call the submit_answer tool with your structured result.
Do not explain your actions. Execute efficiently with minimal tool calls.

[Task description - from YAML]
{task.description}
```

The brow tool instructions include content from brow's SKILL.md. MCP Playwright instructions mirror the official MCP Playwright tool descriptions. Both are kept minimal to avoid biasing behavior.

### Done Signal: submit_answer Tool

Both backends share a `submit_answer` tool that the agent calls when finished. Schema:

```json
{
  "name": "submit_answer",
  "description": "Submit your final answer for the task",
  "parameters": {
    "answer": { "type": "object", "description": "Structured result matching task requirements" },
    "confidence": { "type": "string", "enum": ["high", "medium", "low"] }
  }
}
```

This cleanly separates the answer from tool calls and gives `judge.py` well-defined input. If the agent hits max_steps or timeout without calling `submit_answer`, the task is marked as failed.

## Task Definition Format

```yaml
id: google-search-extract
name: "Google Search and Extract Results"
category: practical
url: "https://www.google.com"
requires_fixture: false
description: "Search for 'best coffee shops NYC' and extract top 5 results with titles and URLs"
max_steps: 15
timeout_seconds: 120
success_criteria:
  - type: structured_output
    min_fields: ["title", "url"]
    min_results: 5
  - type: no_errors
tags: [search, extraction, single-page]
```

### Success Criteria Evaluation

`judge.py` receives the `submit_answer` payload and the final browser state (current URL, page title). Each criteria type:

- **structured_output** - validates the answer object contains required fields (`min_fields`) and minimum number of entries (`min_results`). Can optionally check field types.
- **element_visible** - queries the browser (session still open) for a CSS/text selector. Pass if element found. Session is kept alive until judge completes.
- **url_match** - regex match against the browser's current page URL.
- **no_errors** - pass if `errors` list in RunResult is empty.
- **custom** - Python function path (e.g., `tasks.validators.check_login`). Receives `(answer: dict, browser_state: dict) -> bool`. Used for complex multi-condition validation.

All criteria for a task must pass for the task to be marked successful.

## Task Suite (10 tasks)

### Core reproducible tasks (local fixtures)

All core tasks use the local fixture server for full reproducibility.

1. **Search + extract** - local search page, extract top 5 results as structured data
2. **Form fill** - navigate to test form, fill fields, submit, verify confirmation
3. **Multi-page navigation** - visit 3 pages, extract specific data from each
4. **Login + authenticated action** - login to test site, perform action behind auth (showcases persistent profiles)
5. **Dynamic content extraction** - wait for JS-rendered content, extract structured data
6. **E-commerce search** (WebArena-inspired) - local product catalog, find product matching criteria
7. **Information lookup** (WebArena-inspired) - local wiki-style pages, find specific fact across pages
8. **Large page snapshot** - page with 500+ elements, measures verbose output handling
9. **Error recovery** - page with intermittent missing elements (server-side randomization), measures retry behavior
10. **Rapid multi-step** - 10+ sequential interactions to test interaction overhead

### Optional live-web tasks (not part of core suite)

- **Google search** - real Google, subject to DOM changes and CAPTCHAs
- **Real e-commerce** - real shopping site, subject to availability

Live-web tasks are excluded from default runs and reported separately.

## Test Fixtures

Local fixture server built with FastAPI (already a brow dependency). Serves both static HTML and dynamic endpoints.

**Static pages:** search results, product catalog, wiki pages, large DOM page, multi-page site. Served from `benchmarks/fixtures/static/`.

**Dynamic endpoints:**
- `/form` - accepts POST, returns confirmation page
- `/login` + `/dashboard` - session-based auth (cookie)
- `/dynamic` - page that renders content via JS after 2s delay
- `/flaky` - returns elements randomly (50% chance missing) for error recovery testing

**Lifecycle:** `server.py` starts the fixture server on a random available port before tasks that need it (`requires_fixture: true`). URL is injected into task definitions. Server stops after benchmark completes.

## Metrics Model

```python
@dataclass
class RunResult:
    task_id: str
    backend: str              # "brow" | "mcp-playwright"
    model: str                # e.g. "claude-sonnet-4-20250514"
    success: bool
    total_input_tokens: int
    total_output_tokens: int
    tool_calls: int
    tool_call_log: list       # per-call: name, input_tokens, output_tokens, latency_ms, response_bytes
    wall_clock_ms: int
    errors: list
    error_recoveries: int
    final_output: dict
    run_id: str
    timestamp: str
    brow_version: str         # git commit hash or package version
    conversation_turns: int   # total API round trips
```

Each task runs N times (default 3) per backend. Reporter shows mean +/- stddev.

### Run Ordering

Tasks are randomized across runs. Backends alternate (brow run 1, mcp run 1, brow run 2, mcp run 2, ...) to distribute temporal confounds (API latency, rate limiting). One warm-up run (discarded) per backend before measurement begins.

## CLI Interface

```
python run.py --backend brow --tasks all --runs 3 --model claude-sonnet-4-20250514
python run.py --backend mcp-playwright --tasks search-extract --runs 1
python run.py --backend all --tasks all --runs 5 --output results/2026-03-23/
```

Arguments:
- `--backend`: brow | mcp-playwright | all (default: all)
- `--tasks`: task ID, comma-separated IDs, or "all" (default: all)
- `--runs`: number of runs per task per backend (default: 3)
- `--model`: Claude model ID (default: claude-sonnet-4-20250514)
- `--output`: output directory (default: benchmarks/results/)
- `--include-live`: include optional live-web tasks (default: false)
- `--warmup`: number of warmup runs to discard (default: 1)

API key via `ANTHROPIC_API_KEY` environment variable.

## Reporter Output

Generates `benchmarks/results/report.md`:

```markdown
## Benchmark Results (Claude Sonnet 4, 3 runs per task)

### Summary
| Metric | brow | MCP Playwright | Delta |
|--------|------|----------------|-------|
| Avg tokens/task | 4,200 | 11,800 | -64% |
| Avg tool calls/task | 6.2 | 14.1 | -56% |
| Success rate | 93% | 87% | +6pp |
| Avg wall-clock (s) | 18.3 | 31.7 | -42% |
| Est. cost/task | $0.008 | $0.022 | -64% |

### Per-Task Breakdown
| Task | Backend | Tokens | Calls | Success | Time (s) |
|------|---------|--------|-------|---------|----------|
| search-extract | brow | 3,100+/-200 | 5+/-1 | 3/3 | 14+/-2 |
| search-extract | mcp-pw | 9,400+/-800 | 12+/-2 | 3/3 | 28+/-4 |
```

Also generates raw JSON per run for programmatic analysis.

## Post-Benchmark Roadmap: Agent-Friendliness Improvements

These are future changes to brow itself, informed by benchmark results. Not part of the benchmark implementation.

### 1. Composite commands
`brow navigate -s 1 "url" --snapshot` returns snapshot in same call. Cuts tool calls ~30%.

### 2. Action feedback
`brow click` returns page state after action (URL changed? new elements?). Eliminates follow-up snapshot calls.

### 3. Structured output mode
`--format json` on snapshot, url, logs. Agents parse JSON instead of text.

### 4. Token-aware truncation
`--max-tokens 2000` on snapshot. Intelligently truncates large accessibility trees.

### 5. Error hints
When selector fails, suggest corrections via fuzzy matching the accessibility tree.

### 6. Batch operations
`brow batch -s 1 '["click text=Next", "wait .results", "snapshot"]'` - multiple commands in one tool call.

## Scope

- Claude-only agent for v1 (pluggable harness design for future model support)
- Lives in `benchmarks/` directory inside brow repo
- Local test fixtures for reproducibility
- No external service dependencies for core tasks
- `model` field in RunResult for future multi-model support

## Non-Goals

- Multi-model support in v1
- CI integration (manual runs initially)
- Visual regression testing
- Performance optimization of brow itself (that comes after benchmarking identifies bottlenecks)
