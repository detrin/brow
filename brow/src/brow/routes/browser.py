import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException

from brow.config import SCREENSHOTS_DIR, ensure_dirs
from brow.deps import get_page, get_session, log_action, resolve_selector
from brow.models import (
    ClickReq,
    ClickUntilReq,
    DragReq,
    FetchReq,
    FillReq,
    HoverReq,
    KeyReq,
    NavigateReq,
    ScreenshotReq,
    ScrollReq,
    ScrollUntilReq,
    SelectReq,
    TypeReq,
    UploadReq,
    WaitReq,
)
from brow.snapshot import SnapshotLocatorError, filter_lines, take_snapshot, with_snapshot

router = APIRouter(prefix="/browser/{sid}", tags=["browser"])

STATIC_PREFIXES = ("image/", "font/", "text/css", "application/javascript", "text/javascript", "application/font")


async def _snapshot_response(session, page, action=None, **fields):
    if action:
        log_action(session, action, **fields)
    formatted, meta = await take_snapshot(page)
    return with_snapshot({"ok": True, "snapshot": formatted}, meta)


async def _retry_target(page, body, run, verb):
    selector = resolve_selector(body)
    last_error = None
    attempts = body.retry + 1
    for attempt in range(attempts):
        try:
            if body.wait_for_selector:
                await page.wait_for_selector(selector, timeout=body.timeout, state="visible")
            await run(selector)
            return selector
        except Exception as e:
            last_error = e
            if attempt < attempts - 1:
                await asyncio.sleep(1)
    raise HTTPException(
        500, f"Failed to {verb} selector '{selector}' after {attempts} attempts. Last error: {last_error}"
    )


@router.post("/navigate")
async def navigate(body: NavigateReq, session=Depends(get_session), page=Depends(get_page)):
    try:
        r = await page.goto(body.url, timeout=body.timeout)
    except Exception as e:
        logging.error(f"Navigate to {body.url} failed: {e}")
        raise HTTPException(502, f"Navigation failed: {e}")
    status = r.status if r else None
    if body.wait in ("load", "networkidle"):
        try:
            await page.wait_for_load_state(body.wait, timeout=min(body.timeout, 10000))
        except Exception:
            pass
    log_action(session, "navigate", url=body.url, status=status)
    formatted, meta = await take_snapshot(page)
    return with_snapshot({"url": page.url, "status": status, "snapshot": formatted}, meta)


@router.post("/wait")
async def wait(body: WaitReq, page=Depends(get_page)):
    if body.load:
        await page.wait_for_load_state(timeout=body.timeout)
    elif body.selector:
        await page.wait_for_selector(body.selector, timeout=body.timeout)
    return {"ok": True}


@router.get("/url")
async def get_url(page=Depends(get_page)):
    return {"url": page.url}


@router.get("/snapshot")
async def snapshot(
    search: Optional[str] = None,
    locator: Optional[str] = None,
    compact: bool = False,
    limit: int = 10,
    page=Depends(get_page),
):
    try:
        formatted, meta = await take_snapshot(page, search=search, locator=locator, limit=limit)
    except SnapshotLocatorError as e:
        raise HTTPException(400, str(e))
    lines = formatted.split("\n")
    if (compact or len(lines) > 500) and not search:
        interactive = [ln for ln in lines if "[" in ln and "]" in ln]
        context = [ln for ln in lines if any(k in ln for k in ("heading", "navigation", "main", "form"))]
        kept = list(dict.fromkeys(interactive + context))[:300]
        formatted = f"[Showing {len(kept)} of {len(lines)} lines — use --search <regex> to filter]\n" + "\n".join(kept)
        meta["truncated"] = True
        meta["lines_kept"] = (len(kept), len(lines))
    return with_snapshot({"tree": formatted}, meta)


@router.post("/screenshot")
async def screenshot(sid: str, body: ScreenshotReq, page=Depends(get_page)):
    from PIL import Image

    ensure_dirs()
    path = Path(body.path) if body.path else SCREENSHOTS_DIR / f"{sid}-{int(time.time())}.png"
    await page.screenshot(path=str(path), full_page=body.full)

    if body.width or body.scale or body.quality:
        img = Image.open(path)
        if body.quality:
            width = {"low": 400, "medium": 800, "high": 1200}.get(body.quality, 800)
        elif body.width:
            width = body.width
        else:
            width = int(img.width * body.scale)
        if width != img.width:
            img = img.resize((width, int(width * img.height / img.width)), Image.Resampling.LANCZOS)
            img.save(path, optimize=True, quality=85)

    return {"path": str(path)}


