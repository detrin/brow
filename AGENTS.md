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
brow snapshot -s <id> [--search <regex>] [--limit N] [--locator <sel>]   # prefer over screenshot
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
brow click-until -s <id> <selector> [--until-gone <selector>] [--max-iterations N] [--settle-ms N]
# Prints the click count; if it stopped early the reason goes to stderr.

# Fetch (uses browser cookies — bypasses auth walls)
brow fetch -s <id> <url> [-X POST] [-H "Header: val"] [-d '{"body":"json"}']
# Body goes to stdout; a non-2xx status is reported on stderr.

# Eval (one-off Python, inline)
brow eval -s <id> "<python code>"           # vars: page, context, browser, state, pages
brow eval -s <id> "<code>" --timeout 300000 # default 30s — RAISE IT for long jobs
# print() output IS returned, and `result = ...` is returned as JSON.

# Run (reusable Python, from a file — same vars as eval, plus args)
brow run -s <id> workflow.py [--arg key=value] [--timeout 300000]
# args['key'] is available in the script for each --arg passed.

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

- A `[brow] brow X.Y.Z is available ...` line on stderr is an informational
  update notice, not an error — safe to ignore. Disable with `BROW_NO_UPDATE_CHECK=1`.
- Prefer `snapshot` over `screenshot` — faster, token-efficient, AI-readable
- A snapshot can be truncated. When it is, it says so on stderr:
  `⚠ truncated: 361 of 4,529 nodes (main complete — omitted nodes are page chrome)`.
  Read the parenthetical before trusting an absence: `main complete` means what
  was dropped is chrome, while `also truncated` or `no content landmark found`
  means the answer may be missing. Don't reach for `html` — narrow the walk:
- `snapshot --locator "<css>"` walks only that subtree, which is the cheapest way
  to get a big listing or table in full. A locator matching nothing is an error,
  not a silent full-page snapshot
- `snapshot --search "<regex>"` searches the *whole* page, including nodes the
  default walk omits and table rows past the row cap. It prints only matching
  lines (10 by default; raise with `--limit`) and reports on stderr when it
  withheld matches
- `network --clear` before navigation to isolate requests for a specific page
- `fetch` uses the browser's real cookies — use it to call authenticated APIs
- `eval` returns both `print()` output and `result` — read it, don't just use it for side effects
- **Long jobs: raise `--timeout` instead of batching.** Draining work a few items
  per call (staging state on `window.*` and looping) is slower and loses progress
  when a call dies. One `--timeout 300000` call does the same work in one shot.
- **Bulk work belongs in one `eval`/`run`, not N CLI calls.** Each `brow` invocation
  is a fresh process plus an HTTP round trip. A loop inside one call avoids both.
- **Draining a paginated list: use `click-until`.** "Act on the visible batch, the
  list refills, act again" is one command, not a shell loop. Always read the exit
  reason — `--max-iterations` stopping early looks the same as finishing otherwise.
- **Never `for id in ...; do brow eval ...; done` from your own shell.** That's a
  process + round trip per item, thrown away the moment the task ends. Use one of
  the two mechanisms below instead, chosen by whether you'll need it again:

| Need | Use |
|---|---|
| Looking around, one command at a time | Individual commands (`click`, `fill`, `snapshot`, ...) |
| A one-off bulk operation, never reused | Inline `brow eval "<code>"` |
| Python you might rerun, tweak, or hand to someone else | `brow run workflow.py` (below) |
| A short, declarative, auditable sequence (no branching/loops in your head) | YAML `brow replay` (further below) |

## Running a script in the session (`brow run`)

For anything reusable, write a `.py` file and run it once inside the session —
same variables as `eval` (`page`, `context`, `browser`, `state`, `pages`), plus
`args` from `--arg key=value`:

```bash
brow run -s 1 workflow.py --arg query=widgets --timeout 300000
```

```python
# workflow.py
items = await page.locator(".item").all()

for item in items:
    await item.click()
    await page.wait_for_selector(".saved")

result = {"processed": len(items)}   # returned as JSON; print() is also returned
```

This is plain Python with Playwright semantics — loops, conditionals, retries,
functions, whatever the task needs — running as ONE call against the live,
already-authenticated session, instead of a shell loop re-invoking `brow`
per item. Prefer it over shell-looping `eval`/CLI calls for anything with more
than a couple of iterations, and over YAML playbooks once the logic needs a
branch or a loop body more complex than "repeat these steps."

## Scripting a workflow (playbooks)

For a short, declarative, auditable sequence — no real branching, just steps —
write a YAML playbook once and run it with `brow replay`. For anything with
loop bodies more complex than a few flat steps, prefer `brow run` above.

```bash
brow replay playbook.yaml -s 1 [--var key=value]
```

```yaml
base_url: https://example.com
vars:
  query: widgets

steps:
  - action: navigate
    url: /search?q={query}

  - action: wait                    # wait for a condition, not a guessed sleep
    selector: "#results"
    state: visible                  # visible | hidden | attached | detached
    timeout: 10000

  - action: assert                  # fail loudly if a precondition doesn't hold
    selector: ".result-count"
    state: visible

  - action: fetch
    url: /api/items?q={query}
    headers:
      X-Api-Key: "{api_key}"
    output: items                   # captured JSON becomes {items} in later steps

  - action: for_each                # replaces "N near-identical CLI calls"
    var: item
    items: items                    # a captured variable (must be a list)...
    # items: [1, 2, 3]              # ...or an inline literal list
    steps:
      - action: navigate
        url: /item/{item[id]}       # dict/list indexing into captured JSON
      - action: click
        selector: "text=Save"
```

Supported step actions: `navigate`, `click`, `fill`, `key`, `select`, `fetch`
(`headers`, `auth: none` for cookie-less, `output: name` to capture JSON for
later steps), `wait` (`selector`+`state`, or `ms` for a fixed sleep), `assert`
(same shape as `wait`, but a non-match is reported as a failed step), and
`for_each` (loop a nested `steps` list over a literal or captured list).

By default a failed step is recorded but the playbook keeps going. Add
`stop_on_failure: true` at the top level to halt on the first failure — use
this when a later step's `{var}` substitution depends on an earlier one
having actually run.

`brow actions -s <id> --json` shows the raw action log for a live session if
you want to crystallize what you just did by hand into a playbook.

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
