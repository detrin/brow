import re
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from brow.config import DEFAULT_TIMEOUT, SCREENSHOTS_DIR, ensure_dirs
from brow.snapshot import filter_lines, format_tree, match_lines

router = APIRouter(prefix="/browser/{sid}", tags=["browser"])

SNAPSHOT_JS = """
(arg) => {
    const opts = arg || {};
    const rootEl = opts.root || document.body;
    const searchMode = !!opts.search;

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
    const CHROME = new Set(['nav', 'header', 'footer', 'aside']);
    const CHROME_ROLES = new Set(['navigation', 'banner', 'contentinfo', 'complementary']);

    function isInteractiveEl(el) {
        return INTERACTIVE.has(el.tagName.toLowerCase()) || INTERACTIVE_ROLES.has(el.getAttribute('role'));
    }

    // Pre-scan: count interactive elements to set adaptive cap
    const allElements = rootEl.querySelectorAll('*');
    let interactiveCount = 0;
    for (const el of allElements) {
        if (isInteractiveEl(el)) interactiveCount++;
    }

    // The budget spends text nodes as well as elements, so the denominator in
    // "N of M nodes" has to count them too — otherwise the notice can claim
    // more nodes were kept than the page has.
    let totalNodes = allElements.length;
    try {
        const walker = document.createTreeWalker(rootEl, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
            if (walker.currentNode.textContent && walker.currentNode.textContent.trim()) totalNodes++;
        }
    } catch (e) { /* denominator stays element-only */ }

    let NODE_LIMIT;
    if (interactiveCount < 50) {
        NODE_LIMIT = 200;
    } else if (interactiveCount <= 150) {
        NODE_LIMIT = 400;
    } else {
        NODE_LIMIT = 300;
    }

    // Under --search only matching lines reach the caller, so a stingy walk buys
    // no tokens and costs matches that silently never existed. Walk wide instead.
    if (searchMode) NODE_LIMIT = 8000;
    const TEXT_MAX = searchMode ? 400 : 80;
    const CELL_MAX = searchMode ? 400 : 60;
    const MAX_TABLE_ROWS = searchMode ? 500 : 10;

    // Smallest budget the chrome pass may be left with, so the page's controls
    // survive even when the content pass spends everything.
    // (Also keeps the pass-2 cap above zero: a zero cap would make buildTree
    // bail at the root and take the spliced content subtree down with it.)
    const CHROME_FLOOR = 60;

    // Nodes a menu-like container may spend when it sits inside the content root.
    const MENU_QUOTA = 12;

    // One budget, re-capped per pass. `capped` records a container quota firing,
    // `exhausted` a pass running out — both mean nodes were dropped.
    const budget = { spent: 0, cap: NODE_LIMIT, exhausted: false, capped: false };
    function out() { return budget.spent >= budget.cap; }

    const refEls = [];
    let walkErrors = 0;
    let walkError = '';
    const skipNonInteractive = interactiveCount > 150;

    function isVisible(el) {
        if (!el || el.hidden || el.getAttribute('aria-hidden') === 'true') return false;
        return el.offsetParent !== null || el.getClientRects().length > 0;
    }

    // Collapse runs of whitespace before measuring. Raw textContent counts the
    // newlines and indentation between elements, which on a 842-item dropdown
    // adds up to more "prose" than a real article has — enough to make a menu
    // outscore the content it sits next to.
    function textLen(el) {
        return (el.textContent || '').replace(/\\s+/g, ' ').trim().length;
    }

    // Prose, not link text: a 140-link navbar is bigger than the article it sits
    // above, so counting characters alone picks the chrome every time.
    function scoreBlock(el) {
        const text = textLen(el);
        if (!text) return 0;
        let linkText = 0;
        for (const a of el.querySelectorAll('a')) linkText += textLen(a);
        const fields = el.querySelectorAll('input, select, textarea').length;
        return Math.max(0, text - linkText) + fields * 30;
    }

    // A big container carrying no prose of its own is a menu, not content, even
    // when it sits inside <main> — github.com/trending keeps a 1,000-entry
    // language dropdown there, and uncapped it spends the entire content budget
    // before the repository rows are reached. A listing earns its budget by
    // carrying real text per row; a dropdown of bare links does not.
    function looksLikeMenu(el) {
        const role = el.getAttribute('role');
        if (role === 'menu' || role === 'listbox' || role === 'tablist') return true;
        return scoreBlock(el) < el.children.length * 20;
    }

    function findContentRoot() {
        if (rootEl !== document.body) return null;  // already scoped by --locator

        const main = document.querySelector('main, [role="main"]');
        if (main && main !== document.body && isVisible(main)) return main;

        const articles = Array.from(document.querySelectorAll('article'));
        if (articles.length === 1 && isVisible(articles[0])) return articles[0];
        if (articles.length > 1) {
            // A page of article cards: the list container is the content, not the
            // first card.
            const parent = articles[0].parentElement;
            if (parent && parent !== document.body &&
                articles.every(a => a.parentElement === parent) && isVisible(parent)) {
                return parent;
            }
        }

        const CANDIDATE = new Set(['div', 'section', 'table', 'ul', 'ol']);
        let best = null;
        let bestScore = 200;  // floor: below this there is no content worth reserving for
        let examined = 0;

        function scan(node, depth) {
            if (depth > 6 || examined > 400) return;
            for (const child of node.children) {
                const tag = child.tagName.toLowerCase();
                if (SKIP.has(tag) || CHROME.has(tag)) continue;
                if (CHROME_ROLES.has(child.getAttribute('role'))) continue;
                if (CANDIDATE.has(tag) && isVisible(child)) {
                    examined++;
                    // >= so a tighter descendant with the same substance wins.
                    const score = scoreBlock(child);
                    if (score >= bestScore) { bestScore = score; best = child; }
                }
                scan(child, depth + 1);
            }
        }
        scan(document.body, 0);
        return best;
    }

    function describe(el) {
        const tag = el.tagName.toLowerCase();
        if (el.id) return tag + '#' + el.id;
        const cls = typeof el.className === 'string' ? el.className.trim().split(/\\s+/)[0] : '';
        return cls ? tag + '.' + cls : tag;
    }

    function sig(node) {
        if (node.nodeType !== Node.ELEMENT_NODE) return '';
        // On SVG elements className is an SVGAnimatedString, not a string, so
        // .split() throws. sig() runs outside the child loop's try, so that
        // throw used to escape buildTree and get swallowed by the *parent's*
        // catch — silently deleting every icon-bearing link and button from the
        // snapshot. That, not the node budget, is why github.com/trending
        // showed zero repository rows.
        const raw = typeof node.className === 'string' ? node.className : '';
        const cls = raw ? '.' + raw.split(' ')[0] : '';
        const ch = node.children.length;
        return node.tagName + cls + ch;
    }

    let contentRoot = null;
    let contentTree = null;
    let contentDone = false;
    let contentSpliced = false;
    let inContentPass = false;

    // Ancestors of the content root, until it has been spliced in. Pass 2 must
    // stay able to walk down to the content subtree even with an exhausted
    // budget, or a heavy header makes it discard the very content pass 1 spent
    // the whole budget building — which is what left github.com/trending and
    // Wikipedia articles with nothing but chrome.
    function onContentPath(node) {
        if (!contentDone || contentSpliced || !contentRoot) return false;
        if (!node || node.nodeType !== Node.ELEMENT_NODE) return false;
        return node === contentRoot || node.contains(contentRoot);
    }

    function buildTree(node, depth) {
        if (!node || depth > 15) return null;

        // The content subtree is already paid for; splice it in at its document
        // position so the output order is exactly what it was before. Checked
        // before the budget, because reaching it must never depend on what pass
        // 2 has left over.
        if (contentDone && node === contentRoot) {
            contentSpliced = true;
            return contentTree;
        }
        if (out() && !onContentPath(node)) return null;

        if (node.nodeType === Node.TEXT_NODE) {
            const t = node.textContent?.trim();
            if (!t || !t.length) return null;
            budget.spent++;
            return { role: 'text', name: t.substring(0, TEXT_MAX) };
        }
        if (node.nodeType !== Node.ELEMENT_NODE) return null;

        const tag = node.tagName.toLowerCase();
        if (SKIP.has(tag)) return null;

        // Table-aware: emit compact table node instead of deep tree
        if (tag === 'table') {
            budget.spent++;
            const headers = [];
            const rows = [];
            const ths = node.querySelectorAll('thead th, thead td, tr:first-child th');
            ths.forEach(th => headers.push(th.textContent?.trim()?.substring(0, CELL_MAX) || ''));
            const trs = node.querySelectorAll('tbody tr, tr');
            const startIdx = headers.length > 0 && trs.length > 0 && trs[0].querySelector('th') ? 1 : 0;
            for (let i = startIdx; i < trs.length && rows.length < MAX_TABLE_ROWS; i++) {
                const cells = [];
                trs[i].querySelectorAll('td, th').forEach(td => {
                    cells.push(td.textContent?.trim()?.substring(0, CELL_MAX) || '');
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
        // A single 180-item dropdown must not be able to spend the whole pass.
        // Only genuinely huge containers are capped, so listings of a dozen
        // varied cards are left alone; the pass root is exempt, since there is
        // nothing else in the pass for it to crowd out, and so are the content
        // root's ancestors, since capping one could cut the walk off before it
        // reached the spliced subtree.
        // Search mode caps nothing: only matching lines reach the caller, so a
        // quota buys no tokens and costs matches — a language buried in a
        // 842-item dropdown has to be findable.
        let quota = 0;
        if (!searchMode && depth > 0 && node.children.length > 20 && !onContentPath(node)) {
            if (!inContentPass) {
                quota = Math.max(20, Math.floor(budget.cap * 0.2));
            } else if (looksLikeMenu(node)) {
                // Inside the content root, a menu gets a flat allowance rather
                // than a share of the budget: three dropdowns in <main> at 20%
                // each is 60% of the content budget spent on things that are not
                // content. This keeps a few refs and the omitted-item count.
                quota = MENU_QUOTA;
            }
        }
        const spentBefore = budget.spent;
        let children = [];
        let lastSig = '', repeatCount = 0;
        let seen = 0;
        for (const child of childNodes) {
            if (out() && !onContentPath(child)) {
                // Out of budget: stop, unless the content subtree is still
                // waiting further along this child list.
                if (!onContentPath(node)) break;
                continue;
            }
            if (quota && budget.spent - spentBefore >= quota) {
                const left = node.children.length - seen;
                if (left > 0) {
                    children.push({ role: 'text', name: '... ' + left + ' more items omitted (container cap)' });
                    budget.spent++;
                    budget.capped = true;
                }
                break;
            }
            if (child.nodeType === Node.ELEMENT_NODE) seen++;
            const s = sig(child);
            if (s && s === lastSig) {
                repeatCount++;
                if (repeatCount > 3) continue;
            } else {
                if (repeatCount > 3) {
                    children.push({ role: 'text', name: '... ' + (repeatCount - 3) + ' similar items omitted' });
                    budget.spent++;
                }
                lastSig = s;
                repeatCount = 0;
            }
            try {
                const c = buildTree(child, depth + 1);
                if (c) children.push(c);
            } catch (e) {
                // Dropping a subtree silently is how a one-line crash hid real
                // page content for as long as it did. Count it and report it.
                walkErrors++;
                if (!walkError) walkError = e.message;
            }
        }
        if (repeatCount > 3) {
            children.push({ role: 'text', name: '... ' + (repeatCount - 3) + ' similar items omitted' });
            budget.spent++;
        }

        if (!isInteractive && !isSemantic && !name) {
            if (children.length === 0) return null;
            if (children.length === 1) return children[0];
            return { role: 'group', children };
        }

        // When interactive-dense, skip non-interactive non-semantic nodes sooner.
        // Never during the content pass: on a link-dense article (a wiki page,
        // say) "non-interactive" is the prose, and dropping it defeats the
        // reason the content pass exists.
        if (skipNonInteractive && !inContentPass && !isInteractive && budget.spent > budget.cap * 0.7) {
            if (children.length === 0) return null;
            return { role: 'group', children };
        }

        budget.spent++;
        const obj = { role };
        if (isInteractive) {
            // Provisional number; renumber() below reassigns refs in output
            // order and writes the DOM attributes to match.
            refEls.push(node);
            obj.ref = refEls.length;
        }
        if (name) obj.name = name.substring(0, TEXT_MAX);
        else if (isInteractive && !name) {
            const txt = node.textContent?.trim()?.substring(0, 50);
            if (txt) obj.name = txt;
        }
        if (placeholder && !obj.name) obj.name = placeholder;
        const inputType = tag === 'input' ? (node.getAttribute('type') || 'text').toLowerCase() : '';
        if (inputType !== 'password' && node.value !== undefined && node.value !== '') {
            obj.value = String(node.value).substring(0, 80);
        }
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

    // Two passes build the content subtree before the chrome around it, so refs
    // are assigned out of document order. Renumber the assembled tree so [N]
    // still ascends as the caller reads down it, and point the DOM attributes at
    // the new numbers. Refs on subtrees that were built but dropped never make
    // it here, so no stale attribute is left behind for a click to resolve.
    function renumber(tree) {
        const assigned = [];
        function visit(node) {
            if (!node || typeof node !== 'object') return;
            if (node.ref !== undefined) {
                assigned.push(refEls[node.ref - 1]);
                node.ref = assigned.length;
            }
            (node.items || []).forEach(visit);
            (node.children || []).forEach(visit);
        }
        visit(tree);
        document.querySelectorAll('[data-brow-ref]').forEach(el => el.removeAttribute('data-brow-ref'));
        assigned.forEach((el, i) => { if (el) el.setAttribute('data-brow-ref', String(i + 1)); });
        return assigned.length;
    }

    function safeBuild(node) {
        try {
            return buildTree(node, 0);
        } catch (e) {
            // Fallback: return minimal tree on crash
            return { role: 'text', name: 'Snapshot error: ' + e.message };
        }
    }

    let contentDescriptor = null;
    let contentComplete = true;
    let contentSpent = 0;
    try {
        contentRoot = findContentRoot();
    } catch (e) {
        contentRoot = null;
    }

    // Pass 1: the content root is walked first and may spend the entire budget.
    // Capping it below NODE_LIMIT would make content *worse* off than the old
    // single pass on any page whose content came first, which is exactly what a
    // long article is.
    if (contentRoot) {
        contentDescriptor = describe(contentRoot);
        budget.cap = NODE_LIMIT;
        budget.spent = 0;
        inContentPass = true;
        contentTree = safeBuild(contentRoot);
        inContentPass = false;
        contentComplete = !out();
        if (!contentComplete) budget.exhausted = true;
        contentDone = true;
        contentSpent = budget.spent;
        // Chrome gets the remainder, but never nothing: a snapshot with no nav
        // or search refs at all cannot be acted on, and CHROME_FLOOR nodes is
        // cheap next to losing the page's controls.
        budget.cap = Math.max(CHROME_FLOOR, NODE_LIMIT - contentSpent);
        budget.spent = 0;
    }

    // Pass 2: everything else, in document order, with the content spliced back in.
    const tree = safeBuild(rootEl);
    if (out()) budget.exhausted = true;

    return {
        tree,
        truncated: budget.exhausted || budget.capped,
        nodeCount: contentSpent + budget.spent,
        totalNodes,
        contentRoot: contentDescriptor,
        contentComplete,
        refCount: renumber(tree),
        interactiveCount,
        walkErrors,
        walkError,
    };
}
"""


