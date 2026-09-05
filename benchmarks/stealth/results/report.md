# Stealth benchmark

Host: Darwin / `navigator.platform` should be `MacIntel` / timezone `CEST`

## Fingerprint checks

Deterministic: pure JS on a control page, no third-party detector involved.

| Check | brow | patchright | patchright-newheadless | agent-browser |
|---|---|---|---|---|
| navigator.webdriver absent | pass | pass | pass | **FAIL** |
| no automation globals | pass | pass | pass | pass |
| window.chrome present | pass | **FAIL** | pass | pass |
| chrome.runtime present | **FAIL** | **FAIL** | **FAIL** | **FAIL** |
| plugins non-empty | pass | **FAIL** | pass | pass |
| PDF viewer enabled | pass | **FAIL** | pass | pass |
| no 'Headless' in UA | pass | **FAIL** | **FAIL** | **FAIL** |
| client hints free of 'Headless' | pass | **FAIL** | pass | pass |
| window not larger than screen | pass | pass | pass | **FAIL** |
| hardware-accelerated WebGL | pass | **FAIL** | pass | pass |
| notification permission not denied | pass | **FAIL** | pass | pass |
| permissions API self-consistent | pass | **FAIL** | pass | pass |
| native function toString | pass | pass | pass | pass |
| stack traces clean | pass | pass | pass | pass |
| plausible core count | pass | pass | pass | pass |
| timezone matches host | pass | pass | pass | pass |
| platform matches host OS | pass | pass | pass | pass |
| **score** | **16/17** | **8/17** | **15/17** | **13/17** |

## Real sites

Live third-party sites. Informational, not a gate — these verdicts move on someone else's schedule.

| Site | brow | patchright | patchright-newheadless | agent-browser |
|---|---|---|---|---|
| `example` | through | through | through | through |
| `alza` | through | BLOCKED | BLOCKED | BLOCKED |
| `google-search` | through | BLOCKED | BLOCKED | BLOCKED |
| `sannysoft` | through | through | through | through |

- `example` — Control. A runner failing here is broken, not blocked.
- `alza` — Blocked agent-browser and let brow through in manual testing; the case that motivated this harness.
- `google-search` — Soft-blocks aggressively on automation signals.
- `sannysoft` — Reference detector page; read the per-signal table in the JSON output.

## Reading this

A failing check is a signal a detector can read for free; it is not proof of a block, and passing every
check is not proof of access. The fingerprint table is the regression test — run it after every
`patchright` bump. The site table is the outcome, and it is noisy by nature.
