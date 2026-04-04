---
title: Navigation
description: Navigating pages and waiting for load events
---

## `brow navigate`

Navigate to a URL. Waits for the page to load and returns a snapshot.

```
brow navigate -s <id> <url> [--timeout <ms>]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--timeout` | `30000` | Navigation timeout in milliseconds |

```bash
brow navigate -s 1 "https://example.com"
# https://example.com/ [200]
# h1 "Example Domain"
# [1] a "More information..." href="https://iana.org/domains/example"
```

Output: current URL, HTTP status code, then the accessibility tree snapshot.

Relative URLs are supported when the page already has an origin:

```bash
brow navigate -s 1 "https://github.com"
brow navigate -s 1 "/anthropics/claude-code"   # → https://github.com/anthropics/claude-code
```

## `brow wait`

Wait for a selector to appear, or for the page to reach a network-idle state.

```
brow wait -s <id> [--selector <sel>] [--load] [--timeout <ms>]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--selector` | none | CSS or text selector to wait for |
| `--load` | `false` | Wait for `networkidle` instead |
| `--timeout` | `30000` | Timeout in milliseconds |

```bash
brow wait -s 1 --selector ".results-table"     # wait for element
brow wait -s 1 --load                          # wait for network idle
```

Use `wait` after actions that trigger asynchronous content loading (AJAX, SPA navigation).

## `brow url`

Get the current page URL.

```
brow url -s <id>
```

```bash
brow url -s 1
# https://example.com/page?q=test
```