class SnapshotLocatorError(Exception):
    """A --locator that resolves to nothing. Falling back to the whole page is
    what made this bug invisible for so long, so it is an error instead."""


def _snapshot_hint(meta):
    """Render what the snapshot left out, or None if it left nothing out."""
    parts = []
    if meta.get("truncated"):
        node_count = meta.get("node_count") or 0
        total = meta.get("total_nodes") or 0
        root = meta.get("content_root")
        if root and meta.get("content_complete"):
            why = f"{root} complete — omitted nodes are page chrome"
        elif root:
            why = f"{root} also truncated — narrow with --locator or --search"
        else:
            why = "no content landmark found — narrow with --locator or --search"
        parts.append(f"⚠ truncated: {node_count:,} of {total:,} nodes ({why})")
    lines_kept = meta.get("lines_kept")
    if lines_kept:
        kept, total_lines = lines_kept
        parts.append(f"⚠ showing {kept:,} of {total_lines:,} lines (interactive elements only)")
    walk_errors = meta.get("walk_errors")
    if walk_errors:
        detail = meta.get("walk_error") or "unknown error"
        parts.append(f"⚠ {walk_errors:,} subtree(s) dropped by a walker error: {detail}")
    match_count = meta.get("match_count")
    if match_count is not None and match_count > meta.get("match_shown", 0):
        parts.append(f"⚠ matched {match_count:,} lines, showing {meta['match_shown']:,} — raise --limit to see more")
    return "\n".join(parts) or None


