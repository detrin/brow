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
| [Daemon](daemon.md) | `daemon start`, `daemon stop`, `daemon status` |
| [Sessions](sessions.md) | `session new`, `session list`, `session delete` |
| [Navigation](navigation.md) | `navigate`, `wait`, `url` |
| [Interaction](interaction.md) | `click`, `fill`, `select`, `type`, `key`, `hover`, `scroll`, `scroll-to`, `drag`, `upload` |
| [Observation](observation.md) | `snapshot`, `screenshot`, `html`, `logs`, `network`, `fetch`, `websocket` |
| [Actions & Replay](actions-replay.md) | `actions`, `replay` |
| Pages | `page list`, `page new`, `page close`, `page switch` |
| Profiles | `profile list`, `profile delete` |
| States | `state save`, `state restore`, `state list` |
| Eval & Run | `eval`, `run` |

## Auto-start

The daemon starts automatically when you run any session command. You don't need to call `brow daemon start` manually.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Daemon failed to start |
| `2` | API error (details printed to stderr) |
