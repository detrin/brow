import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from brow.config import SCREENSHOTS_DIR, DEFAULT_TIMEOUT, ensure_dirs
from brow.snapshot import format_tree, filter_lines

router = APIRouter(prefix="/browser/{sid}", tags=["browser"])

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

class NavigateReq(BaseModel):
    url: str
    timeout: int = DEFAULT_TIMEOUT

class WaitReq(BaseModel):
    selector: Optional[str] = None
    load: bool = False
    timeout: int = DEFAULT_TIMEOUT

class ClickReq(BaseModel):
    selector: str
    timeout: int = DEFAULT_TIMEOUT

class FillReq(BaseModel):
    selector: str
    value: str
    timeout: int = DEFAULT_TIMEOUT

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

class ScreenshotReq(BaseModel):
    full: bool = False
    path: Optional[str] = None

@router.post("/navigate")
async def navigate(req: Request, sid: str, body: NavigateReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    r = await page.goto(body.url, timeout=body.timeout)
    return {"url": page.url, "status": r.status if r else None}

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

    js_code = """
    () => {
        function buildTree(node, depth = 0) {
            if (!node || depth > 20) return null;

            const obj = { role: node.tagName?.toLowerCase() || 'text' };

            if (node.nodeType === Node.TEXT_NODE) {
                const text = node.textContent?.trim();
                if (text) obj.name = text;
                return text ? obj : null;
            }

            if (node.nodeType !== Node.ELEMENT_NODE) return null;

            const role = node.getAttribute('role') || node.tagName.toLowerCase();
            obj.role = role;

            const ariaLabel = node.getAttribute('aria-label');
            const alt = node.getAttribute('alt');
            const title = node.getAttribute('title');
            const value = node.value;

            if (ariaLabel) obj.name = ariaLabel;
            else if (alt) obj.name = alt;
            else if (title) obj.name = title;
            else if (value) obj.value = value;
            else if (['input', 'button', 'a'].includes(role)) {
                obj.name = node.textContent?.trim()?.substring(0, 50) || '';
            }

            const checked = node.checked;
            if (checked !== undefined) obj.checked = checked;

            const children = [];
            for (const child of node.childNodes) {
                const childObj = buildTree(child, depth + 1);
                if (childObj) children.push(childObj);
            }

            if (children.length > 0) obj.children = children;

            return obj;
        }

        return buildTree(document.body);
    }
    """

    tree = await page.evaluate(js_code)
    formatted = format_tree(tree) if tree else ""
    if search:
        formatted = filter_lines(formatted, search)
    return {"tree": formatted}

@router.post("/screenshot")
async def screenshot(req: Request, sid: str, body: ScreenshotReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    ensure_dirs()
    if body.path:
        path = Path(body.path)
    else:
        path = SCREENSHOTS_DIR / f"{sid}-{int(time.time())}.png"
    await page.screenshot(path=str(path), full_page=body.full)
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
    session = _get_session(req, sid)
    page = _get_page(session)
    await page.click(body.selector, timeout=body.timeout)
    return {"ok": True}

@router.post("/fill")
async def fill(req: Request, sid: str, body: FillReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    await page.fill(body.selector, body.value, timeout=body.timeout)
    return {"ok": True}

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
    return {"ok": True}

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

@router.post("/upload")
async def upload(req: Request, sid: str, body: UploadReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    await page.set_input_files(body.selector, body.filepath)
    return {"ok": True}
