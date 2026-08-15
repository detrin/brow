---
title: Getting Started
description: Install brow and run your first browser session
---

## Installation

Install the Python package and the Chromium browser:

```bash
pip install brow-cli
brow setup
```

Verify the installation:

```bash
brow --help
```

### Updating

`pip install --upgrade brow-cli` updates the CLI itself. To pick up a newer
`patchright` and the Chromium build it drives:

```bash
brow setup --upgrade
```

This upgrades the `patchright` pip package first, then installs the
Chromium build that new version expects — running `brow setup` again on its
own would just re-fetch the build for whatever version was already pinned,
not actually upgrade anything. It also stops a running daemon, since it
already imported the old `patchright` in memory and won't pick up the
upgrade until it restarts.

## Configuration

brow reads a small set of environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `BROW_HOME` | `~/.brow` | Data directory (profiles, states, screenshots) |
| `BROW_PORT` | `19987` | Daemon HTTP port |
| `BROW_MAX_SESSIONS` | `10` | Maximum concurrent browser sessions |

## Your first session

### Headless (default)

```bash
brow session new          # → 1
brow navigate -s 1 "https://example.com"
brow snapshot -s 1
brow session delete 1
```

### Headed (visible browser)

Add `--headed` to see the Chromium window. Useful for debugging and for sites that block headless browsers:

```bash
brow session new --headed
brow navigate -s 1 "https://example.com"
brow session delete 1
```

## The daemon

brow runs a local FastAPI daemon on port `19987`. It starts automatically on the first command that needs it — you never have to start it manually.

```bash
brow daemon status          # check if running
brow daemon stop            # stop it
brow daemon start --wait    # start and block until ready
```

The daemon survives individual CLI invocations. Sessions you create persist until you delete them or stop the daemon.

## Selectors

brow uses Playwright's selector syntax. The most useful forms:

| Selector | Example |
|----------|---------|
| CSS | `#submit`, `button.primary`, `input[type="email"]` |
| Text | `text=Sign In` |
| Role | `role=button[name="Save"]` |
| Ref (from snapshot) | `--ref 15` |

The `snapshot` command annotates interactive elements with a numeric `ref`. You can use `--ref N` instead of a selector for any click/fill/select command.

## Persistent profiles

Log in once, reuse forever. See the [Persistent Login tutorial](/brow/tutorials/persistent-login/) for a complete walkthrough.
