---
title: Sessions
description: Creating and managing browser sessions
---

## `brow session new`

Start a new browser session. Returns the session ID.

```
brow session new [--profile <name>] [--headed] [--url <url>]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--profile` | `default` | Chromium profile name (persistent login state) |
| `--headed` | `false` | Show the browser window |
| `--url` | none | Navigate immediately after opening |

```bash
brow session new                          # → 1  (headless, default profile)
brow session new --headed                 # → 2  (visible window)
brow session new --profile mysite --headed  # → 3  (named profile, visible)
brow session new --url "https://example.com"  # → 4  (navigate on start)
```

The returned integer is the session ID used in all subsequent commands.

!!! warning "Profile conflict"
    Each profile can only be used by one session at a time. If you try to open the same profile twice, you'll get: `Profile 'default' already in use by session 1`. Use unique `--profile <name>` values for concurrent sessions.

## `brow session list`

List all active sessions.

```bash
brow session list
# 1    default    headless    1 pages
# 2    mysite     headed      2 pages
```

Columns: `id`, `profile`, `headed/headless`, `page count`.

## `brow session delete`

Close a session and release its resources. The profile directory is preserved.

```
brow session delete <session-id>
```

```bash
brow session delete 1
# Deleted session 1
```
