import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from brow.config import SCREENSHOTS_DIR, DEFAULT_TIMEOUT, ensure_dirs
from brow.snapshot import format_tree, filter_lines

router = APIRouter(prefix="/browser/{sid}", tags=["browser"])

SNAPSHOT_JS = """
() => {
    document.querySelectorAll('[data-brow-ref]').forEach(el => el.removeAttribute('data-brow-ref'));

    const INTERACTIVE = new Set([
        'a', 'button', 'input', 'select', 'textarea', 'option',
        'details', 'summary', 'dialog', 'menu', 'menuitem',
    ]);
    const INTERACTIVE_ROLES = new Set([
        'button', 'tab', 'link', 'menuitem', 'option', 'switch',
        'checkbox', 'radio', 'slider', 'spinbutton', 'combobox',
        'searchbox', 'textbox',
    ]);
    const SEMANTIC = new Set([
        'h1','h2','h3','h4','h5','h6','img','video','audio',
        'table','thead','tbody','tr','th','td','ul','ol','li',
        'form','label','fieldset','legend','nav','main',
    ]);
    const SKIP = new Set([
        'script','style','noscript','svg','path','link','meta',
        'br','hr','iframe',
    ]);

    let nodeCount = 0;
    let refCounter = 0;
    const NODE_LIMIT = 300;

    function sig(node) {
        if (node.nodeType !== Node.ELEMENT_NODE) return '';
        const tag = node.tagName;
        const cls = node.className ? '.' + node.className.split(' ')[0] : '';
        const ch = node.children.length;
        return tag + cls + ch;
    }

    function buildTree(node, depth) {
        if (!node || depth > 15 || nodeCount >= NODE_LIMIT) return null;

        if (node.nodeType === Node.TEXT_NODE) {
            const t = node.textContent?.trim();
            if (!t || !t.length) return null;
            nodeCount++;
            return { role: 'text', name: t.substring(0, 80) };
        }
        if (node.nodeType !== Node.ELEMENT_NODE) return null;

        const tag = node.tagName.toLowerCase();
        if (SKIP.has(tag)) return null;

        // Table-aware: emit compact table node instead of deep tree
        if (tag === 'table') {
            nodeCount++;
            const headers = [];
            const rows = [];
            const ths = node.querySelectorAll('thead th, thead td, tr:first-child th');
            ths.forEach(th => headers.push(th.textContent?.trim()?.substring(0, 60) || ''));
            const trs = node.querySelectorAll('tbody tr, tr');
            const startIdx = headers.length > 0 && trs.length > 0 && trs[0].querySelector('th') ? 1 : 0;
            const MAX_TABLE_ROWS = 10;
            for (let i = startIdx; i < trs.length && rows.length < MAX_TABLE_ROWS; i++) {
                const cells = [];
                trs[i].querySelectorAll('td, th').forEach(td => {
                    cells.push(td.textContent?.trim()?.substring(0, 60) || '');
                });
                if (cells.length > 0) rows.push(cells);
            }
            const totalRows = trs.length - startIdx;
            return { role: 'table', headers, rows, totalRows };
        }

        if (node.hidden || node.getAttribute('aria-hidden') === 'true') return null;

        const role = node.getAttribute('role') || tag;
        const ariaLabel = node.getAttribute('aria-label');
        const alt = node.getAttribute('alt');
        const placeholder = node.getAttribute('placeholder');
        const name = ariaLabel || alt || node.getAttribute('title') || '';
        const isInteractive = INTERACTIVE.has(tag) || INTERACTIVE_ROLES.has(node.getAttribute('role'));
        const isSemantic = SEMANTIC.has(tag);

        const childNodes = Array.from(node.childNodes);
        let children = [];
        let lastSig = '', repeatCount = 0;
        for (const child of childNodes) {
            if (nodeCount >= NODE_LIMIT) break;
            const s = sig(child);
            if (s && s === lastSig) {
                repeatCount++;
                if (repeatCount > 3) continue;
            } else {
                if (repeatCount > 3) {
                    children.push({ role: 'text', name: '... ' + (repeatCount - 3) + ' similar items omitted' });
                    nodeCount++;
                }
                lastSig = s;
                repeatCount = 0;
            }
            const c = buildTree(child, depth + 1);
            if (c) children.push(c);
        }
        if (repeatCount > 3) {
            children.push({ role: 'text', name: '... ' + (repeatCount - 3) + ' similar items omitted' });
            nodeCount++;
        }

        if (!isInteractive && !isSemantic && !name) {
            if (children.length === 0) return null;
            if (children.length === 1) return children[0];
            return { role: 'group', children };
        }

        nodeCount++;
        const obj = { role };
        if (isInteractive) {
            refCounter++;
            node.setAttribute('data-brow-ref', String(refCounter));
            obj.ref = refCounter;
        }
        if (name) obj.name = name.substring(0, 80);
        else if (isInteractive && !name) {
            const txt = node.textContent?.trim()?.substring(0, 50);
            if (txt) obj.name = txt;
        }
        if (placeholder && !obj.name) obj.name = placeholder;
        if (node.value !== undefined && node.value !== '') obj.value = String(node.value).substring(0, 80);
        if (node.checked !== undefined) obj.checked = node.checked;
        if (node.disabled) obj.disabled = true;
        if (tag === 'a' && node.href) obj.href = node.href;

        if (children.length > 0) {
            if (children.length === 1 && children[0].role === 'text' && !obj.name) {
                obj.name = children[0].name;
            } else {
                obj.children = children;
            }
        }

        // List compression: inline >5 same-type simple children
        if (children.length > 5) {
            const roles = children.map(c => c.role);
            const firstRole = roles[0];
            const allSame = roles.every(r => r === firstRole);
            const allSimple = children.every(c => !c.children || c.children.every(gc => gc.role === 'text'));
            if (allSame && allSimple) {
                return { role: 'inline-list', itemRole: firstRole, items: children };
            }
        }

        return obj;
    }

    const tree = buildTree(document.body, 0);
    return { tree, truncated: nodeCount >= NODE_LIMIT, nodeCount, refCount: refCounter };
}
"""

