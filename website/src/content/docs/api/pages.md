---
title: Pages API
description: HTTP endpoints for tab and page management
---

Each session can have multiple pages (browser tabs). Commands operate on
whichever page was last explicitly chosen — via `switch`, or the page a
session started on — falling back to the newest open page only if none was
ever chosen, or the chosen one has since closed.

## List pages

```
GET /pages/{sid}
```

**Response:**

```json
{
  "pages": [
    {"index": 0, "url": "https://example.com", "active": false},
    {"index": 1, "url": "https://github.com", "active": true}
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

`url` is optional — omit to open a blank page. The new page becomes active
only if no page had been explicitly chosen yet (e.g. via `switch`) — an
earlier deliberate choice isn't silently overridden by a tab opening later.

**Response:**

```json
{"index": 1, "url": "https://github.com/", "active": 1}
```

`active` is the index of whichever page is active after this call — not
necessarily the page just created.

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
