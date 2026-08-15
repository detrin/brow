---
title: Actions & Replay
description: Recording and replaying browser actions
---

## `brow actions`

View the action log — every navigate, click, fill, key, select, upload, and fetch recorded in this session.

```
brow actions -s <id> [--json] [--clear]
```

| Flag | Description |
|------|-------------|
| `--json` | Output as JSON array instead of human-readable format |
| `--clear` | Reset the action log |

```bash
brow actions -s 1
# 1   navigate  https://example.com  [200]
# 2   fill      #email  value='user@example.com'
# 3   fill      #password  value='...'
# 4   click     button[type=submit]
# 5   navigate  https://example.com/dashboard  [200]

brow actions -s 1 --json
# [
#   {"seq": 1, "action": "navigate", "url": "https://example.com", "status": 200},
#   {"seq": 2, "action": "fill", "selector": "#email", "value": "user@example.com"},
#   ...
# ]
```

The action log is the input for the [Playbook Writer workflow](/brow/tutorials/playbook-writer/). After an exploratory session, review the log to identify the minimal set of steps needed, then write a playbook YAML from them.

## `brow replay`

Execute a playbook YAML file against the current session.

```
brow replay -s <id> <playbook.yaml> [--var <key>=<value>]
```

| Argument/Flag | Description |
|---------------|-------------|
| `<playbook.yaml>` | Path to the playbook file |
| `--var` | Override a playbook variable (repeatable) |

```bash
brow replay -s 1 search.yaml
brow replay -s 1 search.yaml --var query="playwright"
brow replay -s 1 search.yaml --var query="brow" --var count=20
```

Output per step:

```
✓  navigate   https://example.com  200
✓  fill       #search
✓  key        Enter
✓  navigate   https://example.com/results  200
   → {"results": [{"title": "brow", "url": "..."}...
✗  click      .nonexistent   Timeout waiting for selector
```

### Playbook format

```yaml
name: search-example
description: Search example.com for a term
base_url: https://example.com
auth: none                    # none | browser-session | browser
vars:
  query: "default value"      # overridable with --var

steps:
  - action: navigate
    url: /search

  - action: fill
    selector: "input[name=q]"
    value: "{query}"

  - action: key
    key: Enter

  - action: wait               # by condition, not just a fixed sleep
    selector: "#results"
    state: visible             # visible | hidden | attached | detached
    timeout: 10000

  - action: fetch
    url: /api/results?q={query}
    method: GET
    headers:
      X-Api-Key: "{api_key}"
    output: results            # captured JSON becomes {results} (and {results[key]}) in later steps
```

### Supported step actions

| Action | Required fields | Optional fields |
|--------|----------------|-----------------|
| `navigate` | `url` | `timeout` |
| `click` | `selector` | — |
| `fill` | `selector`, `value` | — |
| `key` | `key` | — |
| `select` | `selector`, `value` | — |
| `fetch` | `url` | `method`, `headers`, `auth`, `output`, `expect_status` |
| `wait` | — | `selector`+`state`, or `ms` for a fixed sleep |
| `assert` | `selector` | `state` — fails the step (not the run, unless `stop_on_failure`) if unmet |
| `for_each` | `var`, `items`, `steps` | loop nested `steps` over a literal or captured list |

A top-level `auth: none` on the playbook applies to every `fetch` step that
doesn't set its own `auth`. Add `stop_on_failure: true` at the top level to
halt the whole run (including out of a `for_each`) after the first failed
step, instead of the default "record it and keep going."

For anything needing real branching or a loop body more complex than a few
flat steps, prefer `brow run <file.py>` — a Python file executed once against
the live session, with the same `page`/`context`/`browser`/`state`/`pages`
variables as `eval`, plus `args` from `--arg key=value` — over growing this
YAML further.

### Variable substitution

Use `{varname}` anywhere in string fields. Variables come from the `vars` section and can be overridden with `--var`:

```yaml
vars:
  user_id: "123"
  date: "2024-01-01"

steps:
  - action: fetch
    url: /api/users/{user_id}/history?from={date}
```

```bash
brow replay -s 1 playbook.yaml --var user_id=456 --var date=2024-06-01
```
