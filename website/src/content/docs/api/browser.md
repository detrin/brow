---
title: Browser Actions API
description: HTTP endpoints for browser interaction and observation
---

All routes are under `/browser/{sid}` where `{sid}` is the session ID.

---

## Navigate

```
POST /browser/{sid}/navigate
```

```json
{"url": "https://example.com", "timeout": 30000}
```

**Response:**

```json
{
  "url": "https://example.com/",
  "status": 200,
  "snapshot": "h1 \"Example Domain\"\n...",
  "truncated": false
}
```

---

## Wait

```
POST /browser/{sid}/wait
```

```json
{"selector": ".results", "load": false, "timeout": 30000}
```

Pass `"selector"` to wait for an element, or `"load": true` to wait for network idle.

**Response:** `{"ok": true}`

---

## Get URL

```
GET /browser/{sid}/url
```

**Response:** `{"url": "https://example.com/current-page"}`

---

## Snapshot

```
GET /browser/{sid}/snapshot?search=<regex>&locator=<selector>
```

**Response:**

```json
{
  "tree": "navigation\n  [1] a \"Home\"...",
  "truncated": false,
  "hint": "Page has 600+ nodes. Use search param to filter."
}
```

---

## Screenshot

```
POST /browser/{sid}/screenshot
```

```json
{
  "full": false,
  "path": "/tmp/page.png",
  "width": null,
  "scale": null,
  "quality": "medium"
}
```

`quality` is a preset: `"low"` (400px), `"medium"` (800px), `"high"` (1200px). Overrides `width` when set.

**Response:** `{"path": "/Users/you/.brow/screenshots/2024-01-01T12-00-00.png"}`

---

## HTML

```
GET /browser/{sid}/html?locator=<selector>&search=<regex>
```

**Response:** `{"html": "<main>...</main>"}`

---

## Console logs

```
GET /browser/{sid}/logs?search=<str>&count=50
```

**Response:** `{"logs": "[log] Page loaded\n[error] Failed to fetch..."}`

---

## Network requests

```
GET /browser/{sid}/network?search=<str>&count=50&include_static=false&include_response=false
```

**Response:** `{"network": "GET  200  application/json  https://api.example.com/data\n  → {\"results\":..."}`

```
DELETE /browser/{sid}/network
```

**Response:** `{"ok": true}`

---

## Fetch

```
POST /browser/{sid}/fetch
```

```json
{
  "url": "https://api.example.com/data",
  "method": "GET",
  "headers": {"Accept": "application/json"},
  "body": null,
  "no_cookies": false
}
```

When `no_cookies` is `false` (default), the request runs inside the browser page using `fetch()` — cookies and session are included. When `true`, a plain `httpx` request is made without any browser state.

**Response:**

```json
{
  "status": 200,
  "contentType": "application/json",
  "body": "{\"results\": [...]}"
}
```

---

## WebSocket messages

```
GET /browser/{sid}/websocket?search=<str>&count=50
```

**Response:** `{"websocket": "recv  wss://example.com/ws  {\"op\":\"replace\",\"path\":\"/price\",\"value\":1.85}\n..."}`

```
DELETE /browser/{sid}/websocket
```

**Response:** `{"ok": true}`

---

## Click

```
POST /browser/{sid}/click
```

```json
{
  "selector": "button[type=submit]",
  "ref": null,
  "timeout": 30000,
  "retry": 0,
  "wait_for_selector": true
}
```

Provide either `selector` or `ref` (element ref from snapshot). `retry` attempts the click up to N additional times (1-second delay each) if it fails.

**Response:**

```json
{"ok": true, "snapshot": "...", "truncated": false}
```

---

## Fill

```
POST /browser/{sid}/fill
```

```json
{
  "selector": "#email",
  "ref": null,
  "value": "user@example.com",
  "timeout": 30000,
  "retry": 0,
  "wait_for_selector": true
}
```

**Response:** `{"ok": true, "snapshot": "..."}`

---

## Select

```
POST /browser/{sid}/select
```

```json
{"selector": "#country", "ref": null, "value": "Slovakia", "timeout": 30000}
```

**Response:** `{"ok": true, "snapshot": "..."}`

---

## Type

```
POST /browser/{sid}/type
```

```json
{"text": "Hello, world"}
```

Types at the current focus position using real keyboard events.

**Response:** `{"ok": true}`

---

## Key

```
POST /browser/{sid}/key
```

```json
{"key": "Enter"}
```

Accepts any Playwright key string: `Enter`, `Tab`, `Escape`, `Meta+a`, `Control+c`, `ArrowDown`, etc.

**Response:** `{"ok": true, "snapshot": "..."}`

---

## Hover

```
POST /browser/{sid}/hover
```

```json
{"selector": "nav .dropdown", "timeout": 30000}
```

**Response:** `{"ok": true}`

---

## Scroll

```
POST /browser/{sid}/scroll
```

```json
{"pixels": 1000}
```

Or scroll to an element:

```json
{"selector": "#footer"}
```

**Response:** `{"ok": true}`

---

## Drag

```
POST /browser/{sid}/drag
```

```json
{"source": ".draggable-card", "target": ".drop-zone"}
```

**Response:** `{"ok": true}`

---

## Upload

```
POST /browser/{sid}/upload
```

```json
{"selector": "input[type='file']", "filepath": "/path/to/file.csv"}
```

**Response:** `{"ok": true}`

---

## Action log

```
GET /browser/{sid}/actions?as_json=false
```

Returns the action log as formatted text (default) or JSON array.

**Response (text):**

```json
{"actions": "1   navigate  https://example.com  [200]\n2   click     button[type=submit]\n..."}
```

**Response (JSON):**

```json
{
  "actions": [
    {"seq": 1, "action": "navigate", "url": "https://example.com", "status": 200},
    {"seq": 2, "action": "click", "selector": "button[type=submit]"}
  ]
}
```

```
DELETE /browser/{sid}/actions
```

**Response:** `{"ok": true}`

---

## Replay playbook

```
POST /browser/{sid}/replay
```

```json
{
  "playbook": {
    "name": "my-playbook",
    "base_url": "https://example.com",
    "vars": {"query": "test"},
    "steps": [
      {"action": "navigate", "url": "/search"},
      {"action": "fill", "selector": "input", "value": "{query}"},
      {"action": "key", "key": "Enter"}
    ]
  },
  "vars": {"query": "override"}
}
```

Variables in `vars` override those in `playbook.vars`.

**Response:**

```json
{
  "results": [
    {"action": "navigate", "ok": true, "url": "https://example.com/search", "status": 200},
    {"action": "fill", "ok": true},
    {"action": "key", "ok": true},
    {"action": "fetch", "ok": true, "url": "...", "status": 200, "data": {...}}
  ]
}
```