@router.get("/html")
async def get_html(locator: Optional[str] = None, search: Optional[str] = None, page=Depends(get_page)):
    html = await page.locator(locator).inner_html() if locator else await page.content()
    return {"html": filter_lines(html, search) if search else html}


@router.get("/logs")
async def get_logs(search: Optional[str] = None, count: int = 50, session=Depends(get_session)):
    text = "\n".join(session.state.get("console_logs", [])[-count:])
    return {"logs": filter_lines(text, search) if search else text}


@router.get("/network")
async def get_network(
    search: Optional[str] = None,
    count: int = 50,
    include_static: bool = False,
    include_response: bool = False,
    session=Depends(get_session),
):
    reqs = session.state.get("network_requests", [])
    if not include_static:
        reqs = [r for r in reqs if not any(r["type"].startswith(p) for p in STATIC_PREFIXES)]
    if search:
        pattern = re.compile(search)
        reqs = [r for r in reqs if pattern.search(r["url"]) or pattern.search(r["type"])]
    lines = []
    for r in reqs[-count:]:
        line = f"{r['method']:<6} {r['status']}  {r['type']:<30} {r['url']}"
        if include_response and r.get("response_preview"):
            line += f"\n    {r['response_preview'][:200]}"
        lines.append(line)
    return {"network": "\n".join(lines)}


@router.delete("/network")
async def clear_network(session=Depends(get_session)):
    session.state["network_requests"] = []
    return {"ok": True}


FETCH_JS = """
async ({url, method, headers, body}) => {
    const opts = {method, headers: headers || {}};
    if (body) opts.body = body;
    const r = await fetch(url, opts);
    const text = await r.text();
    return {status: r.status, contentType: r.headers.get('content-type') || '', body: text};
}
"""


@router.post("/fetch")
async def fetch_url(body: FetchReq, session=Depends(get_session)):
    if body.no_cookies:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            r = await client.request(body.method, body.url, headers=body.headers or {}, content=body.body)
        log_action(session, "fetch", url=body.url, method=body.method, no_cookies=True, status=r.status_code)
        return {"status": r.status_code, "contentType": r.headers.get("content-type", ""), "body": r.text}

    result = await get_page(session).evaluate(
        FETCH_JS,
        {"url": body.url, "method": body.method, "headers": body.headers or {}, "body": body.body},
    )
    log_action(session, "fetch", url=body.url, method=body.method, no_cookies=False, status=result.get("status"))
    return result


@router.get("/websocket")
async def get_websocket(search: Optional[str] = None, count: int = 50, session=Depends(get_session)):
    msgs = session.state.get("websocket_messages", [])[-count:]
    text = "\n".join(f"{m['direction'].upper():<4}  {m['url']}\n      {m['data'][:200]}" for m in msgs)
    return {"websocket": filter_lines(text, search) if search else text}


@router.delete("/websocket")
async def clear_websocket(session=Depends(get_session)):
    session.state["websocket_messages"] = []
    return {"ok": True}


@router.post("/click")
async def click(body: ClickReq, session=Depends(get_session), page=Depends(get_page)):
    async def run(selector):
        await page.click(selector, timeout=body.timeout)
        log_action(session, "click", selector=selector)
        try:
            await page.wait_for_load_state("load", timeout=300)
        except Exception:
            await asyncio.sleep(0.15)

    await _retry_target(page, body, run, "click")
    return await _snapshot_response(session, page)


@router.post("/fill")
async def fill(body: FillReq, session=Depends(get_session), page=Depends(get_page)):
    async def run(selector):
        await page.fill(selector, body.value, timeout=body.timeout)
        log_action(session, "fill", selector=selector)

    await _retry_target(page, body, run, "fill")
    return await _snapshot_response(session, page)


@router.post("/type")
async def type_text(body: TypeReq, page=Depends(get_page)):
    await page.keyboard.type(body.text)
    return {"ok": True}


@router.post("/key")
async def press_key(body: KeyReq, session=Depends(get_session), page=Depends(get_page)):
    await page.keyboard.press(body.key)
    return await _snapshot_response(session, page, "key", key=body.key)


