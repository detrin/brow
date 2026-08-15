#!/usr/bin/env bash
# Deterministic microbenchmark: N near-identical `brow eval` calls driven from a
# shell loop vs one `brow run` call doing the same N-item loop server-side.
#
# No LLM involved — this isolates the process-spawn + HTTP round trip cost of
# "shell-loop calling brow" that AGENTS.md warns against, from actual task
# difficulty (which the benchmarks/ harness measures separately).
set -euo pipefail

N="${1:-30}"
SID=$(brow session new --profile "microbench-$$" | head -1)
trap 'brow session delete "$SID" >/dev/null 2>&1 || true' EXIT

items_html=$(python3 -c "print(''.join(f'<div id=i{i}>Item {i}</div>' for i in range($N)))")
brow navigate -s "$SID" "data:text/html,<body>${items_html}</body>" > /dev/null

echo "=== shell loop of $N \`brow eval\` calls ==="
loop_start=$(python3 -c "import time; print(time.time())")
for ((i = 0; i < N; i++)); do
  brow eval -s "$SID" "el = await page.query_selector('#i$i'); result = await el.inner_text()" > /dev/null
done
loop_end=$(python3 -c "import time; print(time.time())")
python3 -c "print(f'{$loop_end - $loop_start:.2f}s total, {($loop_end - $loop_start) / $N * 1000:.0f}ms/item')"

script=$(mktemp /tmp/microbench_workflow.XXXXXX.py)
python3 -c "
n = $N
print('items = {}')
print(f'for i in range({n}):')
print('    el = await page.query_selector(f\"#i{i}\")')
print('    items[i] = await el.inner_text()')
print('result = {\"count\": len(items)}')
" > "$script"

echo "=== single \`brow run\` call, $N items in one script ==="
run_start=$(python3 -c "import time; print(time.time())")
brow run -s "$SID" "$script" > /dev/null
run_end=$(python3 -c "import time; print(time.time())")
python3 -c "print(f'{$run_end - $run_start:.2f}s total')"
rm -f "$script"
