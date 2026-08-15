# Playbook Writer

After completing a brow session that accomplishes a task, use this to distil the session into a minimal, reusable playbook YAML and generate a self-contained Python script from it.

## When to use

When the user says: "generate a script", "save this as a playbook", "make this repeatable", "create a scraper from this session".

---

## Step 1 — Review the action log

```bash
brow actions -s <id> --json
```

Read every entry. Classify each action:

| Action | Keep? | Reason |
|--------|-------|--------|
| `navigate` | ✓ if essential for auth/routing | Discard retries; keep final successful navigation |
| `fetch` with `no_cookies: false`, status 200 | ✓ | Productive data fetch — keep |
| `fetch` with `no_cookies: true`, status 200 | ✓ | Public endpoint — simpler script |
| `fetch` with `no_cookies: true`, status 4xx | note only | Confirms auth is required — don't keep as step, just inform auth field |
| `fetch` that returned wrong/empty data | ✗ | Discard failed probes |
| `click` / `fill` / `key` / `select` | ✓ if needed for routing/auth | Discard if page was already in right state |
| `click` / `fill` that failed and was retried | keep only the final working selector | |

---

## Step 2 — Determine auth strategy

Look at `fetch` actions and their `no_cookies` results:

- All needed fetches work with `no_cookies: true` → **auth: none** → pure httpx script, no browser
- Some fetches need `no_cookies: false` → **auth: browser-session** → Playwright for cookie harvest + httpx
- Task is pure UI interaction (no API found) → **auth: browser** → full Playwright script

---

## Step 3 — Write the playbook YAML

```yaml
name: <descriptive-name>
description: <one sentence>
base_url: https://target-site.com
auth: none | browser-session | browser
vars:
  <param_name>: <default_value>    # parameterise IDs, dates, search terms

steps:
  - action: navigate
    url: /path
    note: <why this is needed>

  - action: fetch
    url: /api/endpoint/{param_name}
    method: GET                     # omit if GET
    auth: none                      # omit if same as top-level auth
    output: result_name             # variable name for captured data

  - action: click
    selector: "css-or-text-selector"

  - action: fill
    selector: "#field"
    value: "{param_name}"

  - action: key
    key: Enter

  - action: wait
    selector: "#results"             # prefer this over ms — waits for the actual condition
    state: visible                  # visible | hidden | attached | detached
    timeout: 10000
  # - action: wait
  #   ms: 1000                      # fixed sleep — last resort, only for animations/debounce

  - action: assert                  # fail the step (not the whole run, unless stop_on_failure) if unmet
    selector: ".result-count"
    state: visible

  - action: for_each                # replaces "one step per item" — loop a captured or literal list
    var: item
    items: result_name              # a variable captured via `output:` above, or an inline list
    steps:
      - action: navigate
        url: /item/{item[id]}       # {item[key]} indexes into a dict/list variable
```

`output: result_name` makes the captured JSON available as `{result_name}` in
every later step, including `{result_name[key]}` for dict/list indexing — not
just recorded in the run's result log. Add `stop_on_failure: true` at the
playbook's top level if a later step's substitution depends on an earlier
step having actually succeeded.

Verify it works:
```bash
brow replay playbook.yaml -s <id>
brow replay playbook.yaml -s <id> --var param_name=other_value
```

---

## Step 4 — Generate Python script

Choose template based on `auth` field:

### auth: none — pure httpx (no browser)

```python
import httpx
import json

BASE = "https://target-site.com"

def fetch(path: str, **params) -> dict:
    r = httpx.get(f"{BASE}{path}", params=params, headers={"Accept": "application/json"})
    r.raise_for_status()
    return r.json()

def main(param_name="default_value"):
    data = fetch(f"/api/endpoint/{param_name}")
    return data

if __name__ == "__main__":
    import sys
    result = main(*sys.argv[1:])
    print(json.dumps(result, indent=2, ensure_ascii=False))
```

### auth: browser-session — cookie harvest + httpx

```python
import httpx
import json
from playwright.sync_api import sync_playwright

BASE = "https://target-site.com"

def get_cookies() -> dict:
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir="/tmp/brow-profile-<name>",
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
        )
        page = ctx.new_page()
        page.goto(f"{BASE}/path-needed-for-auth")
        cookies = {c["name"]: c["value"] for c in ctx.cookies()}
        ctx.close()
    return cookies

def fetch(path: str, cookies: dict, **params) -> dict:
    r = httpx.get(f"{BASE}{path}", params=params, cookies=cookies,
                  headers={"Accept": "application/json"})
    r.raise_for_status()
    return r.json()

def main(param_name="default_value"):
    cookies = get_cookies()
    data = fetch(f"/api/endpoint/{param_name}", cookies)
    return data

if __name__ == "__main__":
    import sys
    result = main(*sys.argv[1:])
    print(json.dumps(result, indent=2, ensure_ascii=False))
```

### auth: browser — full Playwright interaction

```python
import json
from playwright.sync_api import sync_playwright

BASE = "https://target-site.com"

def main(param_name="default_value"):
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir="/tmp/brow-profile-<name>",
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
        )
        page = ctx.new_page()

        # steps from playbook
        page.goto(f"{BASE}/path")
        page.click("selector")
        page.fill("#field", param_name)
        page.keyboard.press("Enter")
        page.wait_for_selector(".results")

        # extract data
        data = page.evaluate("() => { /* extract */ }")
        ctx.close()
    return data

if __name__ == "__main__":
    import sys
    result = main(*sys.argv[1:])
    print(json.dumps(result, indent=2, ensure_ascii=False))
```

---

## Output

Deliver:
1. `<name>.yaml` — the playbook
2. `<name>.py` — the generated script
3. Brief note on what was discarded and why (for the user's understanding)
