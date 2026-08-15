---
name: brow
description: Browser automation CLI for agents — control Chromium with simple commands
---

# brow — Browser Automation for Agents

Control a real Chromium browser from Claude Code. Navigate pages, click buttons, fill forms, take screenshots, and read page content — all through simple CLI commands.

## Setup

```bash
pip install brow-cli
brow setup
```

## Usage

Syntax is **subcommand-first**, with `-s <id>` on the subcommand:

```bash
brow session new --headed          # → 1
brow navigate -s 1 "https://example.com"
brow snapshot -s 1                 # accessibility tree
brow click -s 1 "text=Login"
brow fill -s 1 "#email" "user@example.com"
brow fill -s 1 "#password" "secret"
brow key -s 1 Enter
brow screenshot -s 1               # saves to ~/.brow/screenshots/
brow session delete 1
```

## Key Commands

| Command | Description |
|---------|-------------|
| `session new [--headed] [--profile <name>]` | Start browser session |
| `navigate -s <id> <url>` | Go to URL |
| `snapshot -s <id>` | Get accessibility tree (best for understanding page) |
| `screenshot -s <id>` | Capture screenshot |
| `click -s <id> <selector>` | Click element |
| `fill -s <id> <selector> <value>` | Fill input field |
| `type -s <id> <text>` | Type with keyboard |
| `key -s <id> <key>` | Press key (Enter, Tab, Space, PageDown, End, Home) |
| `scroll -s <id> [--pixels <n>]` | Scroll the outermost page |
| `upload -s <id> <selector> <file>` | Upload file (use CSS selector, not numeric ID) |
| `html -s <id>` | Get page HTML |
| `logs -s <id> [--count N] [--search <str>]` | Get console logs |
| `network -s <id> [--count N] [--search <str>] [--response] [--clear]` | Get network requests |
| `fetch -s <id> <url> [-X method] [-H header] [-d body] [--no-cookies]` | Browser fetch → stdout; `--no-cookies` does plain HTTP to test auth requirement |
| `websocket -s <id> [--count N] [--search <str>] [--clear]` | Get WebSocket messages |
| `actions -s <id> [--json] [--clear]` | View recorded action log for current session |
| `replay -s <id> <playbook.yaml> [--var k=v]` | Replay a playbook YAML (with optional var overrides) |
| `eval -s <id> <code>` | Run Python inline; returns `result` + stdout. Helpers: `text(sel)`, `texts(sel)` |
| `run -s <id> <file.py> [--arg k=v]` | Run a reusable Python file in the session; same vars as `eval`, plus `args` |

## Scrolling

`scroll` only works on the outermost page — it does nothing inside iframes or fixed-height containers (Streamlit, React dashboards):

```bash
brow scroll -s 1 --pixels 3000    # scroll outer page down
```

For content inside iframes or constrained containers, use keyboard navigation instead:

```bash
brow click -s 1 "text=Section Heading"   # focus the area
brow key -s 1 Space                       # scroll down half-page
brow key -s 1 PageDown                    # scroll down full page
brow key -s 1 End                         # jump to bottom
```

## Network Inspection

Captures all requests across the session (accumulates across navigations). Static assets (images, fonts, scripts, CSS) are filtered out by default:

```bash
brow network -s 1                          # last 50 non-static requests
brow network -s 1 --count 100             # last 100
brow network -s 1 --search "api"          # filter by URL/content-type
brow network -s 1 --response              # include 200-char response body preview
brow network -s 1 --include-static        # include all asset requests
brow network -s 1 --clear                 # reset the log (use before navigation to isolate requests)
```

Output format: `METHOD  STATUS  content-type                    url`

## Authenticated Fetch

Make requests with the browser's session cookies — essential for reverse-engineering authenticated APIs:

```bash
brow fetch -s 1 "/rest/offer/v2/competitions/136806/matches" | jq
brow fetch -s 1 "https://example.com/api/data" -X POST -d '{"key":"val"}' -H "Content-Type: application/json"
```

## Running Python Workflows (`run`)