async def _take_snapshot(page, search=None, locator=None, limit=10):
    """Snapshot the page (or one locator's subtree) and report what was dropped.

    Returns `(formatted, meta)`; pass meta to `_snapshot_hint` for the notice.
    """
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass

    root_handle = None
    if locator:
        try:
            loc = page.locator(locator)
            count = await loc.count()
        except Exception as e:
            raise SnapshotLocatorError(f"Invalid locator {locator!r}: {e}")
        if count == 0:
            raise SnapshotLocatorError(f"Locator {locator!r} matched no elements on this page")
        root_handle = await loc.first.element_handle()

    try:
        result = await page.evaluate(SNAPSHOT_JS, {"root": root_handle, "search": bool(search)})
    except Exception:
        result = {
            "tree": {"role": "text", "name": "Snapshot unavailable (page too complex)"},
            "truncated": True,
            "nodeCount": 0,
        }
    finally:
        if root_handle is not None:
            try:
                await root_handle.dispose()
            except Exception:
                pass

    if not isinstance(result, dict):
        result = {"tree": result}
    tree = result.get("tree")
    meta = {
        "truncated": bool(result.get("truncated")),
        "node_count": result.get("nodeCount", 0),
        "total_nodes": result.get("totalNodes", 0),
        "content_root": result.get("contentRoot"),
        "content_complete": result.get("contentComplete", True),
        "walk_errors": result.get("walkErrors", 0),
        "walk_error": result.get("walkError", ""),
    }
    formatted = format_tree(tree) if tree else ""
    if search:
        formatted, total = match_lines(formatted, search, limit)
        meta["match_count"] = total
        meta["match_shown"] = min(total, limit)
    return formatted, meta


