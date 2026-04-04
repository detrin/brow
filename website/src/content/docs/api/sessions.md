---
title: Sessions API
description: HTTP endpoints for session lifecycle management
---

## Create session

```
POST /sessions
```

**Request:**

```json
{
  "profile": "default",
  "headless": true,
  "url": "https://example.com"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `profile` | string | `"default"` | Chromium profile name |
| `headless` | boolean | `true` | Run without visible window |
| `url` | string | — | Navigate to this URL after launch |

**Response:**

```json
{
  "id": "1",
  "profile": "default",
  "url": "https://example.com/",
  "status": 200,
  "snapshot": "h1 \"Example Domain\"\n[1] a \"More...\" href=\"...\""
}
```

If `url` is provided, the response includes the navigation result. Otherwise only `id` and `profile` are returned.

---

## List sessions

```
GET /sessions
```

**Response:**

```json
[
  {"id": "1", "profile": "default", "headless": true, "pages": 1},
  {"id": "2", "profile": "mysite", "headless": false, "pages": 2}
]
```

---

## Delete session

```
DELETE /sessions/{sid}
```

Closes the browser context. Profile data is preserved.

**Response:**

```json
{"deleted": "1"}
```
