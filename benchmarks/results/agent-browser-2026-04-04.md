## Benchmark Results (us.anthropic.claude-sonnet-4-20250514-v1:0, 1 runs per task)

### Summary
| Metric | agent-browser | Delta |
|--------|--------|-------|
| Avg tokens/task | 73156+/-99344 |  |
| Avg tool calls/task | 11.2+/-5.8 |  |
| Success rate | 56% |  |
| Avg wall-clock (s) | 35.6+/-18.9 |  |
| Est. cost/task | $0.2320 |  |

### Per-Task Breakdown
| Task | Backend | Tokens | Calls | Success | Time (s) |
|------|---------|--------|-------|---------|----------|
| data-table-extract | agent-browser | 295975+/-0 | 9.0+/-0.0 | 0/1 | 39.8+/-0.0 |
| deep-wizard | agent-browser | 79238+/-0 | 25.0+/-0.0 | 0/1 | 89.8+/-0.0 |
| dynamic-content | agent-browser | 5239+/-0 | 3.0+/-0.0 | 0/1 | 9.2+/-0.0 |
| ecommerce-search | agent-browser | 38230+/-0 | 9.0+/-0.0 | 1/1 | 27.2+/-0.0 |
| error-recovery | agent-browser | 16495+/-0 | 8.0+/-0.0 | 1/1 | 22.5+/-0.0 |
| form-fill | agent-browser | 19632+/-0 | 9.0+/-0.0 | 0/1 | 20.1+/-0.0 |
| form-validation-recovery | agent-browser | 41677+/-0 | 13.0+/-0.0 | 1/1 | 39.5+/-0.0 |
| infinite-scroll | agent-browser | 88090+/-0 | 14.0+/-0.0 | 1/1 | 42.2+/-0.0 |
| info-lookup | agent-browser | 11298+/-0 | 6.0+/-0.0 | 1/1 | 13.0+/-0.0 |
| large-snapshot | agent-browser | 340559+/-0 | 7.0+/-0.0 | 1/1 | 34.9+/-0.0 |
| login-auth | agent-browser | 55250+/-0 | 20.0+/-0.0 | 0/1 | 50.3+/-0.0 |
| multi-page-nav | agent-browser | 17046+/-0 | 8.0+/-0.0 | 1/1 | 19.9+/-0.0 |
| multi-tab-workflow | agent-browser | 29067+/-0 | 11.0+/-0.0 | 1/1 | 34.0+/-0.0 |
| rapid-multi-step | agent-browser | 44519+/-0 | 17.0+/-0.0 | 1/1 | 37.8+/-0.0 |
| search-extract | agent-browser | 12642+/-0 | 5.0+/-0.0 | 0/1 | 48.4+/-0.0 |
| spa-navigation | agent-browser | 75544+/-0 | 15.0+/-0.0 | 0/1 | 40.8+/-0.0 |