@router.post("/hover")
async def hover(body: HoverReq, page=Depends(get_page)):
    await page.hover(body.selector, timeout=body.timeout)
    return {"ok": True}


@router.post("/scroll")
async def scroll(body: ScrollReq, page=Depends(get_page)):
    if body.selector:
        await page.locator(body.selector).scroll_into_view_if_needed()
    else:
        await page.evaluate(f"window.scrollBy(0, {body.pixels})")
    return {"ok": True}


@router.post("/scroll-until")
async def scroll_until(body: ScrollUntilReq, page=Depends(get_page)):
    for attempt in range(body.max_attempts):
        try:
            loc = page.locator(body.until)
            if await loc.count() > 0 and await loc.first.is_visible():
                await loc.first.scroll_into_view_if_needed()
                return {"ok": True, "found": True, "attempts": attempt + 1}
        except Exception:
            pass
        await page.evaluate(f"window.scrollBy(0, {body.pixels})")
        await page.wait_for_timeout(500)
    return {"ok": True, "found": False, "attempts": body.max_attempts}


async def _count(page, selector, label):
    try:
        return await page.locator(selector).count()
    except Exception as e:
        raise HTTPException(400, f"Invalid {label} '{selector}': {e}")


@router.post("/click-until")
async def click_until(body: ClickUntilReq, session=Depends(get_session), page=Depends(get_page)):
    iterations = 0
    reason = "until_gone cleared"
    done = False

    for _ in range(body.max_iterations):
        if body.until_gone and await _count(page, body.until_gone, "until_gone selector") == 0:
            done = True
            break
        if await _count(page, body.selector, "selector") == 0:
            done, reason = True, "clickable is gone"
            break
        try:
            await page.locator(body.selector).first.click(timeout=body.timeout)
        except Exception as e:
            return {
                "ok": False,
                "done": False,
                "iterations": iterations,
                "reason": f"click failed on iteration {iterations + 1}: {e}",
            }
        iterations += 1
        await page.wait_for_timeout(body.settle_ms)
    else:
        reason = f"hit max_iterations ({body.max_iterations}) — work may remain, re-run to continue"

    if body.until_gone and not done:
        try:
            done = await page.locator(body.until_gone).count() == 0
            if done:
                reason = "until_gone cleared"
        except Exception:
            pass

    log_action(session, "click-until", selector=body.selector, iterations=iterations)
    return {"ok": True, "done": done, "iterations": iterations, "reason": reason}


@router.post("/drag")
async def drag(body: DragReq, page=Depends(get_page)):
    await page.drag_and_drop(body.source, body.target)
    return {"ok": True}


@router.post("/select")
async def select_option(body: SelectReq, session=Depends(get_session), page=Depends(get_page)):
    selector = resolve_selector(body)
    await page.select_option(selector, body.value, timeout=body.timeout)
    return await _snapshot_response(session, page, "select", selector=selector, value=body.value)


@router.post("/upload")
async def upload(body: UploadReq, session=Depends(get_session), page=Depends(get_page)):
    await page.set_input_files(body.selector, body.filepath)
    log_action(session, "upload", selector=body.selector, filepath=body.filepath)
    return {"ok": True}


ACTION_FORMATS = {
    "navigate": lambda a: f"navigate  {a.get('url', '')}  [{a.get('status', '')}]",
    "fetch": lambda a: (
        f"fetch     {a.get('url', '')}  [{a.get('status', '')}]" + (" --no-cookies" if a.get("no_cookies") else "")
    ),
    "click": lambda a: f"click     {a.get('selector', '')}",
    "fill": lambda a: f"fill      {a.get('selector', '')}  value=<redacted>",
    "key": lambda a: f"key       {a.get('key', '')}",
    "select": lambda a: f"select    {a.get('selector', '')}  value={a.get('value', '')!r}",
    "upload": lambda a: f"upload    {a.get('selector', '')}  file={a.get('filepath', '')}",
}


@router.get("/actions")
async def get_actions(as_json: bool = False, session=Depends(get_session)):
    actions = session.state.get("actions", [])
    if as_json:
        return {"actions": actions}
    fmt = ACTION_FORMATS
    lines = [f"{a['seq']:<3} {fmt[a['action']](a) if a['action'] in fmt else a['action']}" for a in actions]
    return {"actions": "\n".join(lines)}


@router.delete("/actions")
async def clear_actions(session=Depends(get_session)):
    session.state["actions"] = []
    return {"ok": True}
