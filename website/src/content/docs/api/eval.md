---
title: Eval API
description: HTTP endpoint for running arbitrary Playwright Python
---

## Execute code

```
POST /eval/{sid}
```

```json
{
  "code": "result = await page.title()\nprint(result)",
  "timeout": 30000
}
```

Executes arbitrary Python code in a sandboxed environment with access to the session's Playwright objects.

### Sandbox globals

brow bundles [`patchright`](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python)
(a stealth-patched fork of Playwright), not `playwright` itself — the objects
below are `patchright` instances, API-compatible with Playwright's.

| Name | Type | Description |
|------|------|-------------|
| `page` | `patchright.async_api.Page` | Active page |
| `context` | `patchright.async_api.BrowserContext` | Browser context |
| `browser` | `patchright.async_api.Browser` | Browser instance |
| `state` | `dict` | Session state (console_logs, network_requests, etc.) |
| `pages` | `list` | All pages in the session |
| `asyncio` | module | asyncio module |
| `text` | function | `await text(selector)` — inner text of the first match, or `None` |
| `texts` | function | `await texts(selector)` — inner text of every match |

**Response:**

```json
{
  "result": "Example Domain",
  "stdout": ""
}
```

`result` is whatever you assign to a variable named `result` — there's no
implicit "value of the last expression" the way a REPL works, so a bare
`await page.title()` with no assignment returns nothing. `stdout` always
captures anything printed with `print()`, whether or not you also set
`result`.

### Examples

**Get page title:**

```python
result = await page.title()
```

**Extract all links:**

```python
links = await page.evaluate("""
  () => Array.from(document.querySelectorAll('a[href]'))
        .map(a => ({text: a.innerText.trim(), href: a.href}))
""")
result = links
```

**Inject a cookie:**

```python
await context.add_cookies([{
  "name": "session",
  "value": "abc123",
  "domain": "example.com",
  "path": "/"
}])
```

**Grant permissions:**

```python
await context.grant_permissions(["geolocation"])
await page.set_geolocation({"latitude": 48.1, "longitude": 17.1})
```

!!! warning "No stdout return by default"
    `eval` does not return printed output unless you use `print()` explicitly and check `stdout`. Side effects (cookies set, navigation triggered) take effect immediately but aren't reported unless you capture them in `result`.

!!! note "Async functions"
    The sandbox is async — you can `await` any Playwright coroutine directly.

!!! tip "Long jobs: raise `timeout`, don't batch"
    A timed-out call still returns whatever stdout was printed before the
    cutoff, so raising `timeout` for a long job loses less than staging
    progress across many short calls.

For a reusable version of the same sandbox — a `.py` file executed once
instead of an inline code string — see [`brow run`](/brow/cli/eval-run/).
