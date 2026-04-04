---
title: Pages API
description: HTTP endpoints for tab and page management
---

Each session can have multiple pages (browser tabs). By default, commands operate on the last (most recently active) page.

## List pages

```
GET /pages/{sid}
```

**Response:**

```json
{
  "pages": [
    {"index": 0, "url": "https://example.com"},
    {"index": 1, "url": "https://github.com"}
  ]
}
```

---

## New page

```
POST /pages/{sid}/new
```

```json
{"url": "https://github.com"}
```

`url` is optional — omit to open a blank page.

**Response:**

```json
{"index": 1, "url": "https://github.com/"}
```

---

## Close page

```
POST /pages/{sid}/close?index=<n>
```

`index` is optional — omits closes the last page.

**Response:** `{"closed": 1}`

---

## Switch page

```
POST /pages/{sid}/switch
```

```json
{"index": 0}
```

Switches the active page (subsequent commands operate on this page).

**Response:**

```json
{"active": 0, "url": "https://example.com"}
```
