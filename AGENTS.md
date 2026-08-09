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

# Repeat a click until the work runs out (pagination, "load more", batch actions)
brow click-until -s <id> <selector> [--until-gone <selector>] [--max-iterations N]
# Prints the click count; if it stopped early the reason goes to stderr.

# Fetch (uses browser cookies — bypasses auth walls)
brow fetch -s <id> <url> [-X POST] [-H "Header: val"] [-d '{"body":"json"}']
# Body goes to stdout; a non-2xx status is reported on stderr.

# Eval (Playwright Python)
brow eval -s <id> "<python code>"           # vars: page, context, browser, state, pages
brow eval -s <id> "<code>" --timeout 300000 # default 30s — RAISE IT for long jobs
# print() output IS returned, and `result = ...` is returned as JSON.

# Pages (tabs)
brow page list -s <id>                      # '*' marks the active tab
brow page new -s <id> [url]
brow page switch -s <id> <index>            # retargets all later commands
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
- `eval` returns both `print()` output and `result` — read it, don't just use it for side effects
- **Long jobs: raise `--timeout` instead of batching.** Draining work a few items
  per call (staging state on `window.*` and looping) is slower and loses progress
  when a call dies. One `--timeout 300000` call does the same work in one shot.
- **Bulk work belongs in one `eval`, not N CLI calls.** Each `brow` invocation is a
  fresh process plus an HTTP round trip. A loop inside a single `eval` avoids both.
- **Draining a paginated list: use `click-until`.** "Act on the visible batch, the
  list refills, act again" is one command, not a shell loop. Always read the exit
  reason — `--max-iterations` stopping early looks the same as finishing otherwise.

## Driving an app's own API

Often faster and far more reliable than clicking through a UI: read the app's
network traffic, then call the same endpoints with the browser's cookies.

```bash
brow network -s 1 --search "api" --response   # find the endpoint
brow fetch -s 1 "/api/v4/items?limit=100"     # relative URLs resolve against the page
```

If you get a 401/403 that the UI clearly doesn't get:

- The app may require custom headers (an app-version or client-id header is
  common). Pass them with `-H`; they are forwarded as-is.
- The request may need to originate from the app's own origin. `fetch` runs in the
  active page, so `navigate` to the app first — the same call from a different
  page of the same product can fail.

## Working with several tabs

`page switch` sets the target for every later command, and `page list` marks the
active tab with `*`. Check it after anything that might open a tab (OAuth popups,
`target=_blank`) so you know where the next command will land.