`eval` is for one-off inline snippets. `run` is for anything with a loop or a
condition — write it as a `.py` file and it executes once inside the live
session (same `page`/`context`/`browser`/`state`/`pages` vars as `eval`, plus
`args` from `--arg key=value`):

```bash
brow run -s 1 workflow.py --arg query=widgets
```

**Where this earns its keep over the alternatives:** scraping a paginated
listing whose pages are rendered by JS (not real navigations) — the loop has
to wait for each page's render, validate what it got before trusting it, and
decide per-item whether to keep going, none of which a flat list of steps or
a shell loop of `brow eval` calls does well:

```python
# scrape_paginated.py
results = []
page_num = 1
while True:
    await page.wait_for_selector(".product-row", timeout=10000)   # wait for render, not a guessed sleep
    for row in await page.locator(".product-row").all():
        price_text = await row.locator(".price").inner_text()
        price = float(price_text.strip("$"))
        if price <= 0:                                            # a check, not just hope
            raise ValueError(f"page {page_num}: bad price {price_text!r} — stopping before bad data spreads")
        results.append({"name": await row.locator(".name").inner_text(), "price": price})

    next_btn = page.locator("#next")
    if await next_btn.count() == 0 or not await next_btn.is_visible():
        break                                                     # loop until the data says stop, not a fixed N
    await next_btn.click()
    await page.wait_for_timeout(150)
    page_num += 1

result = {"pages": page_num, "items": len(results), "data": results}
```

```bash
brow run -s 1 scrape_paginated.py
# {"pages": 3, "items": 5, "data": [...]}
```

Why not the alternatives here: a shell loop of `brow eval` per page costs a
process + HTTP round trip per page and still has to guess how long to sleep
after each click; a YAML `replay` playbook has no way to say "keep clicking
Next until the button is gone AND validate every row before trusting the
page," since `for_each` needs the item count known up front. One `run` call
does the wait, the check, and the open-ended loop natively, and a bad page
aborts the whole call with a clear error instead of silently returning
partial or wrong data.

## WebSocket Inspection

Live sites push updates over WebSocket (socket.io, etc.). Capture and inspect frames:

```bash
brow websocket -s 1                        # last 50 messages
brow websocket -s 1 --search "patch"       # filter by content
brow websocket -s 1 --clear               # reset the log
```

WebSocket messages are captured automatically from session start. Use `--clear` before a navigation to isolate messages for a specific page.

## File Upload

Use CSS selectors — numeric snapshot IDs return 500:

```bash
brow upload -s 1 "input[type='file']" data.csv    # works
brow upload -s 1 "[3]" data.csv                   # fails with 500
```

## Profiles

Persistent Chromium profiles survive across sessions. Log in once, reuse forever:

```bash
brow session new --profile gmail --headed
brow navigate -s 1 "https://gmail.com"
brow session delete 1

# Next time — already logged in:
brow session new --profile gmail
```

**Profile conflict:** `session new` fails if the profile is already in use: `Profile 'default' already in use by session N`. Fix: use a unique `--profile <name>` per concurrent session, or pass `--reclaim` to close the stale session and take over the profile.

## Tips

- Use `--headed` to see the browser while debugging
- Use `snapshot` over `screenshot` — it's faster and uses fewer tokens
- Click/fill accept the snapshot ref directly: `click "[1]"` works (same as `click --ref 1`)
- `eval` returns `result` and stdout. `page` is async — `await` everything, or use the `text(sel)` / `texts(sel)` helpers for quick extraction
- `navigate --wait networkidle` for JS-heavy pages instead of guessing with `sleep`
- Session IDs are simple integers: 1, 2, 3...

## API Scouting

To reverse-engineer a site's API and generate a minimal scraper script, read the reference:
[references/api-scout.md](references/api-scout.md)

## Playbook Writer

After completing a brow session that accomplishes a task, crystallize it into a reusable YAML playbook and Python script:
[references/playbook-writer.md](references/playbook-writer.md)

## Selectors

- CSS: `#login`, `button.submit`, `input[type='file']`
- Text: `text=Sign In`
- Role: `role=button[name="Save"]`
