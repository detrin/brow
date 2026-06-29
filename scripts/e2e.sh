#!/usr/bin/env bash
set -euo pipefail

export BROW_HOME="${BROW_HOME:-$(mktemp -d)/.brow}"
export BROW_PORT="${BROW_PORT:-29871}"
PAGE='data:text/html,<title>brow e2e</title><body><h1>hello brow</h1><button id=go>Go</button></body>'

cleanup() { brow session delete 1 2>/dev/null || true; brow daemon stop 2>/dev/null || true; }
trap cleanup EXIT
cleanup

assert() { echo "$1" | grep -qF "$2" || { echo "FAIL: expected '$2' in:"; echo "$1"; exit 1; }; }

echo "==> brow setup"
brow setup ${BROW_SETUP_ARGS:-}

echo "==> session new"
assert "$(brow session new --url "$PAGE")" "hello brow"

echo "==> url"
assert "$(brow url -s 1)" "brow e2e"

echo "==> snapshot"
assert "$(brow snapshot -s 1)" "Go"

echo "==> eval"
assert "$(brow eval -s 1 'result = await page.title()')" "brow e2e"

echo "==> click"
brow click -s 1 "#go"

echo "PASS: e2e ok ($(brow --version 2>/dev/null || echo brow))"
