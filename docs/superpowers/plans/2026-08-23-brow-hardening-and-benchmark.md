# Brow Hardening and Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden sensitive output, make replay and daemon configuration deterministic, modernize documentation dependencies, and benchmark the new reusable Python workflow.

**Architecture:** Keep brow's CLI-to-local-daemon architecture. Add validation and redaction at the daemon trust boundary, persist the chosen daemon port in `BROW_HOME`, use the standard PEP 440 parser, and adapt the existing benchmark subprocess bridge to materialize `brow_run` code as a temporary script.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic, Typer, Patchright, pytest, npm, Astro/Starlight, AWS Bedrock benchmark harness.

**Spec:** `docs/superpowers/specs/2026-08-23-brow-hardening-and-benchmark-design.md`

## Global Constraints

- Preserve existing user changes under `benchmarks/results/` and unrelated untracked files.
- Follow red-green-refactor for Python behavior changes.
- Do not log or serialize plaintext fill values.
- Write benchmark results to an isolated directory.

---

### Task 1: Sensitive-value redaction

**Files:**
- Modify: `brow/src/brow/routes/browser.py`
- Test: `brow/tests/test_routes_browser.py`

**Interfaces:**
- Consumes: `SNAPSHOT_JS`, `_log_action`, fill and replay routes.
- Produces: snapshots with no password value and fill action entries with no `value` field.

- [ ] Add browser-route tests proving password snapshots and direct/replay fill action logs contain no secret.
- [ ] Run focused tests and confirm they fail because secrets are currently present.
- [ ] Omit password values in `SNAPSHOT_JS` and stop passing fill values to `_log_action`.
- [ ] Run focused tests and confirm they pass.

### Task 2: Strict replay validation

**Files:**
- Modify: `brow/src/brow/routes/browser.py`
- Test: `brow/tests/test_routes_browser.py`

**Interfaces:**
- Consumes: `ReplayReq`, `_run_replay_steps`.
- Produces: `_validate_playbook(playbook: dict) -> None` and explicit runtime `for_each` errors.

- [ ] Add failing tests for unknown fields, missing required fields, invalid nested steps, undefined item sources, and non-list item values.
- [ ] Run the focused tests and confirm expected 422 or failed-step results.
- [ ] Implement recursive schema validation and strict `for_each` lookup/type handling.
- [ ] Run all replay tests.

### Task 3: Ports, versions, and warning-free tests

**Files:**
- Modify: `brow/src/brow/config.py`
- Modify: `brow/src/brow/cli.py`
- Modify: `brow/src/brow/daemon.py`
- Modify: `brow/src/brow/update_check.py`
- Modify: `brow/pyproject.toml`
- Test: `brow/tests/test_cli.py`
- Test: `brow/tests/test_config.py`
- Test: `brow/tests/test_update_check.py`
- Test: `brow/tests/test_routes_eval.py`

**Interfaces:**
- Produces: persisted daemon port selection and PEP 440 version parsing.

- [ ] Add failing tests for requested-port health checks, persistence, environment precedence, and rc/dev comparisons.
- [ ] Implement port storage and `packaging.version.Version` comparison.
- [ ] Remove resource-warning causes in tests without suppressing warnings globally.
- [ ] Run the full suite with warnings treated as errors.

### Task 4: Documentation dependency upgrade

**Files:**
- Modify mechanically: `website/package.json`
- Modify mechanically: `website/package-lock.json`

**Interfaces:**
- Produces: a deterministic Astro/Starlight build with no high/critical npm advisories.

- [ ] Query registry metadata for compatible current Astro/Starlight releases.
- [ ] Install explicit upgraded direct dependencies and refresh the lockfile.
- [ ] Run `npm run build` and `npm audit --audit-level=high`.

### Task 5: `brow_run` benchmark tool and rerun

**Files:**
- Modify: `benchmarks/harness/tools_brow.py`
- Create: `benchmarks/tests/test_tools_brow.py`
- Modify: `benchmarks/README.md` only if needed to document the new tool surface/result location.

**Interfaces:**
- Produces: `brow_run` tool schema with `session`, `code`, optional `args`, and optional `timeout`; secure temporary-file lifecycle in `execute_brow_tool`.

- [ ] Add tests proving schema exposure, command construction, argument forwarding, and temporary-file cleanup.
- [ ] Run tests and confirm failure before implementation.
- [ ] Implement the tool adapter and pass its focused tests.
- [ ] Run the brow fixture benchmark once with isolated output and preserve the result artifact.

### Task 6: Completion audit

**Files:**
- Verify all modified files and isolated benchmark artifacts.

**Interfaces:**
- Consumes every deliverable above.
- Produces completion evidence for each explicit user requirement.

- [ ] Run full pytest with warnings as errors, ruff, docs build/audit, Python package build, and isolated CLI smoke tests.
- [ ] Inspect git diff for scope, secrets, generated noise, and unrelated user changes.
- [ ] Confirm benchmark result coverage includes `brow_run` and report its location and outcome.
