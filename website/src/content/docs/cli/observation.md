---
title: Observation
description: Snapshots, screenshots, HTML, logs, network, and WebSocket inspection
---

## `brow snapshot`

Get the accessibility tree of the current page. This is the primary way to read page content.

```
brow snapshot -s <id> [--search <regex>] [--locator <selector>]
```

| Flag | Description |
|------|-------------|
| `--search` | Filter tree to nodes matching this regex |
| `--locator` | Restrict tree to a subtree rooted at this selector |

```bash
brow snapshot -s 1                           # full tree
brow snapshot -s 1 --search "price"          # only nodes containing "price"
brow snapshot -s 1 --locator "main"          # only the <main> element subtree
```

Interactive elements are annotated with refs in brackets — use them with `--ref N` in click/fill/select:

```
[1] button "Add to cart"
[2] input "Email address"
[3] a "Read more" href="/article/42"
```

If the page has more than ~500 interactive elements, the snapshot is truncated and a hint is shown. Use `--search` to filter.

## `brow screenshot`

Capture a screenshot. Saved to `~/.brow/screenshots/` by default.

```
brow screenshot -s <id> [--full] [--path <file>] [--width <px>] [--scale <f>] [--quality low|medium|high]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--full` | `false` | Capture full page (not just viewport) |
| `--path` | auto-generated | Save path |
| `--width` | viewport | Resize browser to this width before capture |
| `--scale` | `1.0` | Scale factor |
| `--quality` | none | Preset: `low` (400px), `medium` (800px), `high` (1200px) |

```bash
brow screenshot -s 1                          # viewport screenshot
brow screenshot -s 1 --full                   # full page
brow screenshot -s 1 --quality medium         # 800px wide
brow screenshot -s 1 --path /tmp/page.png     # specific path
```

Returns the file path of the saved screenshot.

## `brow html`

Get the HTML content of the page (or a subtree).

```
brow html -s <id> [--locator <selector>] [--search <regex>]
```

```bash
brow html -s 1                        # full page HTML
brow html -s 1 --locator "article"   # just the <article> element
brow html -s 1 --search "price"      # lines containing "price"
```

Use `html` when you need raw markup that `snapshot` doesn't capture (e.g. table data, custom attributes).

## `brow logs`

Get console log messages from the page.

```
brow logs -s <id> [--search <str>] [--count <n>]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--search` | none | Filter by substring |
| `--count` | `50` | Number of recent entries to return |

```bash
brow logs -s 1
brow logs -s 1 --search "error" --count 100
```

Captures all `console.log`, `console.warn`, `console.error`, etc. messages.

## `brow network`

View HTTP requests made by the browser.

```
brow network -s <id> [--search <str>] [--count <n>] [--response] [--include-static] [--clear]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--search` | none | Filter by URL or content-type |
| `--count` | `50` | Number of recent entries |
| `--response` | `false` | Include first 200 chars of response body |
| `--include-static` | `false` | Include images, fonts, CSS, JS requests |
| `--clear` | — | Reset the log |

```bash
brow network -s 1                              # last 50 API requests
brow network -s 1 --search "api"              # filter by URL
brow network -s 1 --response                  # show response previews
brow network -s 1 --clear                     # reset before next navigation
```

Output format:

```
POST   200  application/json    https://api.example.com/v2/search
  → {"results":[{"id":1,"name":"foo"...
GET    200  application/json    https://api.example.com/v2/user/profile
```

This command is the foundation of API scouting. See the [API Scouting tutorial](../tutorials/api-scouting.md).

## `brow fetch`

Make an HTTP request using the browser's session cookies (or without cookies to test auth).

```
brow fetch -s <id> <url> [-X <method>] [-H <header>] [-d <body>] [--no-cookies]
```

| Flag | Default | Description |
|------|---------|-------------|
| `-X` / `--method` | `GET` | HTTP method |
| `-H` / `--header` | — | Header in `Key: Value` format (repeatable) |
| `-d` / `--data` | — | Request body |
| `--no-cookies` | `false` | Skip browser cookies (plain httpx request) |

```bash
# Authenticated request (with browser cookies)
brow fetch -s 1 "https://api.example.com/user/me" | jq

# Test if endpoint works without auth
brow fetch -s 1 "https://api.example.com/public/data" --no-cookies

# POST with JSON body
brow fetch -s 1 "https://api.example.com/search" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"query":"test"}'
```

The response body is written to stdout. Combine with `jq` for JSON exploration.

## `brow websocket`

View WebSocket messages captured during the session.

```
brow websocket -s <id> [--search <str>] [--count <n>] [--clear]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--search` | none | Filter by message content |
| `--count` | `50` | Number of recent messages |
| `--clear` | — | Reset the log |

```bash
brow websocket -s 1
brow websocket -s 1 --search "patch"      # find JSON Patch messages
brow websocket -s 1 --clear               # reset before next navigation
```

Output format:

```
recv  wss://realtime.example.com/socket  {"op":"replace","path":"/odds/1","value":1.85}
sent  wss://realtime.example.com/socket  42["subscribe",{"channel":"matches"}]
```

WebSocket messages are captured automatically from session start, including socket.io frames.
