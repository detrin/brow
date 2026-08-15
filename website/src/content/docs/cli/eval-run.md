---
title: Eval & Run
description: Running Python against the live session, inline or from a file
---

Both commands execute Python in the same sandbox — `page`, `context`,
`browser`, `state`, `pages` — against the live, already-navigated,
already-authenticated session. `eval` is for a one-off inline snippet; `run`
is for anything with a loop or a condition, written once as a file and reused.

## `brow eval`

```
brow eval -s <id> <code> [--timeout <ms>]
```

```bash
brow eval -s 1 "result = await page.title()"
brow eval -s 1 "print(await page.url())"
```

`result` is whatever you assign to a variable named `result` — there's no
implicit "last expression" return like a REPL. `print()` output is always
captured and returned as `stdout`, whether or not you also set `result`.
Two helpers are in scope for quick extraction: `await text(selector)` (inner
text of the first match, or `None`) and `await texts(selector)` (inner text
of every match).

Default timeout is 30 seconds. Raise `--timeout` for a long job rather than
splitting it into several short calls — a timeout still returns whatever
stdout was printed before the cutoff, so you don't lose partial progress.

## `brow run`

```
brow run -s <id> <file.py> [--arg key=value] [--timeout <ms>]
```

Runs a `.py` file once, in the same sandbox as `eval`, plus `args` — a dict
built from every `--arg key=value` passed:

```python
# scrape_paginated.py
results = []
page_num = 1
while True:
    await page.wait_for_selector(".product-row", timeout=10000)
    for row in await page.locator(".product-row").all():
        price_text = await row.locator(".price").inner_text()
        price = float(price_text.strip("$"))
        if price <= 0:
            raise ValueError(f"page {page_num}: bad price {price_text!r}")
        results.append({"name": await row.locator(".name").inner_text(), "price": price})

    next_btn = page.locator("#next")
    if await next_btn.count() == 0 or not await next_btn.is_visible():
        break
    await next_btn.click()
    await page.wait_for_timeout(150)
    page_num += 1

result = {"pages": page_num, "items": len(results), "data": results}
```

```bash
brow run -s 1 scrape_paginated.py
# {"pages": 3, "items": 5, "data": [...]}
```

### Why this beats a shell loop or a `replay` playbook

For anything with a real loop or a per-item check, both alternatives cost
more than they save:

- A shell loop of `brow eval` calls costs a process + HTTP round trip per
  iteration, and still has to guess how long to `sleep` after each action —
  measured at ~20x slower than one `run` call for 30 items (see
  `benchmarks/microbench_run_vs_loop.sh` in the repo).
- A YAML `replay` playbook's `for_each` needs the item count known up front;
  there's no "keep going until the button is gone" primitive, and no way to
  abort mid-loop on a bad row the way a Python `raise` does.

Reach for `eval` for a one-off snippet, `run` for anything you'd rerun or
tweak, and `replay` only for a short, flat, declarative sequence with no
real branching — see [Actions & Replay](/brow/cli/actions-replay/).