async def _take_snapshot(page, search=None):
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass
    result = await page.evaluate(SNAPSHOT_JS)
    tree = result.get("tree") if isinstance(result, dict) else result
    truncated = result.get("truncated", False) if isinstance(result, dict) else False
    node_count = result.get("nodeCount", 0) if isinstance(result, dict) else 0
    formatted = format_tree(tree) if tree else ""
    if search:
        formatted = filter_lines(formatted, search)
    return formatted, truncated, node_count

def _get_session(req, sid):
    try:
        return req.app.state.manager.get(sid)
    except KeyError:
        raise HTTPException(404, f"Session {sid} not found")

def _get_page(session):
    page = session.page
    if not page:
        raise HTTPException(400, "No active page")
    return page

def _resolve_selector(body):
    if hasattr(body, 'ref') and body.ref is not None:
        return f'[data-brow-ref="{body.ref}"]'
    if hasattr(body, 'selector') and body.selector is not None:
        return body.selector
    raise HTTPException(400, "Either 'ref' or 'selector' must be provided")

class NavigateReq(BaseModel):
    url: str
    timeout: int = DEFAULT_TIMEOUT

class WaitReq(BaseModel):
    selector: Optional[str] = None
    load: bool = False
    timeout: int = DEFAULT_TIMEOUT

class ClickReq(BaseModel):
    selector: Optional[str] = None
    ref: Optional[int] = None
    timeout: int = DEFAULT_TIMEOUT
    retry: int = 0
    wait_for_selector: bool = True

class FillReq(BaseModel):
    selector: Optional[str] = None
    ref: Optional[int] = None
    value: str
    timeout: int = DEFAULT_TIMEOUT
    retry: int = 0
    wait_for_selector: bool = True

class TypeReq(BaseModel):
    text: str

class KeyReq(BaseModel):
    key: str

class HoverReq(BaseModel):
    selector: str
    timeout: int = DEFAULT_TIMEOUT

class ScrollReq(BaseModel):
    pixels: int = 0
    selector: Optional[str] = None

class DragReq(BaseModel):
    source: str
    target: str

class UploadReq(BaseModel):
    selector: str
    filepath: str

class SelectReq(BaseModel):
    selector: Optional[str] = None
    ref: Optional[int] = None
    value: str
    timeout: int = DEFAULT_TIMEOUT

class ScreenshotReq(BaseModel):
    full: bool = False
    path: Optional[str] = None
    width: Optional[int] = None
    scale: Optional[float] = None
    quality: Optional[str] = None

@router.post("/navigate")
async def navigate(req: Request, sid: str, body: NavigateReq):
    import logging
    session = _get_session(req, sid)
    page = _get_page(session)
    try:
        r = await page.goto(body.url, timeout=body.timeout)
    except Exception as e:
        logging.error(f"Navigate to {body.url} failed: {e}")
        raise HTTPException(502, f"Navigation failed: {e}")
    formatted, truncated, node_count = await _take_snapshot(page)
    resp = {"url": page.url, "status": r.status if r else None, "snapshot": formatted}
    if truncated:
        resp["truncated"] = True
        resp["hint"] = f"Page has {node_count}+ nodes. Use search param to filter."
    return resp

