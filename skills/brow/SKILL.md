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
| `eval -s <id> <code>` | Run Playwright Python (side effects only — no stdout return) |

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

**Profile conflict:** `session new` fails if the profile is already in use: `Profile 'default' already in use by session N`. Fix: use a unique `--profile <name>` per concurrent session.

## Tips

- Use `--headed` to see the browser while debugging
- Use `snapshot` over `screenshot` — it's faster and uses fewer tokens
- `eval` runs arbitrary Playwright Python but output is not returned to stdout — use for side effects only
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
