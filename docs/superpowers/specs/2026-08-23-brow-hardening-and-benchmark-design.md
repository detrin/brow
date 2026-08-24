# Brow Hardening and Benchmark Design

## Scope

This design implements the approved post-audit work:

- Prevent passwords and sensitive fill values from entering snapshots or action logs.
- Upgrade the documentation dependency tree until the build passes without known high-severity advisories.
- Fix custom daemon ports, test warnings, replay validation, and pre-release version comparison.
- Add `brow_run` to the agent benchmark tool surface and run the fixture benchmark into an isolated result directory.

## Behavior

Password inputs never expose their value in a snapshot. Action logs retain the fact that a fill occurred and its selector, but omit every fill value; this protects passwords, tokens, personal data, and future sensitive fields without unreliable name heuristics.

Replay requests are validated before any browser action runs. The validator rejects unknown playbook fields, unknown step fields, missing required fields, invalid states/auth/status declarations, malformed nested steps, and `for_each` references that are undefined or do not resolve to a list at runtime. Validation errors identify the step path.

`brow daemon start --port N` stores `N` under the active `BROW_HOME`. Later CLI processes use that stored port unless `BROW_PORT` explicitly overrides it. The `--wait` probe checks the actual requested port.

Update checks compare versions with `packaging.version.Version`, including development and release-candidate versions. CLI tests use inert client calls when `run_async` is mocked, and the un-awaited-coroutine hint test closes the deliberately created coroutine.

The benchmark harness exposes `brow_run(session, code, args, timeout)`. It writes code to a secure temporary `.py` file, invokes `brow run` once, then removes the file. Benchmark output is written outside existing tracked/user result files.

## Security Boundaries

- No fill value is retained in action state.
- Password values are omitted, not replaced with a reversible representation.
- Temporary benchmark scripts use owner-only temporary files and guaranteed cleanup.
- Profile/state path and daemon-auth hardening remain outside this user-selected scope.

## Verification

- Focused tests must fail before each Python behavior change and pass afterward.
- Full Python tests must pass without warnings.
- Ruff check and format verification must pass.
- The documentation build must pass and `npm audit` must report zero high/critical findings.
- Wheel and source distribution builds must pass.
- An isolated CLI smoke test must prove redaction, custom-port persistence, replay rejection, and `brow run` execution.
- The reproducible brow fixture benchmark must run with `brow_run` present in the tool schema; results must not overwrite existing benchmark files.
