---
title: HTTP API
description: Direct HTTP API reference for the brow daemon
---

The brow daemon exposes a REST API on `http://127.0.0.1:19987`. All request and response bodies are JSON.

## Base URL

```
http://127.0.0.1:19987
```

Configurable via `BROW_PORT` environment variable.

## Interactive docs

The daemon serves OpenAPI docs at:

- Swagger UI: `http://127.0.0.1:19987/docs`
- ReDoc: `http://127.0.0.1:19987/redoc`
- OpenAPI JSON: `http://127.0.0.1:19987/openapi.json`

## Error responses

All errors follow FastAPI's standard format:

```json
{"detail": "Session 5 not found"}
```

| HTTP Status | Meaning |
|-------------|---------|
| `400` | Invalid request body |
| `404` | Session, selector, or resource not found |
| `408` | Eval timeout |
| `502` | Browser error (navigation failed, selector timeout) |

## Sections

| Section | Prefix | Description |
|---------|--------|-------------|
| [Sessions](sessions.md) | `/sessions` | Create and manage browser sessions |
| [Browser Actions](browser.md) | `/browser/{sid}` | Navigate, click, fill, inspect |
| [Pages](pages.md) | `/pages/{sid}` | Multi-tab management |
| [Profiles & States](profiles.md) | `/profiles`, `/states` | Login persistence |
| [Eval](eval.md) | `/eval/{sid}` | Execute arbitrary Python |

## Health check

```
GET /status
```

```json
{"status": "running", "sessions": 2}
```
