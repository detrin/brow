# brow — Browser Automation

Use `brow` to control a real Chromium browser. Daemon auto-starts on first command.

## Quickstart

```bash
brow session new --headed     # → session id (e.g. 1)
brow navigate -s 1 "https://example.com"
brow snapshot -s 1            # read page as accessibility tree
brow click -s 1 "text=Login"
brow fill -s 1 "#email" "user@example.com"
brow key -s 1 Enter
brow screenshot -s 1
brow session delete 1
```

## Commands

```bash
# Sessions
brow session new [--headed] [--profile <name>]
brow session list
brow session delete <id>

# Navigation
brow navigate -s <id> <url>
brow wait -s <id> <selector>
brow wait -s <id> --load

# Observe
brow snapshot -s <id> [--search <regex>]     # accessibility tree — prefer over screenshot
brow screenshot -s <id> [--full]
brow html -s <id>
brow url -s <id>
brow logs -s <id> [--count N] [--search <str>]
brow network -s <id> [--count N] [--search <str>] [--response] [--clear]
brow websocket -s <id> [--count N] [--search <str>] [--clear]

# Interact
brow click -s <id> <selector>
brow fill -s <id> <selector> <value>
brow type -s <id> <text>
brow key -s <id> <key>          # Enter, Tab, Space, PageDown, End, Home, Meta+a
brow hover -s <id> <selector>
brow scroll -s <id> [--pixels N]
brow upload -s <id> <selector> <filepath>   # use CSS selector, not ref id

# Fetch (uses browser cookies — bypasses auth walls)
brow fetch -s <id> <url> [-X POST] [-H "Header: val"] [-d '{"body":"json"}']

# Eval (Playwright Python, no stdout return)
brow eval -s <id> "<python code>"           # vars: page, context, browser

# Pages (tabs)
brow page list -s <id>
brow page new -s <id> [url]
brow page switch -s <id> <index>
brow page close -s <id> [index]
```

## Selectors

- CSS: `#id`, `button.class`, `input[type='file']`
- Text: `text=Sign In`
- Role: `role=button[name="Save"]`
- Ref: `--ref <n>` from snapshot output (click/fill/select only)

## Scrolling in iframes / fixed containers

`scroll` only works on the outer page. For Streamlit, React dashboards, iframes:

```bash
brow click -s 1 "text=Section"   # focus area
brow key -s 1 PageDown
brow key -s 1 End
```

## Profiles (persistent login)

```bash
brow session new --profile myprofile --headed   # log in once manually
brow session delete 1

brow session new --profile myprofile            # reuse — already logged in
```

Profile conflict: `Profile 'X' already in use by session N` → use a different `--profile` name per concurrent session.

## Testing a local web app

```bash
brow session new --headed
brow navigate -s 1 "http://localhost:3000"
brow snapshot -s 1
brow fill -s 1 "#username" "testuser"
brow fill -s 1 "#password" "pass"
brow click -s 1 "text=Submit"
brow snapshot -s 1                # verify result
brow session delete 1
```

## Browsing documentation (JS-rendered or auth-gated sites)

```bash
brow session new
brow navigate -s 1 "https://docs.example.com/api-reference"
brow snapshot -s 1
brow key -s 1 End                 # scroll to load more
brow snapshot -s 1 --search "authentication"
brow session delete 1
```

## Tips

- Prefer `snapshot` over `screenshot` — faster, token-efficient, AI-readable
- `network --clear` before navigation to isolate requests for a specific page
- `fetch` uses the browser's real cookies — use it to call authenticated APIs
- `eval` output is not returned to stdout — use only for side effects
