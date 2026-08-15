---
title: API Scouting
description: Reverse-engineer a site's API and generate a minimal scraper
---

API scouting is the process of using brow to discover and reverse-engineer a site's internal API, then crystallizing that knowledge into a minimal Python or Go script that calls the API directly — no browser required (or with just a cookie harvest).

## When to use this

- You want to scrape data from a site, but the page renders via JavaScript from API calls
- You want to automate interactions that would be slow or fragile with UI automation
- You want to call an internal API directly from a script

## Phase 1: Set up a session

```bash
brow session new --profile mysite --headed   # headed to handle bot detection
```

If the site uses Cloudflare or similar bot detection, start headed and wait 2–3 seconds after the first navigation before doing anything else.

## Phase 2: Capture network traffic

Clear the log, then navigate and interact:

```bash
brow network -s 1 --clear
brow navigate -s 1 "https://example.com/listings"
# interact with the page if needed (filters, pagination, etc.)
brow network -s 1 --search "api" --response
```

Look for:
- **JSON responses**: `application/json` content type
- **Pattern URLs**: `/api/v2/`, `/rest/`, `/graphql`, `/_next/data/`
- **Pagination patterns**: `page=`, `offset=`, `cursor=`
- **Search patterns**: `q=`, `query=`, `search=`

## Phase 3: Classify auth requirement

For each interesting endpoint, test whether it works without cookies:

```bash
# With browser cookies (authenticated):
brow fetch -s 1 "https://example.com/api/listings?page=1" | jq

# Without cookies (public?):
brow fetch -s 1 "https://example.com/api/listings?page=1" --no-cookies | jq
```

| Result | Meaning |
|--------|---------|
| Both return 200 with data | Public endpoint — no auth needed |
| `--no-cookies` returns 401/403 | Auth required — need cookies or session |
| `--no-cookies` returns empty `{"data":[]}` | Silently degrades without auth |

## Phase 4: Probe parameters

Explore the endpoint to understand its parameters:

```bash
# Try pagination
brow fetch -s 1 "https://example.com/api/listings?page=2"
brow fetch -s 1 "https://example.com/api/listings?limit=100"

# Try filters
brow fetch -s 1 "https://example.com/api/listings?category=electronics"

# Check response structure
brow fetch -s 1 "https://example.com/api/listings?page=1" | python3 -m json.tool | head -50
```

## Phase 5: Check for WebSocket updates

For live data (prices, inventory, scores), look at WebSocket traffic:

```bash
brow websocket -s 1 --clear
brow navigate -s 1 "https://example.com/live-data"
# wait a few seconds
brow websocket -s 1
```

If you see messages, capture the structure. Common patterns:
- **JSON Patch** (RFC 6902): `{"op":"replace","path":"/price","value":99.99}`
- **socket.io**: `42["event",{"data":{...}}]`
- **Custom JSON**: varies by site

## Phase 6: Generate a script

Based on your findings, choose an approach:

### Public API (no auth)

```python
import httpx
import json

BASE = "https://example.com"

def fetch_listings(page: int = 1, limit: int = 20):
    r = httpx.get(f"{BASE}/api/listings", params={"page": page, "limit": limit})
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    data = fetch_listings(page=1)
    print(json.dumps(data, indent=2))
```

### Authenticated API (cookies required)

brow bundles `patchright`, not `playwright` — `import playwright` fails in
brow's own environment. `patchright.sync_api` is drop-in compatible:

```python
import httpx
import json
from patchright.sync_api import sync_playwright

BASE = "https://example.com"

def get_cookies():
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir="/Users/you/.brow/profiles/mysite",
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
        )
        page = ctx.new_page()
        page.goto(f"{BASE}/listings")  # trigger auth cookies
        cookies = {c["name"]: c["value"] for c in ctx.cookies()}
        ctx.close()
    return cookies

def fetch_listings(cookies, page: int = 1):
    r = httpx.get(
        f"{BASE}/api/listings",
        params={"page": page},
        cookies=cookies,
        headers={"Accept": "application/json"},
    )
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    cookies = get_cookies()
    data = fetch_listings(cookies, page=1)
    print(json.dumps(data, indent=2))
```

## Real example: sports odds API

Here's a condensed trace of discovering a sports odds API:

```bash
# 1. Set up
brow session new --profile tipsport --headed
brow navigate -s 1 "https://tipsport.sk"

# 2. Capture traffic while navigating to football matches
brow network -s 1 --clear
brow navigate -s 1 "https://tipsport.sk/competition/football/sk-super-league"
brow network -s 1 --search "competition" --response
# → POST 200 application/json  /rest/offer/v2/competitions/136806/matches
# →   {"data":{"children":[{"id":...,"homeTeam":...,"odds":[...]}]}}

# 3. Test auth requirement
brow fetch -s 1 "/rest/offer/v2/competitions/136806/matches" --no-cookies
# → 200 but {"data":{"children":[]}}  ← needs cookies for data

# 4. With cookies
brow fetch -s 1 "/rest/offer/v2/competitions/136806/matches" | jq '.data.children[0]'
# → full match data with odds

# 5. Discover WebSocket for live updates
brow websocket -s 1 --search "odds"
# → recv  wss://tipsport.sk/socket.io/  [{"op":"replace","path":"/odds/0/value","value":1.85}]
```

Result: a `browser-session` script that harvests cookies from the persistent profile and calls the REST endpoint directly.
