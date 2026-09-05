# Stealth benchmark

Measures how automated a browser looks. Two halves, deliberately separate:

- **Fingerprint checks** — one pure-JS probe on a control page, scored against 17 signals a
  detector can read for free. Deterministic and offline-ish: same browser, same score. This is
  the regression test.
- **Real sites** — four live sites, classified `through` / `blocked` / `error`. This is the
  outcome that matters, and it moves on someone else's schedule. Informational, never a gate.

## Running it

```bash
python -m benchmarks.stealth                                   # fingerprint only, default runners
python -m benchmarks.stealth --sites                           # add the live-site table (slow)
python -m benchmarks.stealth --runners brow,agent-browser      # pick runners
python -m benchmarks.stealth --output /tmp/experiment          # write elsewhere
```

Writes `report.md` and `results.json` to `benchmarks/stealth/results/`. The JSON keeps the full
raw probe for every runner — read it when a check surprises you, because the score is a summary
and the probe is the evidence.

`brow` needs a running daemon (`brow daemon start --wait`). Runners that can't start are listed
under **Not measured** with the reason; they are never silently scored.

## Runners

| Runner | What it is |
|---|---|
| `brow` | This project, over its HTTP API — the thing under test |
| `patchright` | Plain `patchright` with `headless=True`, i.e. the default anyone gets |
| `patchright-bare` | Same, minus brow's launch args — shows what those args are worth |
| `patchright-newheadless` | `channel="chromium"`, isolating the single biggest lever |
| `patchright-chrome` | `channel="chrome"`, needs real Chrome installed |
| `playwright` | Upstream Playwright, as the no-stealth floor |
| `agent-browser` | Vercel's CLI, via `agent-browser --json` |

## Current results

Scores from the committed `results/report.md`. brow 16/17, `patchright-newheadless` 15/17,
`agent-browser` 13/17, plain `patchright` 8/17 — and on live sites brow is the only runner
through both Alza and Google search.

Two things that table is worth reading carefully for:

- **Plain `patchright` scoring 8/17 is the point.** `headless=True` on its own runs
  `chrome-headless-shell`: no GPU, no plugins, no PDF viewer, no `window.chrome`. Six checks
  fail for one reason. brow sets `channel="chromium"` to get Chrome's new headless mode instead.
- **`patchright-bare` scoring the same as `patchright` is also the point.** brow's
  `--disable-blink-features=AutomationControlled` and `ignore_default_args` buy nothing
  measurable. They are kept because they cost nothing, not because they earn anything.

## Known gaps

Recorded here rather than quietly excluded, because a benchmark you tune until you win is not a
benchmark:

- **`chrome.runtime` — brow fails it, and so does every runner measured, agent-browser
  included.** Real desktop Chrome exposes it; getting it means either injecting JS (which is
  what patchright deliberately does not do, and a patched built-in is a louder signal than the
  one it hides) or shipping a real extension. Unresolved on purpose.
- **`userAgentData.brands` says `Chromium`, not `Google Chrome`.** Coherent with itself and
  free of `Headless`, so it passes, but a detector comparing brands against the UA string can
  still tell this is not retail Chrome. `channel="chrome"` fixes it and needs Chrome installed.
- **`screen` equals the window size.** It passes "window not larger than screen", but a real
  display is bigger than the window on it. A stricter check would fail brow too.
- **Nothing here measures behaviour.** Timing, mouse paths and typing cadence are unmeasured,
  so no humanised-input work has shipped — there would be no way to tell whether it helped.

## Adding a check

Append a `(name, test, why)` tuple to `CHECKS` in `signals.py`. `test` receives the raw probe
dict. The `why` is not decoration — a check nobody can justify gets gamed instead of fixed.

Add the signal to `probe.js` first if it isn't captured yet, and add both to
`benchmarks/tests/test_stealth_harness.py`: one case proving a clean browser passes, one proving
a dirty value fails.

## Why the probe is ours and not bot.sannysoft.com

An earlier version scraped a third-party detector's DOM. That breaks silently — the page
restyles, the scrape returns nothing, and every runner looks perfect. A probe we own fails
loudly instead, which is why `signals.unusable()` exists: if the probe did not come back with
real values, the runner is reported under **Errors** rather than scored.

That guard is load-bearing. The first run of this harness reported `agent-browser` at 0/15 —
its `--json eval` needs the probe function *invoked*, not passed, so it returned nothing and
every check "failed". A transport bug read exactly like perfect stealth detection. It is now
13/17, and `fn_forms` retries the invoked form.
