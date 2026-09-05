# brow — browser automation for AI agents

[![CI](https://github.com/detrin/brow/actions/workflows/test.yml/badge.svg)](https://github.com/detrin/brow/actions/workflows/test.yml)
[![PyPI](https://img.shields.io/pypi/v/brow-cli)](https://pypi.org/project/brow-cli/)
[![Python](https://img.shields.io/pypi/pyversions/brow-cli)](https://pypi.org/project/brow-cli/)
[![License: ELv2](https://img.shields.io/badge/license-Elastic%202.0-blue.svg)](LICENSE)

**Your browser, your logins, your machine.** brow gives an agent a real Chromium that stays signed
into your accounts and doesn't look automated — so it can do errands on the sites you actually use,
not just the ones that allow bots.

Two numbers behind that: brow scores **16/17** on [detectable automation
signals](#does-it-look-automated) against agent-browser's 13 and plain patchright's 8, and it is the
only runner tested that gets through both Alza and Google search. It also leads on task success:
**82% at ~$0.22/task**, ahead of browser-use, playwright-mcp and agent-browser across
[22 benchmark tasks](#benchmarks).

Nothing runs in a datacentre. There is no cloud browser to send your session cookies to, which is
the part competitors built on remote CDP cannot copy.

![brow demo](https://github.com/user-attachments/assets/27c6114c-451b-4e64-b66d-2268248be79b)

## Install

**Homebrew:**
```bash
brew tap detrin/tap
brew install brow
```

**pip:**
```bash
pip install brow-cli
```

Then install Chromium once (either method above):
```bash
brow setup            # ~150MB, one-time
```

Update patchright and its matching Chromium build later with:
```bash
brow setup --upgrade
```

**Agent skill:**
```bash
# For most agents (Cline, Cursor, Amp, Gemini CLI, etc.)
npx -y skills add detrin/brow

# For OpenCode (manual install)
git clone https://github.com/detrin/brow.git
ln -s "$(pwd)/brow/skills/brow" ~/.opencode/skills/brow   # OpenCode
```

## Quick start

Sign in once, by hand, in a window you can see:

```bash
brow login https://accounts.google.com
# ... sign in in the window that opens, then leave it or close it
```

After that, drop the ceremony. Commands with no `-s` use your `personal` profile, reusing the open
session or starting one:

```bash
brow navigate "https://www.google.com/maps/search/bars+near+Times+Square"
brow snapshot
brow click "text=Directions"
brow url
```

That's the everyday shape: no session ids, no `session new --reclaim`, no cleanup. Pass `-s <id>`
only when you deliberately want a second, separate browser. Set `BROW_PROFILE=work` to keep a
different identity side by side.

Profiles accumulate; `brow profile prune` reports what's stale and deletes it with `--yes`
(never your default profile, never one with a live session).

## Example: Find Bars Near Times Square with Google Maps

A real use case: use your Google account to search Maps in a city you've never visited, and extract structured results.

### Step 1: Log into Google (once)

```bash
brow login https://accounts.google.com
# Sign in manually in the browser window...
```

Your login is saved in `~/.brow/profiles/personal/` -you won't need to sign in again.

### Step 2: Ask Claude Code to search

Paste this into Claude Code:

> Open a brow session with my personal profile, go to Google Maps, and search for
> bars near Times Square in New York. Return the names, Google Maps URLs, ratings,
> and number of reviews in a markdown table.

Claude Code runs:

```bash
brow navigate "https://www.google.com/maps/search/bars+near+Times+Square+New+York"
brow screenshot
brow eval "
results = await page.evaluate('''() => {
    const items = document.querySelectorAll('div.Nv2PK');
    return Array.from(items).slice(0, 8).map(el => {
        const name = el.querySelector('.fontHeadlineSmall, .qBF1Pd');
        const rating = el.querySelector('.MW4etd');
        const reviews = el.querySelector('.UY7F9');
        const link = el.querySelector('a[href*=\"/maps/place\"]');
        return {
            name: name?.innerText || '',
            rating: rating?.innerText || '',
            reviews: reviews?.innerText.replace(/[()]/g, '') || '',
            url: link?.href || ''
        };
    });
}''')
import json
result = json.dumps(results, indent=2)
"
```

### Result

![Google Maps search results for bars near Times Square](docs/example-maps-search.png)

| Bar | Rating | Reviews | Link |
|-----|--------|---------|------|
| The Riff Raff Club | 4.4 | 60 | [Maps](https://www.google.com/maps/place/The+Riff+Raff+Club/) |
| Ascent Lounge | 4.4 | 646 | [Maps](https://www.google.com/maps/place/Ascent+Lounge/) |
| Jimmy's Corner | 4.6 | 2,195 | [Maps](https://www.google.com/maps/place/Jimmy's+Corner/) |
| O'Donoghue's Times Square | 4.4 | 2,633 | [Maps](https://www.google.com/maps/place/O'Donoghue's+Times+Square/) |
| The Dickens | 4.8 | 2,128 | [Maps](https://www.google.com/maps/place/The+Dickens/) |
| The Woo Woo | 4.8 | 1,871 | [Maps](https://www.google.com/maps/place/The+Woo+Woo/) |

Because the profile persists your login, you get personalized results -no cookie banners, no sign-in walls, just data.

## Does it look automated?

Measured, not asserted. `python -m benchmarks.stealth --sites` runs one JS probe against 17 signals
a detector can read for free, then visits four live sites:

| | **brow** | agent-browser | patchright (default) |
|---|---|---|---|
| Fingerprint signals passed | **16/17** | 13/17 | 8/17 |
| `navigator.webdriver` hidden | **yes** | no | yes |
| Real GPU, plugins, PDF viewer | **yes** | yes | no |
| `Headless` absent from UA + client hints | **yes** | no | no |
| Through Alza (Cloudflare) | **yes** | no | no |
| Through Google search | **yes** | no | no |

The gap over plain patchright is mostly one thing: `headless=True` alone runs
`chrome-headless-shell`, which has no GPU, no plugins, no PDF viewer and no `window.chrome` — six
signals from one cause. brow uses Chrome's new headless mode instead and sanitises the UA string to
match its own client hints. That took plain patchright from 8/17 to 16/17 and turned Alza and Google
from `BLOCKED` into `through`.

brow still fails one check (`chrome.runtime`) — so does every runner measured. Gaps are listed
rather than hidden in [benchmarks/stealth/README.md](benchmarks/stealth/README.md), along with the
raw probe output. Re-run it after every `patchright` bump; that's what it's for.

## Benchmarks

22 tasks total (16 fixture + 6 new), Claude Sonnet via AWS Bedrock. Compared against playwright-cli, MCP Playwright, agent-browser (Rust/CDP), and browser-use (full-stack agent framework).

| Metric | **brow** | agent-browser | browser-use | playwright-cli | MCP Playwright |
|--------|----------|---------------|-------------|----------------|----------------|
| Success rate (16 fixture) | **88% (14/16)** | 63% (10/16) | 63% (10/16) | 50% (8/16) | 44% (7/16) |
| Success rate (22 total) | **82% (18/22)** | 64% (14/22) | 64% (14/22) | 55% (12/22) | 36% (8/22) |
| Avg tokens/task (16 fixture) | **68K** | 73K | 75K | 113K | 118K |
| Avg tokens/task (22 total) | 88K | **69K** | 81K | 96K | 132K |
| Avg tool calls | 9.6 | 11.2 | **5.8** | 9.6 | 11.6 |
| Avg wall-clock (fixture) | 41s | **36s** | 73s | 44s | 50s |
| Est. cost/task | **$0.22** | $0.23 | $0.27 | $0.35 | $0.37 |

brow leads on success rate across both suites. On token efficiency, brow leads the 16-task fixture suite (68K avg) but agent-browser is most efficient across all 22 tasks (69K avg) — brow's average is inflated by one live task (github-trending-python: 383K tokens, agent didn't use snapshot filtering). browser-use runs its own agent loop — included for completeness.

Per-task success grid, token breakdown, and analysis: [benchmarks/README.md](benchmarks/README.md)

## Commands

### Daemon

```bash
brow daemon start [--port 19987]
brow daemon stop
brow daemon status
```

Every command below takes an optional `-s <id>`. Leave it out and brow uses your default profile,
reusing the open session or starting one. Pass it only for a second, separate browser.

### Sessions

```bash
brow login [url] [--profile <name>]   # visible window, sign in by hand
brow session new [--profile <name>] [--headed] [--reclaim]
brow session list
brow session delete <id>
brow session cleanup
```

### Navigation

```bash
brow navigate <url> [--wait load|domcontentloaded|networkidle]
brow wait <selector>
brow wait --load
```

### Observation

```bash
brow snapshot [--search <regex>] [--locator <selector>]
brow screenshot [--full] [--path <file>]
brow html [--locator <selector>] [--search <regex>]
brow logs [--search <regex>] [--count <n>]
brow url
```

### Interaction

```bash
brow click <selector>
brow fill <selector> <value>
brow type <text>
brow key <key>                    # Enter, Tab, Meta+a
brow hover <selector>
brow scroll [--pixels <n>]
brow scroll-to <selector>
brow drag <from> <to>
brow upload <selector> <filepath>
brow click-until <selector> --until-gone <selector>
```

### Pages

```bash
brow page list
brow page new [url]
brow page close [index]
brow page switch <index>
```

### Profiles & State

```bash
brow profile list
brow profile prune [--days <n>] [--yes]   # reclaim disk from one-shot profiles
brow profile delete <name>
brow state save <name>
brow state restore <name>
brow state list
```

### Eval & Run

```bash
brow eval <code>                  # inline, one-off
brow run workflow.py --arg k=v    # reusable, from a file
```

Variables available: `page`, `context`, `browser`, `state`, `pages`, plus `args` (from `--arg`) for `run`.

## Selectors

Playwright selector syntax:
- CSS: `button.submit`, `#login`
- Text: `text=Login`
- Role: `role=button[name="Save"]`
- XPath: `xpath=//div`

## Architecture

```
  ┌─────────────────────────────────────────────────────────────────┐
  │  Agent (Claude Code, script, etc.)                              │
  │                                                                 │
  │  brow login                         ← sign in by hand, once     │
  │  brow navigate "https://..."        ← go to page                │
  │  brow snapshot                      ← read page (a11y tree)     │
  │  brow click "text=Login"            ← interact                  │
  │  brow fill "#email" "me@..."        ← fill form                 │
  │  brow screenshot                    ← capture screen            │
  │  brow eval "await page..."          ← escape hatch              │
  └──────────────┬──────────────────────────────────────────────────┘
                 │ HTTP (localhost:19987)
                 ▼
  ┌──────────────────────────────────────┐
  │  brow daemon (FastAPI + uvicorn)     │
  │                                      │
  │  ┌──────────┐  ┌──────────────────┐  │
  │  │ Session 1 │  │ ProfileManager   │  │
  │  │ (browser) │  │ ~/.brow/profiles │  │
  │  ├──────────┤  └──────────────────┘  │
  │  │ Session 2 │                       │
  │  │ (browser) │  ┌──────────────────┐  │
  │  └──────────┘  │ StateManager     │  │
  │                 │ ~/.brow/states   │  │
  │                 └──────────────────┘  │
  └──────────────┬───────────────────────┘
                 │ CDP (Chrome DevTools Protocol)
                 ▼
  ┌──────────────────────────────────────┐
  │  Chromium (via Playwright)           │
  │                                      │
  │  ┌────────┐ ┌────────┐ ┌────────┐   │
  │  │ Page 1 │ │ Page 2 │ │ Page 3 │   │
  │  └────────┘ └────────┘ └────────┘   │
  └──────────────────────────────────────┘
```

- Daemon auto-starts on first `brow` command
- Persistent Chromium profiles for login session survival
- One browser per session, full isolation
- Headless by default, `--headed` to watch — headless runs Chrome's new headless mode, not
  `chrome-headless-shell`, so it keeps a real GPU and fingerprint
- Commands with no `-s` resolve to your default profile via `~/.brow/current.json`

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `BROW_HOME` | `~/.brow` | Data directory |
| `BROW_PORT` | `19987` | Daemon port |
| `BROW_MAX_SESSIONS` | `10` | Max concurrent sessions |
| `BROW_PROFILE` | `personal` | Profile used by commands without `-s` |

## Resource Usage

~150-300MB per Chromium instance. 10 sessions = ~2-3GB.

## License

Elastic License 2.0 (releases <=1.2.0 remain MIT-licensed).
