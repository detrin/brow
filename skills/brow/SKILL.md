# brow — Browser Automation for Agents

Control a real Chromium browser from Claude Code. Navigate pages, click buttons, fill forms, take screenshots, and read page content — all through simple CLI commands.

## Setup

```bash
pip install brow-cli
playwright install chromium
```

## Usage

Start a browser session and interact with it:

```bash
brow session new --headed          # → 1
brow -s 1 navigate "https://example.com"
brow -s 1 snapshot                 # accessibility tree
brow -s 1 click "text=Login"
brow -s 1 fill "#email" "user@example.com"
brow -s 1 fill "#password" "secret"
brow -s 1 key Enter
brow -s 1 screenshot               # saves to ~/.brow/screenshots/
brow session delete 1
```

## Key Commands

| Command | Description |
|---------|-------------|
| `session new [--headed] [--profile <name>]` | Start browser session |
| `navigate <url>` | Go to URL |
| `snapshot` | Get accessibility tree (best for understanding page) |
| `screenshot` | Capture screenshot |
| `click <selector>` | Click element |
| `fill <selector> <value>` | Fill input field |
| `type <text>` | Type with keyboard |
| `key <key>` | Press key (Enter, Tab, Meta+a) |
| `html` | Get page HTML |
| `eval <code>` | Run arbitrary Playwright Python code |

## Tips

- Use `--headed` to see the browser while debugging
- Use `snapshot` over `screenshot` — it's faster and uses fewer tokens
- Profiles persist login sessions: `brow session new --profile gmail`
- Use `eval` for anything the structured commands can't do
- Session IDs are simple integers: 1, 2, 3...

## Selectors

- CSS: `#login`, `button.submit`
- Text: `text=Sign In`
- Role: `role=button[name="Save"]`

## Profiles

Persistent Chromium profiles survive across sessions. Log in once, reuse forever:

```bash
brow session new --profile gmail --headed
brow -s 1 navigate "https://gmail.com"
# ... log in manually ...
brow session delete 1

# Next time — already logged in:
brow session new --profile gmail
```
