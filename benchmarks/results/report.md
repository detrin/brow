## Benchmark Results — brow (optimized) vs playwright-cli

**Model:** us.anthropic.claude-sonnet-4-20250514-v1:0 | **Runs:** 1 per task

### Summary

| Metric | brow (optimized) | playwright-cli | Delta |
|--------|-----------------|----------------|-------|
| Avg tokens/task | 49,646 | 45,929 | +8% |
| Avg tool calls/task | 10.4 | 8.9 | +17% |
| Avg wall-clock (s) | 46.1 | 31.5 | +46% |
| Est. cost/task | $0.16 | $0.15 | +7% |
| Tasks with correct output | 7/10 | 6/10 | +1 |

### Per-Task Comparison

| Task | brow tokens | pwcli tokens | Δ tokens | brow calls | pwcli calls | brow time | pwcli time |
|------|-------------|--------------|----------|------------|-------------|-----------|------------|
| dynamic-content | 29,640 | 31,954 | **-7%** | 10 | 12 | 33.4s | 40.4s |
| ecommerce-search | 19,206 | 53,292 | **-64%** | 6 | 12 | 22.8s | 45.7s |
| error-recovery | 51,630 | 12,699 | +307% | 16 | 6 | 44.0s | 14.9s |
| form-fill | 33,028 | 16,002 | +106% | 11 | 7 | 40.8s | 33.8s |
| info-lookup | 16,612 | 5,948 | +179% | 6 | 3 | 16.7s | 9.3s |
| large-snapshot | 142,170 | 217,162 | **-35%** | 10 | 10 | 40.4s | 45.6s |
| login-auth | 69,995 | 72,009 | **-3%** | 20 | 20 | 96.1s | 61.1s |
| multi-page-nav | 23,543 | 8,830 | +167% | 8 | 4 | 19.7s | 13.9s |
| rapid-multi-step | 99,919 | 34,707 | +188% | 13 | 12 | 131.3s | 40.9s |
| search-extract | 10,716 | 6,691 | +60% | 4 | 3 | 16.0s | 9.4s |
| **TOTAL** | **496,459** | **459,294** | **+8%** | **104** | **89** | | |

### Key Findings

**brow wins on large/complex pages:**
- `large-snapshot`: -35% tokens (142K vs 217K) — tree pruning + repetition dedup
- `ecommerce-search`: -64% tokens (19K vs 53K) — compact snapshot format
- `dynamic-content`: -7% tokens — fewer decorative nodes

**playwright-cli wins on simple pages:**
- `info-lookup`: +179% — brow uses more tool calls per navigation
- `multi-page-nav`: +167% — extra session setup overhead
- `rapid-multi-step`: +188% — multi-step wizard needs more interaction

**Optimizations applied to brow:**
1. JS tree pruning: skip hidden, script, style, svg; collapse decorative containers
2. Repetition dedup: show first 3 repeated siblings, omit rest with count
3. Node count cap (300): prevents huge snapshots
4. Truncation hints: tells agent to use `search=` param for large pages
5. Message history compression: old tool results >500 chars get summarized
6. Async tool execution: fixed event loop blocking that caused navigate timeouts
