## Benchmark Results (us.anthropic.claude-sonnet-4-20250514-v1:0, 1 runs per task)

### Summary
| Metric | brow | mcp-playwright | playwright-cli | agent-browser | Delta |
|--------|--------|--------|--------|--------|-------|
| Avg tokens/task | 139949+/-136236 | 170096+/-227811 | 51262+/-70117 | 57731+/-43464 |  |
| Avg tool calls/task | 10.5+/-5.9 | 14.5+/-7.1 | 5.3+/-4.9 | 10.2+/-7.5 |  |
| Success rate | 83% | 17% | 83% | 83% |  |
| Avg wall-clock (s) | 57.3+/-50.2 | 57.4+/-34.4 | 38.0+/-33.4 | 35.8+/-25.9 |  |
| Est. cost/task | $0.4453 | $0.5268 | $0.1635 | $0.1856 |  |

### Per-Task Breakdown
| Task | Backend | Tokens | Calls | Success | Time (s) |
|------|---------|--------|-------|---------|----------|
| github-trending-python | agent-browser | 9902+/-0 | 3.0+/-0.0 | 1/1 | 14.4+/-0.0 |
| github-trending-python | brow | 383096+/-0 | 11.0+/-0.0 | 1/1 | 57.2+/-0.0 |
| github-trending-python | mcp-playwright | 12813+/-0 | 3.0+/-0.0 | 1/1 | 48.8+/-0.0 |
| github-trending-python | playwright-cli | 11130+/-0 | 2.0+/-0.0 | 1/1 | 12.5+/-0.0 |
| hacker-news-ask | agent-browser | 76884+/-0 | 5.0+/-0.0 | 1/1 | 24.3+/-0.0 |
| hacker-news-ask | brow | 54866+/-0 | 6.0+/-0.0 | 1/1 | 27.9+/-0.0 |
| hacker-news-ask | mcp-playwright | 626068+/-0 | 9.0+/-0.0 | 0/1 | 127.1+/-0.0 |
| hacker-news-ask | playwright-cli | 1580+/-0 | 1.0+/-0.0 | 0/1 | 101.1+/-0.0 |
| npm-http-clients | agent-browser | 61618+/-0 | 20.0+/-0.0 | 0/1 | 78.1+/-0.0 |
| npm-http-clients | brow | 168282+/-0 | 20.0+/-0.0 | 0/1 | 154.2+/-0.0 |
| npm-http-clients | mcp-playwright | 51625+/-0 | 20.0+/-0.0 | 0/1 | 41.6+/-0.0 |
| npm-http-clients | playwright-cli | 179350+/-0 | 14.0+/-0.0 | 1/1 | 41.6+/-0.0 |
| paginated-news | agent-browser | 58162+/-0 | 9.0+/-0.0 | 1/1 | 26.7+/-0.0 |
| paginated-news | brow | 16356+/-0 | 4.0+/-0.0 | 1/1 | 12.9+/-0.0 |
| paginated-news | mcp-playwright | 145694+/-0 | 20.0+/-0.0 | 0/1 | 46.4+/-0.0 |
| paginated-news | playwright-cli | 19427+/-0 | 4.0+/-0.0 | 1/1 | 21.5+/-0.0 |
| price-comparison | agent-browser | 12994+/-0 | 5.0+/-0.0 | 1/1 | 14.7+/-0.0 |
| price-comparison | brow | 43774+/-0 | 8.0+/-0.0 | 1/1 | 38.4+/-0.0 |
| price-comparison | mcp-playwright | 86215+/-0 | 15.0+/-0.0 | 0/1 | 37.3+/-0.0 |
| price-comparison | playwright-cli | 8913+/-0 | 3.0+/-0.0 | 1/1 | 12.6+/-0.0 |
| tech-stack-graph | agent-browser | 126828+/-0 | 19.0+/-0.0 | 1/1 | 56.8+/-0.0 |
| tech-stack-graph | brow | 173318+/-0 | 14.0+/-0.0 | 1/1 | 53.5+/-0.0 |
| tech-stack-graph | mcp-playwright | 98161+/-0 | 20.0+/-0.0 | 0/1 | 43.0+/-0.0 |
| tech-stack-graph | playwright-cli | 87169+/-0 | 8.0+/-0.0 | 1/1 | 38.6+/-0.0 |
