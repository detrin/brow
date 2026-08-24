# Run-enabled brow benchmark comparison

This is the valid, isolated rerun requested after exposing `brow_run` to the
benchmark agent. It used one run per task, no warmup, the 19 local fixture
tasks, AWS Bedrock model `us.anthropic.claude-sonnet-4-20250514-v1:0`, and a
dedicated brow daemon on port 21988.

The harness's `brow_version` field records Git HEAD `91d9086`. The benchmark
actually used the locally built 1.3.0 wheel containing the current uncommitted
hardening and benchmark-tool changes.

## Valid 19-task result

- Success: **18/19 (94.7%)**; only `deep-wizard` failed.
- Average tokens: **55,858 per task**.
- Average tool calls: **7.8 per task**.
- Average wall time: **41.2 seconds per task**.
- Estimated Bedrock cost: **$3.59**.
- `brow_run`: **25 calls across 11 tasks**, of which 16 calls succeeded.
- Session discipline: exactly **19 `brow_session_new` calls** for 19 tasks.

## Apples-to-apples comparison: original 16 fixtures

| Metric | 2026-04-04 brow run | Run-enabled rerun | Change |
|---|---:|---:|---:|
| Success | 13/16 (81.3%) | 15/16 (93.8%) | +2 tasks |
| Average tokens/task | 68,255 | 55,859 | -18.2% |
| Average tool calls/task | 9.6 | 7.9 | -17.5% |
| Average wall time/task | 41.3 s | 41.0 s | -0.6% |
| `brow_run` adoption | unavailable | 18 calls across 9 tasks | new |

The three additional fixture tasks (`paginated-news`, `price-comparison`, and
`tech-stack-graph`) all passed in the valid 19-task rerun.

## Invalid setup run

An earlier run in `../run-enabled-2026-08-24/` is retained for auditability but
is explicitly invalid: the matching Chromium binary was missing, and all
browser session starts returned HTTP 503. It incurred an estimated $1.67 before
the environment problem was diagnosed. Combined estimated Bedrock cost for the
invalid attempt and valid rerun is **$5.26**.

These are single-run results, so task-level variance remains high. The raw data
and generated report are `results.json` and `report.md` in this directory.
