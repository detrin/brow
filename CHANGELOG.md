# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `brow setup` command to install Chromium (no more manual `patchright install`)
- `session new --reclaim` closes a stale session holding the profile and takes it over (#31)
- `navigate --wait domcontentloaded|load|networkidle` settle strategy (#33)
- `eval` namespace helpers `text(sel)` and `texts(sel)` for quick extraction (#32)

### Changed
- License reverted to MIT (was Elastic License 2.0)
- `session new` returns a clear "Chromium is not installed" message instead of a raw 500 when the browser binary is missing
- click/fill/select accept a snapshot ref directly: `click "[1]"` resolves to `--ref 1` (#30)
- Profile-conflict error now suggests `--reclaim` and the exact `session delete` command (#31)
- `eval` errors involving an un-awaited coroutine now hint to add `await` (#32)

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
