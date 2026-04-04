---
title: Daemon
description: Managing the brow background daemon
---

The brow daemon is a local FastAPI process that manages browser sessions. It starts automatically on the first command that needs it, but you can also control it directly.

## `brow daemon start`

Start the daemon in the background.

```
brow daemon start [--port <port>] [--wait]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | `19987` | Port to listen on |
| `--wait` | `false` | Block until daemon is ready |

Without `--wait`, the command returns immediately and the daemon continues starting in the background. With `--wait`, it polls until the daemon responds to `/status` (up to 15 seconds).

```bash
brow daemon start --wait
# Daemon ready on 127.0.0.1:19987
```

## `brow daemon stop`

Stop the running daemon. All active sessions are closed.

```bash
brow daemon stop
# Daemon stopped
```

## `brow daemon status`

Check if the daemon is running and how many sessions are active.

```bash
brow daemon status
# Running — 2 active sessions
```

## Notes

- The daemon binds to `127.0.0.1` (localhost only) — it's not accessible from outside the machine.
- PID is stored in `~/.brow/daemon.pid`.
- If the daemon crashes, the next CLI command will attempt to restart it automatically.