@router.post("/wait")
async def wait(req: Request, sid: str, body: WaitReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    if body.load:
        await page.wait_for_load_state(timeout=body.timeout)
    elif body.selector:
        await page.wait_for_selector(body.selector, timeout=body.timeout)
    return {"ok": True}

@router.get("/url")
async def get_url(req: Request, sid: str):
    session = _get_session(req, sid)
    page = _get_page(session)
    return {"url": page.url}

@router.get("/snapshot")
async def snapshot(req: Request, sid: str, search: Optional[str] = None, locator: Optional[str] = None):
    session = _get_session(req, sid)
    page = _get_page(session)
    formatted, truncated, node_count = await _take_snapshot(page, search=search)
    resp = {"tree": formatted}
    if truncated:
        resp["truncated"] = True
        resp["hint"] = f"Page has {node_count}+ nodes. Use search param to filter, e.g. search='Item 100'"
    return resp

@router.post("/screenshot")
async def screenshot(req: Request, sid: str, body: ScreenshotReq):
    from PIL import Image

    session = _get_session(req, sid)
    page = _get_page(session)
    ensure_dirs()
    if body.path:
        path = Path(body.path)
    else:
        path = SCREENSHOTS_DIR / f"{sid}-{int(time.time())}.png"

    await page.screenshot(path=str(path), full_page=body.full)

    if body.width or body.scale or body.quality:
        img = Image.open(path)

        if body.quality:
            presets = {"low": 400, "medium": 800, "high": 1200}
            target_width = presets.get(body.quality, 800)
        elif body.width:
            target_width = body.width
        elif body.scale:
            target_width = int(img.width * body.scale)
        else:
            target_width = img.width

        if target_width != img.width:
            aspect_ratio = img.height / img.width
            target_height = int(target_width * aspect_ratio)
            img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
            img.save(path, optimize=True, quality=85)

    return {"path": str(path)}

@router.get("/html")
async def get_html(req: Request, sid: str, locator: Optional[str] = None, search: Optional[str] = None):
    session = _get_session(req, sid)
    page = _get_page(session)
    if locator:
        el = page.locator(locator)
        html = await el.inner_html()
    else:
        html = await page.content()
    if search:
        html = filter_lines(html, search)
    return {"html": html}

@router.get("/logs")
async def get_logs(req: Request, sid: str, search: Optional[str] = None, count: int = 50):
    session = _get_session(req, sid)
    logs = session.state.get("console_logs", [])
    text = "\n".join(logs[-count:])
    if search:
        text = filter_lines(text, search)
    return {"logs": text}

@router.post("/click")
async def click(req: Request, sid: str, body: ClickReq):
    import asyncio as aio

    session = _get_session(req, sid)
    page = _get_page(session)
    selector = _resolve_selector(body)

    attempts = body.retry + 1
    last_error = None

    for attempt in range(attempts):
        try:
            if body.wait_for_selector:
                await page.wait_for_selector(selector, timeout=body.timeout, state="visible")

            await page.click(selector, timeout=body.timeout)
            formatted, truncated, _ = await _take_snapshot(page)
            resp = {"ok": True, "snapshot": formatted}
            if truncated:
                resp["truncated"] = True
            return resp
        except Exception as e:
            last_error = e
            if attempt < attempts - 1:
                await aio.sleep(1)

    raise HTTPException(
        500,
        f"Failed to click selector '{selector}' after {attempts} attempts. Last error: {str(last_error)}"
    )

@router.post("/fill")
async def fill(req: Request, sid: str, body: FillReq):
    import asyncio as aio

    session = _get_session(req, sid)
    page = _get_page(session)
    selector = _resolve_selector(body)

    attempts = body.retry + 1
    last_error = None

    for attempt in range(attempts):
        try:
            if body.wait_for_selector:
                await page.wait_for_selector(selector, timeout=body.timeout, state="visible")

            await page.fill(selector, body.value, timeout=body.timeout)
            formatted, truncated, _ = await _take_snapshot(page)
            resp = {"ok": True, "snapshot": formatted}
            if truncated:
                resp["truncated"] = True
            return resp
        except Exception as e:
            last_error = e
            if attempt < attempts - 1:
                await aio.sleep(1)

    raise HTTPException(
        500,
        f"Failed to fill selector '{selector}' after {attempts} attempts. Last error: {str(last_error)}"
    )

@router.post("/type")
async def type_text(req: Request, sid: str, body: TypeReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    await page.keyboard.type(body.text)
    return {"ok": True}

@router.post("/key")
async def press_key(req: Request, sid: str, body: KeyReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    await page.keyboard.press(body.key)
    formatted, truncated, _ = await _take_snapshot(page)
    resp = {"ok": True, "snapshot": formatted}
    if truncated:
        resp["truncated"] = True
    return resp

@router.post("/hover")
async def hover(req: Request, sid: str, body: HoverReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    await page.hover(body.selector, timeout=body.timeout)
    return {"ok": True}

@router.post("/scroll")
async def scroll(req: Request, sid: str, body: ScrollReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    if body.selector:
        await page.locator(body.selector).scroll_into_view_if_needed()
    else:
        await page.evaluate(f"window.scrollBy(0, {body.pixels})")
    return {"ok": True}

@router.post("/drag")
async def drag(req: Request, sid: str, body: DragReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    await page.drag_and_drop(body.source, body.target)
    return {"ok": True}

@router.post("/select")
async def select_option(req: Request, sid: str, body: SelectReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    selector = _resolve_selector(body)
    await page.select_option(selector, body.value, timeout=body.timeout)
    formatted, truncated, _ = await _take_snapshot(page)
    resp = {"ok": True, "snapshot": formatted}
    if truncated:
        resp["truncated"] = True
    return resp

@router.post("/upload")
async def upload(req: Request, sid: str, body: UploadReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    await page.set_input_files(body.selector, body.filepath)
    return {"ok": True}
