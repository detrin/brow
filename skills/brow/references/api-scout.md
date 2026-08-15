# API Scout

Systematic workflow for reverse-engineering a website's API using brow, ending with a minimal runnable script.

## When to use

When the user wants to:
- Understand what API calls a website makes
- Extract data without a browser (scraping, monitoring, arbitrage)
- Find WebSocket streams for real-time data

---

## Phase 1 — Session Setup

```bash
# Use headed + named profile to survive bot detection
brow session new --headed --profile scout-<sitename>
brow navigate -s <id> "https://target-site.com"
# Wait for Cloudflare/bot challenges to resolve (retry once after 3-5s if 403)
brow navigate -s <id> "https://target-site.com"
```

---

## Phase 2 — Capture API Traffic

Clear the log first so you only see requests from the target navigation:

```bash
brow network --clear -s <id>
brow navigate -s <id> "https://target-site.com/the-page-you-care-about"
# Wait for full load
brow network -s <id> --count 200 --search "application/json"
```

Identify candidate endpoints — look for:
- `application/json` content type
- Paths containing `rest/`, `api/`, `graphql`, `v1/`, `v2/`
- Ignore: analytics, ads, tracking (google, facebook, bing, gtm)

---

## Phase 3 — Auth Classification

For each candidate endpoint, test with and without browser cookies:

```bash
# With browser session (cookies + headers)
brow fetch -s <id> "<url>" | head -c 500

# Without cookies (plain HTTP)
brow fetch -s <id> "<url>" --no-cookies | head -c 500
```

Classify:
- **Public** — both return same data → no auth needed, plain HTTP works
- **Auth-required** — `--no-cookies` returns 401/403/redirect → needs session
- **Bot-protected** — `--no-cookies` returns 403 with challenge page → needs browser fingerprint

---

## Phase 4 — Deep Probe

For public/auth endpoints that returned data, understand the structure:

```bash
# Fetch and pretty-print
brow fetch -s <id> "<url>" | python3 -m json.tool | head -100

# Explore URL parameters by varying them
brow fetch -s <id> "<url>?param=value1" --no-cookies | python3 -m json.tool
```

Look for:
- Pagination params (`page`, `offset`, `limit`, `cursor`)
- Filter params (`sportId`, `competitionId`, `from`, `to`)
- IDs embedded in previous responses that unlock other endpoints

---

## Phase 5 — WebSocket Check

Navigate to the most data-rich page (live data, real-time updates):

```bash
brow websocket --clear -s <id>
brow navigate -s <id> "https://target-site.com/live"
# Wait 5-10s for WS messages to arrive
brow websocket -s <id> --count 5
```

If messages appear:
- Note the `wss://` URL
- Identify the protocol (socket.io, raw WS, STOMP, etc.)
- Identify namespaces/topics/channels
- Note the message format (JSON Patch, full snapshot, delta)

---

## Phase 6 — Generate Minimal Script

Based on findings, output a script in the requested language. Default to Python.

### Python template (public REST + WebSocket)

```python
import httpx
import asyncio
import json

BASE = "https://target-site.com"

def get_data(path: str) -> dict:
    r = httpx.get(f"{BASE}{path}", headers={"Accept": "application/json"})
    r.raise_for_status()
    return r.json()

# --- discovered endpoints ---
# sports = get_data("/rest/offer/v6/sports?...")
# matches = get_data(f"/rest/offer/v2/competitions/{competition_id}/matches")

async def watch_live():
    import websockets
    async with websockets.connect("wss://target-site.com/socket.io/?EIO=4&transport=websocket") as ws:
        async for msg in ws:
            data = json.loads(msg[2:])  # strip socket.io prefix
            print(data)

if __name__ == "__main__":
    asyncio.run(watch_live())
```

### Go template (public REST)

```go
package main

import (
    "encoding/json"
    "fmt"
    "net/http"
)

const base = "https://target-site.com"

func fetch(path string, out any) error {
    r, err := http.Get(base + path)
    if err != nil { return err }
    defer r.Body.Close()
    return json.NewDecoder(r.Body).Decode(out)
}

func main() {
    var data map[string]any
    if err := fetch("/rest/offer/v2/competitions/136806/matches", &data); err != nil {
        panic(err)
    }
    fmt.Printf("%+v\n", data)
}
```

### JS/Node template (public REST)

```js
const BASE = 'https://target-site.com'

async function get(path) {
  const r = await fetch(BASE + path, { headers: { Accept: 'application/json' } })
  return r.json()
}

// const matches = await get('/rest/offer/v2/competitions/136806/matches')
```

---

## Auth-required sites — cookie harvesting

When endpoints need browser cookies, harvest once and reuse:

```bash
# Save session state after login
brow eval -s <id> "
import json
cookies = await context.cookies()
result = json.dumps(cookies)
"
# Paste output → use as Cookie header in script
```

Or use Playwright persistent context directly in the script for sites with heavy bot protection.

---

## Output checklist

Before finishing, confirm you have:
- [ ] List of all relevant endpoints (URL, method, auth requirement)
- [ ] Response schema for each (key fields, types, nesting)
- [ ] WebSocket URL + protocol + message format (if applicable)
- [ ] Minimal runnable script that hits the endpoints
- [ ] Notes on rate limits, bot protection, pagination