def _with_snapshot(resp, meta):
    """Attach the truncation notice to a response that carries a snapshot."""
    if meta.get("truncated"):
        resp["truncated"] = True
    hint = _snapshot_hint(meta)
    if hint:
        resp["hint"] = hint
    return resp


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


_REF_RE = re.compile(r"^\s*\[?(\d+)\]?\s*$")


def _resolve_selector(body):
    if hasattr(body, "ref") and body.ref is not None:
        return f'[data-brow-ref="{body.ref}"]'
    if hasattr(body, "selector") and body.selector is not None:
        m = _REF_RE.match(body.selector)
        if m:
            return f'[data-brow-ref="{m.group(1)}"]'
        return body.selector
    raise HTTPException(400, "Either 'ref' or 'selector' must be provided")


def _log_action(session, action: str, **kwargs):
    actions = session.state.setdefault("actions", [])
    entry = {"seq": len(actions) + 1, "action": action}
    entry.update({k: v for k, v in kwargs.items() if v is not None})
    actions.append(entry)


class NavigateReq(BaseModel):
    url: str
    timeout: int = DEFAULT_TIMEOUT
    wait: str = "load"


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


class ScrollUntilReq(BaseModel):
    until: str
    pixels: int = 800
    max_attempts: int = 10
    timeout: int = DEFAULT_TIMEOUT


