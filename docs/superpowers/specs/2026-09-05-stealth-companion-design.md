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

### As built: deviations

**We own the probe; we do not scrape third-party detectors.** The design said
"scrape verdict cells into per-signal pass/fail" from bot.sannysoft, CreepJS and
browserleaks. Rejected during implementation: scraping someone else's DOM fails
*silently*. They restyle, the scrape returns nothing, and every runner looks
perfect. `benchmarks/stealth/probe.js` is one JS function we control, scored
against 17 signals in `signals.py`, each with a recorded reason. sannysoft stays,
demoted to the real-sites list where it belongs.

That decision immediately paid for itself, and proved the danger was real rather
than theoretical. The first run reported `agent-browser` at **0/15** — every
check failing, including host-independent ones. It was not stealth data: its
`--json eval` needs the probe function *invoked*, not passed, so it returned
nothing and every check "failed" on `None`. A transport bug read exactly like a
perfect detection result. `signals.unusable()` now refuses to score a probe that
didn't come back with real values — such a runner is reported under **Errors** —
and `Runner.fn_forms` retries the invoked form. agent-browser's real score is
13/17. The same bug was silently erroring its live-site column too.

**Correction to the premise this project started from.** The claim was that brow
"measurably wins" on stealth. Measured, brow started at **7/17** and
agent-browser at 13/17: on fingerprint signals brow was *losing*, and the real
Alza result was carried by `navigator.webdriver` alone. The premise was right
about the outcome and wrong about the margin.

## 3. Deepen stealth

Nothing ships here without the harness showing it moved a number.

### As built

**The lever was one line.** `headless=True` alone runs `chrome-headless-shell`:
no GPU, no plugins, no PDF viewer, no `window.chrome` — six failing signals from
one cause. `channel="chromium"` runs the full build in Chrome's new headless mode
instead. Measured on plain patchright: **7/15 → 13/15**.

**Then the UA.** New headless still self-identifies as `HeadlessChrome/151` in
the UA string, while its client-hint brands say plain `Chromium` — so sanitising
the string *removes* a contradiction rather than creating one. `brow/stealth.py`
derives the major version from the browser binary and builds Chrome's frozen
reduced-UA string for the host OS, applied only when headless. Combined: brow
**16/17**, ahead of patchright-newheadless (15) and agent-browser (13).

This is what moved the real-site column, not just the table: plain patchright and
patchright-newheadless are both `BLOCKED` on Alza and Google search; brow is
`through` on all four sites. It reproduces, from a clean harness, the manual
observation this project started from.

Launch failures fall back to a channel-less launch — a machine without the full
build should get a noisier browser, not no browser.

**Launch-args audit: done, and the answer is they buy nothing.**
`patchright-bare` (no `--disable-blink-features=AutomationControlled`, no
`ignore_default_args`) scores identically to `patchright`. Kept because they cost
nothing, not because they earn anything. That column exists to keep the finding
honest rather than to flatter the config.

**Human-like input: deliberately not shipped.** Dwell, micro-movement and
variable `type` delay are unmeasurable by this harness — it probes fingerprint
surface, not behaviour. Shipping them would violate this section's own gate, so
the gate wins. Recorded as a known gap in `benchmarks/stealth/README.md`.

**`chrome.runtime` is unresolved.** brow fails it; so does every runner measured,
agent-browser included. Getting it means injecting JS — which is precisely what
patchright declines to do, and a patched built-in is a louder signal than the one
it hides — or shipping a real extension. Left failing, and documented.

## 4. Reposition the docs

`README.md` and `SKILL.md` reframed from feature list to *your browser, your
logins, your machine*. Lead with the workstream-2 table; show the workstream-1
commands.

`SKILL.md`'s five-rule session preamble mostly deletes itself once workstream 1
lands. That it does is the clearest evidence workstream 1 was the right first
move.

### As built

The session preamble did collapse, as predicted: three of its five rules
(`--reclaim` always, the profile-collision dance, never invent an id) stop
applying to the default path, replaced by "leave `-s` out". What replaced them is
guidance the old docs lacked — when to *not* use the default profile, and how to
hand a login to the user via `brow login` instead of typing their credentials.

Two fixes outside the stated scope, both in files being rewritten anyway: the
README's command reference documented the pre-1.0 `brow -s <id> navigate <url>`
argument order, which has been wrong since the CLI became subcommand-first; and
it still told users to sign in via `session new --headed` + `navigate` + `session
delete`, which `brow login` replaces in one line.

**Acting as you by default.** A bare command uses your real logins. Intended,
but it means any unattended agent run touches your cookies unless it passes
`--profile`. Docs must lead with this.

**Breaking change.** The bare default profile changes from `default` to
`personal`. Scripts that relied on the bare default being anonymous will now
carry your identity. Called out in `CHANGELOG.md` as breaking.

**Auto-create hides state.** A typo'd URL silently launches a browser. Mitigated
by keeping auto-start headless and cheap, and by `session list` remaining the
source of truth.

**`channel="chromium"` assumes the full build is installed.** `brow setup`
installs it, but a machine with only `chrome-headless-shell` would fail to launch.
Mitigated by falling back to a channel-less launch, covered by
`test_launch_falls_back_when_the_full_build_is_missing`. A failure unrelated to
the channel is re-raised rather than swallowed.

**The UA override is constructed, not observed.** `UA_PLATFORM` hard-codes
Chrome's reduced-UA platform tokens for Darwin/Windows/Linux. They are frozen by
the UA-reduction spec, but an unknown `platform.system()` or an unparseable
`--version` skips the override rather than guessing — one failing check beats an
incoherent fingerprint.
