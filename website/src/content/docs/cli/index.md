---
title: CLI Reference
description: Complete reference for all brow CLI commands
---

All brow commands follow the pattern:

```
brow <command> -s <session-id> [options]
```

The `-s` / `--session` flag is required for any command that operates on a session. Session IDs are simple integers assigned at creation time.

## Command groups

| Group | Commands |
|-------|----------|
| [Daemon](/brow/cli/daemon/) | `daemon start`, `daemon stop`, `daemon status` |
| [Sessions](/brow/cli/sessions/) | `session new`, `session list`, `session delete`, `session cleanup` |
| [Navigation](/brow/cli/navigation/) | `navigate`, `wait`, `url` |
| [Interaction](/brow/cli/interaction/) | `click`, `click-until`, `fill`, `select`, `type`, `key`, `hover`, `scroll`, `scroll-to`, `drag`, `upload` |
| [Observation](/brow/cli/observation/) | `snapshot`, `screenshot`, `html`, `logs`, `network`, `fetch`, `websocket` |
| [Pages](/brow/cli/pages/) | `page list`, `page new`, `page close`, `page switch` |
| [Profiles & State](/brow/cli/profiles-state/) | `profile list`, `profile delete`, `state save`, `state restore`, `state list` |
| [Actions & Replay](/brow/cli/actions-replay/) | `actions`, `replay` |
| [Eval & Run](/brow/cli/eval-run/) | `eval`, `run` |

## Auto-start

The daemon starts automatically when you run any session command. You don't need to call `brow daemon start` manually.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Daemon failed to start |
| `2` | API error (details printed to stderr) |
