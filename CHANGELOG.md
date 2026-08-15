# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `run -s <id> <file.py> [--arg k=v]` — execute a reusable Python file once against the live session (same vars as `eval`, plus `args`), instead of shell-looping `eval`/CLI calls over a list. ~20x faster than a shell loop for 30 items (7.75s → 0.38s; see `benchmarks/microbench_run_vs_loop.sh`)
- `replay` playbooks gained `wait` (by selector/state, not just a fixed sleep), `assert` (fail a step when a condition doesn't hold), `for_each` (loop nested steps over a literal or captured list), and `headers` on `fetch` steps
- `stop_on_failure: true` playbook option halts remaining steps after the first failed one, including out of a nested `for_each`
- `setup --upgrade` bumps the `patchright` pip package and installs the Chromium build it now expects, and restarts a running daemon so it stops driving the old binary from memory. Previously there was no command for this — `brow setup` alone just re-fetched the build for whatever version was already pinned
- Update-available check: most commands now print a one-line `[brow] brow X.Y.Z is available ...` notice to stderr when a newer `brow-cli` is on PyPI, cached once a day (hourly retry on failure) so it almost never touches the network. Fails silently on any error and never blocks a command. Disable with `BROW_NO_UPDATE_CHECK=1`

### Fixed
- `fetch` steps' `output: name` now actually populates `{name}` (and `{name[key]}`) for later steps, as the playbook-writer docs always claimed — previously it was only recorded in the run's result log and never fed back into substitution
- `replay` CLI now exits nonzero when any step failed — previously it always exited 0 regardless of step outcomes
- `fetch` steps with an HTTP 4xx/5xx response are now marked as failed (`expect_status` opts out) — previously any response, including a 500, was reported `ok: true`
- An unknown playbook step `action` now reports a clear error instead of failing silently with no explanation
- `stop_on_failure` now actually halts a run when the failure is inside a `for_each` — previously it only stopped the current iteration's remaining steps, and later iterations and outer steps kept going
- A playbook-level `auth: none` is now inherited by `fetch` steps that don't set their own `auth` — previously only a per-step `auth` was ever checked
- `state restore` now restores localStorage in addition to cookies — previously it silently dropped the `origins` half of `storage_state()`, so a restored login failed for any site keeping its auth token in localStorage instead of a cookie
- `profile delete` now refuses (`409`) while a live session holds that profile, instead of deleting the on-disk directory out from under it
- Docs site: every internal cross-reference link used a relative `.md` path that Astro never resolves and rendered as a literal broken href in the built site (e.g. `href="daemon.md"`) — converted site-wide to the resolved `/brow/...` paths the sidebar itself uses

## [1.2.0] - 2026-08-15

### Added
- `brow setup` command to install Chromium (no more manual `patchright install`)
- `session new --reclaim` closes a stale session holding the profile and takes it over (#31)
- `navigate --wait domcontentloaded|load|networkidle` settle strategy (#33)
- `eval` namespace helpers `text(sel)` and `texts(sel)` for quick extraction (#32)
- `click-until` repeats a click until a selector clears or work runs out, for draining paginated lists/batch actions without a shell loop around `brow`

### Changed
- License reverted to MIT (was Elastic License 2.0)
- `session new` returns a clear "Chromium is not installed" message instead of a raw 500 when the browser binary is missing
- click/fill/select accept a snapshot ref directly: `click "[1]"` resolves to `--ref 1` (#30)
- Profile-conflict error now suggests `--reclaim` and the exact `session delete` command (#31)
- `eval` errors involving an un-awaited coroutine now hint to add `await` (#32)
- `page switch` now actually retargets later commands to the chosen tab instead of only changing which tab is visually focused
- `page new` no longer silently steals the active tab when one was deliberately chosen; `page list` marks the active tab with `*`
- `eval` timeout errors name `--timeout`, suggest a value, and return stdout printed before the cutoff instead of discarding it
- `fetch` prints the non-2xx status to stderr (stdout stays pipeable to jq), with a hint on 401/403

## [1.1.0] - 2026-04-08

### Added
- 6 new benchmark tasks (3 fixture + 3 live)
- Astro Starlight documentation site with full CLI, API, and tutorial pages
- GitHub Actions workflow for docs deployment
- Benchmarks for all 5 backends on new tasks

### Changed
- Migrated docs from MkDocs to Astro Starlight
- Normalized benchmark README into single coherent document

### Fixed
- Docs deploy trigger (main branch, not master)
- Regenerated package-lock.json for CI compatibility

## [1.0.3] - 2026-03-28

### Fixed
- Surface API errors in CLI output
- `fill --ref` argument parsing
- `daemon start --wait` flag

## [1.0.1] - 2026-03-27

### Fixed
- Handle SNAPSHOT_JS crashes on complex DOMs (e.g. GitHub)

## [1.0.0] - 2026-03-27

### Added
- Ref-based element addressing (`--ref` for click, fill, select)
- Auto-snapshot on mutation endpoints (click, fill, type, key, select)
- Combined session create with navigate and snapshot
- Table detection and compact markdown rendering in snapshots
- Inline list compression with pipe separators
- Adaptive node cap based on interactive element density
- Parallel tool execution in benchmark agent loop
- agent-browser and browser-use as benchmark backends
- Per-task success grid and token cost tables

### Changed
- Benchmark suite expanded to 16 fixture tasks + live tasks
- Snapshot format: tables render as markdown, lists compress inline

## [0.1.3] - 2026-03-20

### Added
- Screenshot resolution control
- Reliable click/fill with retry logic

### Changed
- Require Python 3.12+ (dropped 3.11)

## [0.1.2] - 2026-03-18

### Added
- Agent skill installation via `npx -y skills add`
- Release process documentation

## [0.1.1] - 2026-03-17

### Fixed
- Add readme, license, and author to pyproject.toml for PyPI

## [0.1.0] - 2026-03-16

### Added
- Initial release
- FastAPI daemon with session management
- CLI commands: navigate, snapshot, screenshot, click, fill, type, key, hover, scroll, eval
- Persistent browser profiles
- State save/restore
- Multi-page/tab support
- Headless and headed modes
- Docker support with Xvfb
- Benchmark harness with 10 tasks
- PyPI and Homebrew distribution
