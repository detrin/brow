import json
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException

from brow.deps import get_page, get_session, log_action
from brow.models import ReplayReq

router = APIRouter(prefix="/browser/{sid}", tags=["browser"])

PLAYBOOK_FIELDS = {"name", "description", "base_url", "auth", "vars", "steps", "stop_on_failure"}
AUTH_MODES = {"none", "browser-session", "browser"}
STATES = {"visible", "hidden", "attached", "detached"}
STEP_FIELDS = {
    "navigate": ({"url"}, {"timeout"}),
    "click": ({"selector"}, set()),
    "fill": ({"selector", "value"}, set()),
    "key": ({"key"}, set()),
    "select": ({"selector", "value"}, set()),
    "fetch": ({"url"}, {"method", "headers", "auth", "output", "expect_status"}),
    "wait": (set(), {"selector", "state", "timeout", "ms"}),
    "assert": ({"selector"}, {"state", "timeout"}),
    "for_each": ({"var", "items", "steps"}, set()),
}


def _invalid(path, message):
    raise HTTPException(status_code=422, detail=f"{path}: {message}")


def _require(value, expected, path):
    if expected is int:
        ok = isinstance(value, int) and not isinstance(value, bool)
    else:
        ok = isinstance(value, expected)
    if not ok:
        _invalid(path, f"must be {expected.__name__}")


def _validate_wait(step, path):
    has_selector, has_ms = "selector" in step, "ms" in step
    if has_selector == has_ms:
        _invalid(path, "must contain exactly one of selector or ms")
    if has_selector:
        _require(step["selector"], str, f"{path}.selector")
    else:
        _require(step["ms"], int, f"{path}.ms")
        if step["ms"] < 0:
            _invalid(f"{path}.ms", "must be non-negative")
    if "state" in step and not has_selector:
        _invalid(f"{path}.state", "requires selector")


def _validate_fetch(step, path):
    if "method" in step:
        _require(step["method"], str, f"{path}.method")
    if "headers" in step:
        _require(step["headers"], dict, f"{path}.headers")
        if any(not isinstance(k, str) or not isinstance(v, str) for k, v in step["headers"].items()):
            _invalid(f"{path}.headers", "keys and values must be strings")
    if "auth" in step:
        _require(step["auth"], str, f"{path}.auth")
        if step["auth"] not in AUTH_MODES:
            _invalid(f"{path}.auth", f"must be one of {sorted(AUTH_MODES)}")
    if "output" in step:
        _require(step["output"], str, f"{path}.output")
    if "expect_status" in step:
        statuses = step["expect_status"]
        if not isinstance(statuses, list) or any(
            not isinstance(s, int) or isinstance(s, bool) or not 100 <= s <= 599 for s in statuses
        ):
            _invalid(f"{path}.expect_status", "must be a list of HTTP status integers")


def _validate_for_each(step, path):
    if not isinstance(step["items"], (str, list)):
        _invalid(f"{path}.items", "must be a variable name or list")
    validate_steps(step["steps"], f"{path}.steps")


_EXTRA_VALIDATORS = {"wait": _validate_wait, "fetch": _validate_fetch, "for_each": _validate_for_each}


def validate_steps(steps, path="steps"):
    if not isinstance(steps, list):
        _invalid(path, "must be a list")

    for index, step in enumerate(steps):
        step_path = f"{path}[{index}]"
        if not isinstance(step, dict):
            _invalid(step_path, "must be an object")
        if "action" not in step:
            _invalid(f"{step_path}.action", "is required")
        action = step["action"]
        if not isinstance(action, str) or action not in STEP_FIELDS:
            _invalid(f"{step_path}.action", f"unknown action {action!r}")

        required, optional = STEP_FIELDS[action]
        unknown = set(step) - {"action", "note", *required, *optional}
        if unknown:
            _invalid(f"{step_path}.{sorted(unknown)[0]}", "is not supported")
        missing = required - set(step)
        if missing:
            _invalid(f"{step_path}.{sorted(missing)[0]}", "is required")

        for field in required & {"url", "selector", "value", "key", "var"}:
            _require(step[field], str, f"{step_path}.{field}")
        if "note" in step:
            _require(step["note"], str, f"{step_path}.note")
        if "timeout" in step:
            _require(step["timeout"], int, f"{step_path}.timeout")
            if step["timeout"] < 0:
                _invalid(f"{step_path}.timeout", "must be non-negative")
        if "state" in step:
            _require(step["state"], str, f"{step_path}.state")
            if step["state"] not in STATES:
                _invalid(f"{step_path}.state", f"must be one of {sorted(STATES)}")

        extra = _EXTRA_VALIDATORS.get(action)
        if extra:
            extra(step, step_path)


def validate_playbook(playbook):
    unknown = set(playbook) - PLAYBOOK_FIELDS
    if unknown:
        _invalid(sorted(unknown)[0], "is not supported")
    if "steps" not in playbook:
        _invalid("steps", "is required")
    for field in ("name", "description", "base_url"):
        if field in playbook:
            _require(playbook[field], str, field)
    if "auth" in playbook:
        _require(playbook["auth"], str, "auth")
        if playbook["auth"] not in AUTH_MODES:
            _invalid("auth", f"must be one of {sorted(AUTH_MODES)}")
    if "vars" in playbook:
        _require(playbook["vars"], dict, "vars")
    if "stop_on_failure" in playbook:
        _require(playbook["stop_on_failure"], bool, "stop_on_failure")
    validate_steps(playbook["steps"])


