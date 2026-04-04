---
title: Concepts
description: Architecture and core concepts of brow
---

## Sessions

A **session** is a running Chromium browser context backed by a persistent profile directory. Sessions are identified by a simple integer ID (1, 2, 3…).

```
Session 1
├── Profile: ~/.brow/profiles/default/  (Chromium user data)
├── Pages: [page-0 (active), page-1, ...]
└── State:
    ├── console_logs      (last 500)
    ├── network_requests  (last 500)
    ├── websocket_messages (last 200)
    └── actions           (all, until cleared)
```

### Profile isolation

Each session uses exactly one profile. Two sessions cannot share the same profile simultaneously — this prevents cookie conflicts. If you try to open the same profile in two sessions you'll get:

```
Profile 'default' already in use by session 1
```

Use distinct `--profile <name>` values for concurrent sessions.

### Session lifecycle

```
session new → [browser process starts] → commands → session delete → [browser closes]
```

The profile directory persists after `session delete` — cookies and localStorage are preserved for next time.

## Snapshots

A **snapshot** is brow's primary way to read the page. It returns an **accessibility tree** — a structured representation of interactive and meaningful elements, not raw HTML.

```
brow snapshot -s 1
```

Example output:

```
navigation
  a "Home" href="/"
  a "Docs" href="/docs"
main
  h1 "Getting Started"
  p "Install with pip..."
  [1] button "Try it"
  [2] a "GitHub" href="https://github.com/..."
  table
    thead: Name | Version | Description
    brow-cli | 1.0.2 | Standalone Playwright CLI
```

Numbers in brackets (`[1]`, `[2]`) are **refs** — interactive element identifiers you can pass to `click`, `fill`, and `select`:

```bash
brow click -s 1 --ref 1
brow fill -s 1 --ref 2 "my value"
```

### Why not HTML?

HTML is verbose (thousands of tokens for a typical page) and full of irrelevant structure. The accessibility tree is:
- **Compact**: only meaningful nodes
- **Structured**: already parsed into a hierarchy
- **Ref-addressable**: direct handles to interactive elements
- **LLM-friendly**: easy to reason about

Use `brow html -s 1` when you need the raw DOM (e.g., to extract table data that isn't captured by the accessibility tree).

## Network inspection

Every HTTP response the browser makes is captured in the session's network log:

```bash
brow network -s 1                    # last 50 non-static requests
brow network -s 1 --search api       # filter by URL substring
brow network -s 1 --response         # include response body preview
```

Static assets (images, fonts, CSS, JS) are filtered out by default. Use `--include-static` to see them.

The network log is the starting point for [API scouting](tutorials/api-scouting.md) — watching what requests the page makes lets you call those endpoints directly.

## Action log

Every productive command is recorded in the session's action log:

```bash
brow actions -s 1           # human-readable
brow actions -s 1 --json    # machine-readable
```

This is the input for the [Playbook Writer](tutorials/playbook-writer.md): review the action log, keep the essential steps, write a YAML playbook, and generate a standalone Python script.

## Playbooks

A **playbook** is a YAML file that describes a repeatable browser workflow. Variables use `{name}` substitution:

```yaml
name: search-hn
base_url: https://news.ycombinator.com
vars:
  query: brow

steps:
  - action: navigate
    url: /
  - action: fill
    selector: "input[name=q]"
    value: "{query}"
  - action: key
    key: Enter
```

Run it:

```bash
brow replay search-hn.yaml -s 1 --var query=playwright
```

Playbooks are the bridge between an exploratory LLM-driven session and a production script. See the [Playbook Writer tutorial](tutorials/playbook-writer.md).

## Auth strategies

When reverse-engineering an API, there are three patterns:

| Strategy | When | Output |
|----------|------|--------|
| `none` | All needed endpoints return 200 with `--no-cookies` | Pure `httpx` script |
| `browser-session` | Cookies required, but UI not | Playwright cookie harvest + `httpx` |
| `browser` | Must interact with UI to get data | Full Playwright script |

The `brow fetch --no-cookies` command is used to probe which strategy applies to each endpoint.