class ClickUntilReq(BaseModel):
    selector: str
    until_gone: Optional[str] = None
    max_iterations: int = 25
    settle_ms: int = 500
    timeout: int = DEFAULT_TIMEOUT


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
    status = r.status if r else None
    if body.wait in ("load", "networkidle"):
        try:
            await page.wait_for_load_state(body.wait, timeout=min(body.timeout, 10000))
        except Exception:
            pass
    _log_action(session, "navigate", url=body.url, status=status)
    formatted, meta = await _take_snapshot(page)
    return _with_snapshot({"url": page.url, "status": status, "snapshot": formatted}, meta)


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
async def snapshot(
    req: Request,
    sid: str,
    search: Optional[str] = None,
    locator: Optional[str] = None,
    compact: bool = False,
    limit: int = 10,
):
    session = _get_session(req, sid)
    page = _get_page(session)
    try:
        formatted, meta = await _take_snapshot(page, search=search, locator=locator, limit=limit)
    except SnapshotLocatorError as e:
        raise HTTPException(400, str(e))
    lines = formatted.split("\n")
    large = len(lines) > 500
    if (compact or large) and not search:
        interactive_lines = [ln for ln in lines if "[" in ln and "]" in ln]
        context_lines = [ln for ln in lines if any(k in ln for k in ("heading", "navigation", "main", "form"))]
        kept = list(dict.fromkeys(interactive_lines + context_lines))[:300]
        header = f"[Showing {len(kept)} of {len(lines)} lines — use --search <regex> to filter]\n"
        formatted = header + "\n".join(kept)
        meta["truncated"] = True
        meta["lines_kept"] = (len(kept), len(lines))
    return _with_snapshot({"tree": formatted}, meta)


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


_STATIC_PREFIXES = ("image/", "font/", "text/css", "application/javascript", "text/javascript", "application/font")


@router.get("/network")
async def get_network(
    req: Request,
    sid: str,
    search: Optional[str] = None,
    count: int = 50,
    include_static: bool = False,
    include_response: bool = False,
):
    import re

    session = _get_session(req, sid)
    reqs = session.state.get("network_requests", [])
    if not include_static:
        reqs = [r for r in reqs if not any(r["type"].startswith(p) for p in _STATIC_PREFIXES)]
    if search:
        pattern = re.compile(search)
        reqs = [r for r in reqs if pattern.search(r["url"]) or pattern.search(r["type"])]
    reqs = reqs[-count:]
    lines = []
    for r in reqs:
        line = f"{r['method']:<6} {r['status']}  {r['type']:<30} {r['url']}"
        if include_response and r.get("response_preview"):
            line += f"\n    {r['response_preview'][:200]}"
        lines.append(line)
    return {"network": "\n".join(lines)}


@router.delete("/network")
async def clear_network(req: Request, sid: str):
    session = _get_session(req, sid)
    session.state["network_requests"] = []
    return {"ok": True}


class FetchReq(BaseModel):
    url: str
    method: str = "GET"
    headers: Optional[dict] = None
    body: Optional[str] = None
    no_cookies: bool = False


@router.post("/fetch")
async def fetch_url(req: Request, sid: str, body: FetchReq):
    session = _get_session(req, sid)
    if body.no_cookies:
        import httpx

        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            r = await client.request(
                body.method,
                body.url,
                headers=body.headers or {},
                content=body.body,
            )
        result = {"status": r.status_code, "contentType": r.headers.get("content-type", ""), "body": r.text}
        _log_action(session, "fetch", url=body.url, method=body.method, no_cookies=True, status=r.status_code)
        return result
    page = _get_page(session)
    js = """
async ({url, method, headers, body}) => {
    const opts = {method, headers: headers || {}};
    if (body) opts.body = body;
    const r = await fetch(url, opts);
    const text = await r.text();
    return {status: r.status, contentType: r.headers.get('content-type') || '', body: text};
}
"""
    result = await page.evaluate(
        js, {"url": body.url, "method": body.method, "headers": body.headers or {}, "body": body.body}
    )
    _log_action(session, "fetch", url=body.url, method=body.method, no_cookies=False, status=result.get("status"))
    return result


@router.get("/websocket")
async def get_websocket(req: Request, sid: str, search: Optional[str] = None, count: int = 50):
    session = _get_session(req, sid)
    msgs = session.state.get("websocket_messages", [])[-count:]
    lines = [f"{m['direction'].upper():<4}  {m['url']}\n      {m['data'][:200]}" for m in msgs]
    text = "\n".join(lines)
    if search:
        text = filter_lines(text, search)
    return {"websocket": text}