def substitute(val, variables):
    if not isinstance(val, str):
        return val

    def repl(m):
        name, _, key = m.group(1).partition("[")
        v = variables.get(name)
        if key:
            key = key.rstrip("]")
            if isinstance(v, dict):
                v = v.get(key)
            elif isinstance(v, list):
                try:
                    v = v[int(key)]
                except (ValueError, IndexError):
                    v = None
            else:
                v = None
        if v is None and name not in variables:
            return m.group(0)
        return str(v)

    return re.sub(r"\{([^{}]+)\}", repl, val)


class Context:
    def __init__(self, page, session, variables, base_url, stop_on_failure=False, default_auth=None):
        self.page = page
        self.session = session
        self.variables = variables
        self.base_url = base_url
        self.stop_on_failure = stop_on_failure
        self.default_auth = default_auth

    def sub(self, val):
        return substitute(val, self.variables)

    def url(self, val):
        resolved = self.sub(val)
        return resolved if resolved.startswith("http") else self.base_url + resolved


async def _navigate(ctx, step, entry):
    url = ctx.url(step["url"])
    r = await ctx.page.goto(url, timeout=step.get("timeout", 30000))
    status = r.status if r else None
    entry.update({"url": url, "status": status, "ok": True})
    log_action(ctx.session, "navigate", url=url, status=status)


async def _click(ctx, step, entry):
    selector = ctx.sub(step["selector"])
    await ctx.page.click(selector)
    log_action(ctx.session, "click", selector=selector)
    entry["ok"] = True


async def _fill(ctx, step, entry):
    selector = ctx.sub(step["selector"])
    await ctx.page.fill(selector, ctx.sub(step["value"]))
    log_action(ctx.session, "fill", selector=selector)
    entry["ok"] = True


async def _key(ctx, step, entry):
    key = ctx.sub(step["key"])
    await ctx.page.keyboard.press(key)
    log_action(ctx.session, "key", key=key)
    entry["ok"] = True


async def _select(ctx, step, entry):
    selector, value = ctx.sub(step["selector"]), ctx.sub(step["value"])
    await ctx.page.select_option(selector, value)
    log_action(ctx.session, "select", selector=selector, value=value)
    entry["ok"] = True


async def _fetch(ctx, step, entry):
    url = ctx.url(step["url"])
    method = step.get("method", "GET")
    no_cookies = step.get("auth", ctx.default_auth) == "none"
    headers = {k: ctx.sub(v) for k, v in step.get("headers", {}).items()}
    if no_cookies:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30, headers=headers) as client:
            r = await client.request(method, url)
        body, status = r.text, r.status_code
    else:
        js = (
            "async ({url,method,headers})=>{"
            "const r=await fetch(url,{method,headers});"
            "return {status:r.status,body:await r.text()}}"
        )
        r = await ctx.page.evaluate(js, {"url": url, "method": method, "headers": headers})
        body, status = r["body"], r["status"]
    log_action(ctx.session, "fetch", url=url, method=method, no_cookies=no_cookies, status=status)

    expect = step.get("expect_status")
    ok = status in expect if expect else status < 400
    entry.update({"url": url, "status": status, "ok": ok})
    if not ok:
        entry["error"] = f"HTTP {status}"
    if step.get("output"):
        try:
            data = json.loads(body)
        except Exception:
            data = body
        entry["data"] = data
        ctx.variables[step["output"]] = data


async def _wait(ctx, step, entry):
    if step.get("selector"):
        await ctx.page.wait_for_selector(
            ctx.sub(step["selector"]), state=step.get("state", "visible"), timeout=step.get("timeout", 30000)
        )
    else:
        await ctx.page.wait_for_timeout(step.get("ms", 1000))
    entry["ok"] = True


async def _assert(ctx, step, entry):
    await ctx.page.wait_for_selector(
        ctx.sub(step["selector"]), state=step.get("state", "visible"), timeout=step.get("timeout", 5000)
    )
    entry["ok"] = True


HANDLERS = {
    "navigate": _navigate,
    "click": _click,
    "fill": _fill,
    "key": _key,
    "select": _select,
    "fetch": _fetch,
    "wait": _wait,
    "assert": _assert,
}


async def _for_each(ctx, step, results):
    var, items = step["var"], step["items"]
    if isinstance(items, str):
        if items not in ctx.variables:
            raise ValueError(f"for_each items variable {items!r} is not defined")
        items = ctx.variables[items]
    if not isinstance(items, list):
        raise TypeError(f"for_each items must resolve to a list, got {type(items).__name__}")

    failed = False
    for item in items:
        ctx.variables[var] = item
        nested = await run_steps(ctx, step["steps"])
        results.extend(nested)
        if ctx.stop_on_failure and any(not r["ok"] for r in nested):
            failed = True
            break
    ctx.variables.pop(var, None)
    return failed


async def run_steps(ctx, steps):
    results = []
    for step in steps:
        action = step["action"]
        if action == "for_each":
            try:
                if await _for_each(ctx, step, results):
                    break
            except Exception as e:
                results.append({"action": action, "ok": False, "error": str(e)})
                if ctx.stop_on_failure:
                    break
            continue

        entry = {"action": action, "ok": False}
        try:
            await HANDLERS[action](ctx, step, entry)
        except Exception as e:
            entry["error"] = str(e)
        results.append(entry)
        if not entry["ok"] and ctx.stop_on_failure:
            break
    return results


@router.post("/replay")
async def replay(body: ReplayReq, session=Depends(get_session), page=Depends(get_page)):
    validate_playbook(body.playbook)
    ctx = Context(
        page,
        session,
        {**body.playbook.get("vars", {}), **body.vars},
        body.playbook.get("base_url", ""),
        stop_on_failure=bool(body.playbook.get("stop_on_failure")),
        default_auth=body.playbook.get("auth"),
    )
    return {"results": await run_steps(ctx, body.playbook.get("steps", []))}
