# Stealth companion: the browser you're already logged into

**Date:** 2026-09-05
**Status:** approved

## Why

brow competes with browser-use, Vercel agent-browser and Playwright MCP on
breadth and loses: they have funded teams and more integrations. It competes on
stealth and persistent identity and wins. Measured this session: agent-browser
was blocked by Alza where brow got through, and a hand-performed Gmail login
survived across brow sessions.

So stop widening and go deep on the axis that already wins. But two things make
"deep on stealth" the wrong framing on its own:

**Stealth is borrowed.** brow's stealth is patchright's stealth, one
`pip install` away for anyone. Stealth alone is not defensible.

**The defensible thing is the combination:** a real Chromium profile you are
already signed into, on your own machine, plus token-cheap snapshots.
agent-browser and Playwright MCP are built around ephemeral cloud/CDP sessions;
"the browser where you're already logged into Gmail" is not a feature they can
bolt on.

And the combination is currently unreachable, because the daily path is broken:

```
$ brow navigate "https://example.com"
Error (404): Session None not found
```

`s` defaults to `None` and is interpolated straight into the request path, so
the user is shown a leaked Python `None`. `SKILL.md` needs five numbered rules
to explain how to obtain a session at all.

The receipt for how badly this steers people is on disk:

```
262 profiles, 8.6 GB in ~/.brow/profiles
  personal          1.9 G   <- the actual product
  default           1.5 G
  gmail-personal     14 M
  ...259 others:  fp_54376_1247, state-fresh5-8409, audit-5954, train34, ...
```

259 of those are throwaway one-shot profiles. The current design pushes people
toward disposable browsers. The companion product already exists — it is the
`personal` directory — buried in litter with no way to tell which is which.

## Scope

Four workstreams, in this order. The order is forced: each one makes the next
honest.

1. **Zero-friction daily use.** Without this, everything else advertises a
   promise the first command breaks.
2. **Stealth benchmark harness.** Without this, workstream 3 is vibes.
3. **Deepen stealth.** Gated on 2 showing movement.
4. **Reposition the docs.** Last, because shipping it earlier would be a lie.

## 1. Zero-friction daily use

### The implicit session

One rule, applied whenever `-s` is absent: *the implicit session is the one
holding your default profile; create it if it isn't there.*

```
brow navigate mail.google.com   # resolves, auto-starts if needed
brow snapshot                   # same session
brow click "[3]"                # same session

brow session new --profile x    # -> 2; extra browsers stay explicit
brow snapshot -s 2
```

The default profile becomes `personal` (was `default`), overridable by
`BROW_PROFILE`. An explicit `--profile` still wins.

**Decision: `personal`, not a clean profile.** A bare `brow navigate` acting as
you, with your real cookies, *is* the product. The cost is a footgun for
unattended agent runs, addressed by documentation prominence rather than by
weakening the default.

### Where resolution lives

In `call()`. Paths become templates:

```python
call("post", "/browser/{sid}/navigate", json={...})
```

One resolution site that a call site cannot forget. The alternative — a `sid(s)`
helper threaded through ~40 commands — is the same edit 40 times and one
omission from a bug.

### Cost

Naively this costs a `GET /sessions` per command. Instead the resolved id is
cached in `~/.brow/current`; on a `Session N not found` 404 the cache is
invalidated and resolution retried **once** before failing. Common path stays at
one request, and a stale pointer self-heals rather than erroring.

`Session None not found` becomes unreachable: there is no longer a code path
where `sid` is unset.

### Interactive login

Auto-start stays headless — a window opening on every scripted command is worse
than the status quo. The case that matters, an expired session, gets one verb:

```
brow login [url]
```

Opens the default profile headed and waits for the user to finish.

### Profile GC

```
brow profile prune [--days N] [--yes]
```

mtime-based last-use, sizes shown, `--dry-run` semantics by default: it refuses
to delete without `--yes`. Never touches `personal`, `default`, or any profile a
live session holds. This deletes gigabytes, so it gets the paranoid treatment.

## 2. Stealth benchmark harness

`benchmarks/stealth/`. Runners x targets.

**Runners:** brow, raw patchright, raw Playwright, agent-browser.

**Synthetic targets** — scrape verdict cells into per-signal pass/fail:
bot.sannysoft.com, CreepJS, browserleaks canvas/WebRTC. Signals include
`navigator.webdriver`, CDP artifacts, `window.chrome`, plugins, WebGL vendor.

**Real-world targets** — binary got-through/blocked: a Cloudflare-challenged
page, Alza (known to block agent-browser), Google search.

**Output:** markdown table plus JSON, matching the existing benchmark shape.

**Not a CI gate.** These are live third-party sites; a red build caused by
someone else's WAF tuning is noise. Scheduled and informational instead.

The point is not the marketing table. It is that a `patchright` bump becomes
verifiable instead of an act of faith.

## 3. Deepen stealth

Nothing ships here without the harness showing it moved a number.

- **Fingerprint coherence with the real host** — UA, platform, locale, timezone,
  screen. Mismatch is a stronger tell than `navigator.webdriver` and is cheap to
  fix.
- **Human-like input** — dwell and micro-movement on click, variable delay in
  `type`. Both code paths are ours.
- **Launch-args audit** — the current list (`--disable-blink-features=
  AutomationControlled`, dropping `--enable-automation`) has not been revisited
  since it was written.

## 4. Reposition the docs

`README.md` and `SKILL.md` reframed from feature list to *your browser, your
logins, your machine*. Lead with the workstream-2 table; show the workstream-1
commands.

`SKILL.md`'s five-rule session preamble mostly deletes itself once workstream 1
lands. That it does is the clearest evidence workstream 1 was the right first
move.

## Risks

**Acting as you by default.** A bare command uses your real logins. Intended,
but it means any unattended agent run touches your cookies unless it passes
`--profile`. Docs must lead with this.

**Breaking change.** The bare default profile changes from `default` to
`personal`. Scripts that relied on the bare default being anonymous will now
carry your identity. Called out in `CHANGELOG.md` as breaking.

**Auto-create hides state.** A typo'd URL silently launches a browser. Mitigated
by keeping auto-start headless and cheap, and by `session list` remaining the
source of truth.
