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

| Name | Type | Description |
|------|------|-------------|
| `page` | `playwright.async_api.Page` | Active page |
| `context` | `playwright.async_api.BrowserContext` | Browser context |
| `browser` | `playwright.async_api.Browser` | Browser instance |
| `state` | `dict` | Session state (console_logs, network_requests, etc.) |
| `pages` | `list` | All pages in the session |
| `asyncio` | module | asyncio module |

**Response:**

```json
{
  "result": "Example Domain",
  "stdout": ""
}
```

`result` is the value of the last expression evaluated (if any). `stdout` captures any `print()` output.

### Examples

**Get page title:**

```python
await page.title()
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
