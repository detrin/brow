---
title: Playbook & Script Generation
description: Crystallize a brow session into a reusable YAML playbook and Python script
---

After an exploratory brow session, you can crystallize it into a reusable YAML playbook and then generate a standalone Python script from it.

## The workflow

```
Exploratory session
      ↓
brow actions --json    ← review what you did
      ↓
Write playbook.yaml    ← keep only the essential steps
      ↓
brow replay            ← verify it works
      ↓
Generate .py script    ← standalone, no brow needed
```

## Step 1: Review the action log

After your session, inspect what was recorded:

```bash
brow actions -s 1 --json
```

```json
[
  {"seq": 1, "action": "navigate", "url": "https://example.com", "status": 200},
  {"seq": 2, "action": "navigate", "url": "https://example.com", "status": 200},
  {"seq": 3, "action": "click", "selector": "text=Products"},
  {"seq": 4, "action": "fetch", "url": "https://example.com/api/products?category=all", "status": 200, "no_cookies": false},
  {"seq": 5, "action": "fetch", "url": "https://example.com/api/products?category=all", "status": 200, "no_cookies": true}
]
```

Classify each action:

| Seq | Keep? | Reason |
|-----|-------|--------|
| 1 | ✗ | Retry of seq 2 |
| 2 | ✓ | Final successful navigation |
| 3 | ✗ | Discovery click — not needed if we call the API directly |
| 4 | ✓ | Authenticated fetch that returned data |
| 5 | note | `--no-cookies` returned 200 — this endpoint is public! |

## Step 2: Determine auth strategy

Look at the `no_cookies` results:

- Seq 5 returned 200 with `no_cookies: true` → **auth: none** → pure httpx, no browser needed
- If seq 5 returned 401/403 → **auth: browser-session** → need cookies
- If no API was found and you need UI → **auth: browser** → skip the YAML, write a [`brow run`](/brow/cli/eval-run/) script instead

## Step 3: Write the playbook

```yaml
name: example-products
description: Fetch all products from example.com
base_url: https://example.com
auth: none
vars:
  category: all

steps:
  - action: fetch
    url: /api/products?category={category}
    method: GET
    output: products
```

Save as `example-products.yaml` and verify:

```bash
brow replay -s 1 example-products.yaml
# ✓  fetch   https://example.com/api/products?category=all  200
#    → {"products":[{"id":1,"name":"Widget"...

brow replay -s 1 example-products.yaml --var category=electronics
# ✓  fetch   https://example.com/api/products?category=electronics  200
```

## Step 4: Generate a Python script

### auth: none — pure httpx

```python
import httpx
import json

BASE = "https://example.com"

def fetch_products(category="all"):
    r = httpx.get(f"{BASE}/api/products", params={"category": category})
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    import sys
    result = fetch_products(*sys.argv[1:])
    print(json.dumps(result, indent=2, ensure_ascii=False))
```

```bash
python example-products.py electronics
```

### auth: browser-session — cookie harvest + httpx

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
        page.goto(f"{BASE}/")
        cookies = {c["name"]: c["value"] for c in ctx.cookies()}
        ctx.close()
    return cookies

def fetch_products(category="all"):
    cookies = get_cookies()
    r = httpx.get(
        f"{BASE}/api/products",
        params={"category": category},
        cookies=cookies,
        headers={"Accept": "application/json"},
    )
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    import sys
    result = fetch_products(*sys.argv[1:])
    print(json.dumps(result, indent=2, ensure_ascii=False))
```

### auth: browser — don't generate a second script, use `brow run`

A pure-UI task needs the live, already-authenticated session — that's what
`brow run` gives you directly, without spinning up a second browser context
and re-solving cookies/profile setup the session already has. Skip the YAML
and the standalone script; write the steps as a `.py` file instead:

```python
# scrape_products.py — page/context/browser/state/pages/args already in scope
await page.goto(f"{args['base_url']}/products")
await page.click(f"text={args['category']}")
await page.wait_for_selector(".product-grid")
result = await page.evaluate("""() =>
    Array.from(document.querySelectorAll('.product-card'))
         .map(el => ({
             name: el.querySelector('.name').textContent,
             price: el.querySelector('.price').textContent
         }))
""")
```

```bash
brow run scrape_products.py -s 1 --arg category=electronics --arg base_url=https://example.com
```

One artifact, no cookie harvesting, no separate context to keep in sync with
the live session. See [`brow run`](/brow/cli/eval-run/) for more.

## Tips

- **Parameterise aggressively**: any ID, date, search term, or pagination offset should be a variable
- **Discard discovery noise**: failed probes, retry attempts, and exploratory navigations should not appear in the final playbook
- **Test with `--var`** to confirm the parameterisation works before writing the Python script
- **Public endpoints are simpler**: if `--no-cookies` worked, drop the Playwright cookie harvest entirely