@router.delete("/websocket")
async def clear_websocket(req: Request, sid: str):
    session = _get_session(req, sid)
    session.state["websocket_messages"] = []
    return {"ok": True}


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
            _log_action(session, "click", selector=selector)
            # Wait for navigation if it occurs; otherwise sleep briefly to allow
            # hash-routing / JS DOM mutations to settle before snapshotting.
            try:
                await page.wait_for_load_state("load", timeout=300)
            except Exception:
                await aio.sleep(0.15)
            formatted, meta = await _take_snapshot(page)
            return _with_snapshot({"ok": True, "snapshot": formatted}, meta)
        except Exception as e:
            last_error = e
            if attempt < attempts - 1:
                await aio.sleep(1)

    raise HTTPException(
        500, f"Failed to click selector '{selector}' after {attempts} attempts. Last error: {str(last_error)}"
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
            _log_action(session, "fill", selector=selector)
            formatted, meta = await _take_snapshot(page)
            return _with_snapshot({"ok": True, "snapshot": formatted}, meta)
        except Exception as e:
            last_error = e
            if attempt < attempts - 1:
                await aio.sleep(1)

    raise HTTPException(
        500, f"Failed to fill selector '{selector}' after {attempts} attempts. Last error: {str(last_error)}"
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
    _log_action(session, "key", key=body.key)
    formatted, meta = await _take_snapshot(page)
    return _with_snapshot({"ok": True, "snapshot": formatted}, meta)


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


@router.post("/scroll-until")
async def scroll_until(req: Request, sid: str, body: ScrollUntilReq):
    session = _get_session(req, sid)
    page = _get_page(session)
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


@router.post("/click-until")
async def click_until(req: Request, sid: str, body: ClickUntilReq):
    """Click a selector repeatedly until the work runs out.

    Bulk UI work is nearly always this shape: act on the visible batch, the list
    refills, act again. Driving that from outside costs a process launch plus an
    HTTP round trip per iteration and needs hand-written stop conditions, so this
    keeps the loop next to the browser.

    Stops on `until_gone` disappearing, on the clickable itself vanishing, or on
    max_iterations. `done` distinguishes "finished" from "gave up", and `reason`
    says which, so a truncated sweep is never mistaken for a complete one.
    """
    session = _get_session(req, sid)
    page = _get_page(session)

    iterations = 0
    reason = "until_gone cleared"
    done = False

    for _ in range(body.max_iterations):
        if body.until_gone:
            try:
                if await page.locator(body.until_gone).count() == 0:
                    done = True
                    break
            except Exception as e:
                raise HTTPException(400, f"Invalid until_gone selector '{body.until_gone}': {e}")

        target = page.locator(body.selector)
        try:
            if await target.count() == 0:
                done = True
                reason = "clickable is gone"
                break
        except Exception as e:
            raise HTTPException(400, f"Invalid selector '{body.selector}': {e}")

        try:
            await target.first.click(timeout=body.timeout)
        except Exception as e:
            # Report progress made so far rather than losing it to an exception.
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

    _log_action(session, "click-until", selector=body.selector, iterations=iterations)
    return {"ok": True, "done": done, "iterations": iterations, "reason": reason}


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
    _log_action(session, "select", selector=selector, value=body.value)
    formatted, meta = await _take_snapshot(page)
    return _with_snapshot({"ok": True, "snapshot": formatted}, meta)


@router.post("/upload")
async def upload(req: Request, sid: str, body: UploadReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    await page.set_input_files(body.selector, body.filepath)
    _log_action(session, "upload", selector=body.selector, filepath=body.filepath)
    return {"ok": True}


@router.get("/actions")
async def get_actions(req: Request, sid: str, as_json: bool = False):
    session = _get_session(req, sid)
    actions = session.state.get("actions", [])
    if as_json:
        return {"actions": actions}
    lines = []
    for a in actions:
        s, act = a["seq"], a["action"]
        if act == "navigate":
            lines.append(f"{s:<3} navigate  {a.get('url', '')}  [{a.get('status', '')}]")
        elif act == "fetch":
            nc = " --no-cookies" if a.get("no_cookies") else ""
            lines.append(f"{s:<3} fetch     {a.get('url', '')}  [{a.get('status', '')}]{nc}")
        elif act == "click":
            lines.append(f"{s:<3} click     {a.get('selector', '')}")
        elif act == "fill":
            lines.append(f"{s:<3} fill      {a.get('selector', '')}  value=<redacted>")
        elif act == "key":
            lines.append(f"{s:<3} key       {a.get('key', '')}")
        elif act == "select":
            lines.append(f"{s:<3} select    {a.get('selector', '')}  value={a.get('value', '')!r}")
        elif act == "upload":
            lines.append(f"{s:<3} upload    {a.get('selector', '')}  file={a.get('filepath', '')}")
        else:
            lines.append(f"{s:<3} {act}")
    return {"actions": "\n".join(lines)}


@router.delete("/actions")
async def clear_actions(req: Request, sid: str):
    session = _get_session(req, sid)
    session.state["actions"] = []
    return {"ok": True}


class ReplayReq(BaseModel):
    playbook: dict
    vars: dict = Field(default_factory=dict)


_PLAYBOOK_FIELDS = {"name", "description", "base_url", "auth", "vars", "steps", "stop_on_failure"}
_REPLAY_AUTH_MODES = {"none", "browser-session", "browser"}
_REPLAY_STATES = {"visible", "hidden", "attached", "detached"}
_STEP_FIELDS = {
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


def _replay_validation_error(path: str, message: str):
    raise HTTPException(status_code=422, detail=f"{path}: {message}")


def _require_replay_type(value, expected_type, path: str):
    if expected_type is int:
        valid = isinstance(value, int) and not isinstance(value, bool)
    else:
        valid = isinstance(value, expected_type)
    if not valid:
        _replay_validation_error(path, f"must be {expected_type.__name__}")


def _validate_replay_steps(steps, path: str = "steps"):
    if not isinstance(steps, list):
        _replay_validation_error(path, "must be a list")

    for index, step in enumerate(steps):
        step_path = f"{path}[{index}]"
        if not isinstance(step, dict):
            _replay_validation_error(step_path, "must be an object")
        if "action" not in step:
            _replay_validation_error(f"{step_path}.action", "is required")
        action = step["action"]
        if not isinstance(action, str) or action not in _STEP_FIELDS:
            _replay_validation_error(f"{step_path}.action", f"unknown action {action!r}")

        required, optional = _STEP_FIELDS[action]
        allowed = {"action", "note", *required, *optional}
        unknown = set(step) - allowed
        if unknown:
            field = sorted(unknown)[0]
            _replay_validation_error(f"{step_path}.{field}", "is not supported")
        missing = required - set(step)
        if missing:
            field = sorted(missing)[0]
            _replay_validation_error(f"{step_path}.{field}", "is required")

        for field in required & {"url", "selector", "value", "key", "var"}:
            _require_replay_type(step[field], str, f"{step_path}.{field}")
        if "note" in step:
            _require_replay_type(step["note"], str, f"{step_path}.note")
        if "timeout" in step:
            _require_replay_type(step["timeout"], int, f"{step_path}.timeout")
            if step["timeout"] < 0:
                _replay_validation_error(f"{step_path}.timeout", "must be non-negative")
        if "state" in step:
            _require_replay_type(step["state"], str, f"{step_path}.state")
            if step["state"] not in _REPLAY_STATES:
                _replay_validation_error(f"{step_path}.state", f"must be one of {sorted(_REPLAY_STATES)}")

        if action == "wait":
            has_selector = "selector" in step
            has_ms = "ms" in step
            if has_selector == has_ms:
                _replay_validation_error(step_path, "must contain exactly one of selector or ms")
            if has_selector:
                _require_replay_type(step["selector"], str, f"{step_path}.selector")
            if has_ms:
                _require_replay_type(step["ms"], int, f"{step_path}.ms")
                if step["ms"] < 0:
                    _replay_validation_error(f"{step_path}.ms", "must be non-negative")
            if "state" in step and not has_selector:
                _replay_validation_error(f"{step_path}.state", "requires selector")
        elif action == "fetch":
            if "method" in step:
                _require_replay_type(step["method"], str, f"{step_path}.method")
            if "headers" in step:
                _require_replay_type(step["headers"], dict, f"{step_path}.headers")
                for key, value in step["headers"].items():
                    if not isinstance(key, str) or not isinstance(value, str):
                        _replay_validation_error(f"{step_path}.headers", "keys and values must be strings")
            if "auth" in step:
                _require_replay_type(step["auth"], str, f"{step_path}.auth")
                if step["auth"] not in _REPLAY_AUTH_MODES:
                    _replay_validation_error(f"{step_path}.auth", f"must be one of {sorted(_REPLAY_AUTH_MODES)}")
            if "output" in step:
                _require_replay_type(step["output"], str, f"{step_path}.output")
            if "expect_status" in step:
                statuses = step["expect_status"]
                if not isinstance(statuses, list) or any(
                    not isinstance(status, int) or isinstance(status, bool) or not 100 <= status <= 599
                    for status in statuses
                ):
                    _replay_validation_error(f"{step_path}.expect_status", "must be a list of HTTP status integers")
        elif action == "for_each":
            items = step["items"]
            if not isinstance(items, (str, list)):
                _replay_validation_error(f"{step_path}.items", "must be a variable name or list")
            _validate_replay_steps(step["steps"], f"{step_path}.steps")


def _validate_playbook(playbook: dict):
    unknown = set(playbook) - _PLAYBOOK_FIELDS
    if unknown:
        field = sorted(unknown)[0]
        _replay_validation_error(field, "is not supported")
    if "steps" not in playbook:
        _replay_validation_error("steps", "is required")
    for field in ("name", "description", "base_url"):
        if field in playbook:
            _require_replay_type(playbook[field], str, field)
    if "auth" in playbook:
        _require_replay_type(playbook["auth"], str, "auth")
        if playbook["auth"] not in _REPLAY_AUTH_MODES:
            _replay_validation_error("auth", f"must be one of {sorted(_REPLAY_AUTH_MODES)}")
    if "vars" in playbook:
        _require_replay_type(playbook["vars"], dict, "vars")
    if "stop_on_failure" in playbook:
        _require_replay_type(playbook["stop_on_failure"], bool, "stop_on_failure")
    _validate_replay_steps(playbook["steps"])


def _sub(val, variables):
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


async def _run_replay_steps(page, session, steps, variables, base_url, stop_on_failure=False, default_auth=None):
    def sub(val):
        return _sub(val, variables)

    def resolve_url(u):
        u = sub(u)
        return u if u.startswith("http") else base_url + u

    results = []
    for step in steps:
        act = step["action"]
        entry = {"action": act, "ok": False}
        try:
            if act == "navigate":
                url = resolve_url(step["url"])
                r = await page.goto(url, timeout=step.get("timeout", 30000))
                entry.update({"url": url, "status": r.status if r else None, "ok": True})
                _log_action(session, "navigate", url=url, status=r.status if r else None)
            elif act == "click":
                await page.click(sub(step["selector"]))
                _log_action(session, "click", selector=sub(step["selector"]))
                entry["ok"] = True
            elif act == "fill":
                await page.fill(sub(step["selector"]), sub(step["value"]))
                _log_action(session, "fill", selector=sub(step["selector"]))
                entry["ok"] = True
            elif act == "key":
                await page.keyboard.press(sub(step["key"]))
                _log_action(session, "key", key=sub(step["key"]))
                entry["ok"] = True
            elif act == "select":
                await page.select_option(sub(step["selector"]), sub(step["value"]))
                _log_action(session, "select", selector=sub(step["selector"]), value=sub(step["value"]))
                entry["ok"] = True
            elif act == "fetch":
                url = resolve_url(step["url"])
                method = step.get("method", "GET")
                no_cookies = step.get("auth", default_auth) == "none"
                headers = {k: sub(v) for k, v in step.get("headers", {}).items()}
                if no_cookies:
                    import httpx

                    async with httpx.AsyncClient(follow_redirects=True, timeout=30, headers=headers) as client:
                        r = await client.request(method, url)
                    data_text, status = r.text, r.status_code
                else:
                    js = (
                        "async ({url,method,headers})=>{"
                        "const r=await fetch(url,{method,headers});"
                        "return {status:r.status,body:await r.text()}}"
                    )
                    r = await page.evaluate(js, {"url": url, "method": method, "headers": headers})
                    data_text, status = r["body"], r["status"]
                _log_action(session, "fetch", url=url, method=method, no_cookies=no_cookies, status=status)
                expect_status = step.get("expect_status")
                ok = status in expect_status if expect_status else status < 400
                entry.update({"url": url, "status": status, "ok": ok})
                if not ok:
                    entry["error"] = f"HTTP {status}"
                if step.get("output"):
                    import json as _json

                    try:
                        data = _json.loads(data_text)
                    except Exception:
                        data = data_text
                    entry["data"] = data
                    variables[step["output"]] = data
            elif act == "wait":
                if step.get("selector"):
                    await page.wait_for_selector(
                        sub(step["selector"]), state=step.get("state", "visible"), timeout=step.get("timeout", 30000)
                    )
                else:
                    await page.wait_for_timeout(step.get("ms", 1000))
                entry["ok"] = True
            elif act == "assert":
                await page.wait_for_selector(
                    sub(step["selector"]), state=step.get("state", "visible"), timeout=step.get("timeout", 5000)
                )
                entry["ok"] = True
            elif act == "for_each":
                var = step["var"]
                items = step["items"]
                if isinstance(items, str):
                    if items not in variables:
                        raise ValueError(f"for_each items variable {items!r} is not defined")
                    items = variables[items]
                if not isinstance(items, list):
                    raise TypeError(f"for_each items must resolve to a list, got {type(items).__name__}")
                nested_failed = False
                for item in items:
                    variables[var] = item
                    nested_results = await _run_replay_steps(
                        page, session, step["steps"], variables, base_url, stop_on_failure, default_auth
                    )
                    results.extend(nested_results)
                    if stop_on_failure and any(not r["ok"] for r in nested_results):
                        nested_failed = True
                        break
                variables.pop(var, None)
                if nested_failed:
                    break
                continue
            else:
                entry["error"] = f"unknown action: {act!r}"
        except Exception as e:
            entry["error"] = str(e)
        results.append(entry)
        if not entry["ok"] and stop_on_failure:
            break
    return results


@router.post("/replay")
async def replay(req: Request, sid: str, body: ReplayReq):
    _validate_playbook(body.playbook)
    session = _get_session(req, sid)
    page = _get_page(session)
    base_url = body.playbook.get("base_url", "")
    variables = {**body.playbook.get("vars", {}), **body.vars}

    results = await _run_replay_steps(
        page,
        session,
        body.playbook.get("steps", []),
        variables,
        base_url,
        stop_on_failure=bool(body.playbook.get("stop_on_failure")),
        default_auth=body.playbook.get("auth"),
    )
    return {"results": results}
