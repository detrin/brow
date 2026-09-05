import re
from functools import lru_cache
from importlib.resources import files


class SnapshotLocatorError(Exception):
    pass


@lru_cache(maxsize=1)
def snapshot_js():
    return files("brow").joinpath("snapshot.js").read_text()


def _format_table(tree, indent=0):
    prefix = "  " * indent
    headers = tree.get("headers", [])
    rows = tree.get("rows", [])
    total = tree.get("totalRows", len(rows))
    lines = []
    if headers:
        lines.append(prefix + "| " + " | ".join(headers) + " |")
        lines.append(prefix + "| " + " | ".join("---" for _ in headers) + " |")
    lines.extend(prefix + "| " + " | ".join(row) + " |" for row in rows)
    if total > len(rows):
        lines.append(prefix + f"... ({total - len(rows)} more rows)")
    return "\n".join(lines)


def _format_inline_list(tree, indent=0):
    parts = []
    for item in tree.get("items", []):
        ref, name = item.get("ref"), item.get("name", "")
        parts.append(f'[{ref}] "{name}"' if ref is not None else f'"{name}"')
    return "  " * indent + tree.get("itemRole", "item") + ": " + " | ".join(parts)


def format_tree(tree, indent=0):
    if not tree:
        return ""
    role = tree.get("role", "")
    name = tree.get("name", "")
    children = tree.get("children", [])

    if role == "table" and "headers" in tree:
        return _format_table(tree, indent)
    if role == "inline-list" and "items" in tree:
        return _format_inline_list(tree, indent)
    if role == "group" and not name:
        return "\n".join(format_tree(child, indent) for child in children)

    parts = []
    ref = tree.get("ref")
    if ref is not None:
        parts.append(f"[{ref}]")
    parts.append(role)
    if name:
        parts.append(f'"{name}"')
    for key in ("value", "checked", "disabled", "href", "level"):
        if key in tree:
            v = tree[key]
            parts.append(f'{key}="{v}"' if isinstance(v, str) else f"{key}={v}")

    lines = ["  " * indent + " ".join(parts)]
    lines.extend(format_tree(child, indent + 1) for child in children)
    return "\n".join(lines)


def match_lines(text, pattern, limit=10):
    regex = re.compile(pattern)
    matches = [line for line in text.split("\n") if regex.search(line)]
    return "\n".join(matches[:limit]), len(matches)


def filter_lines(text, pattern, limit=10):
    return match_lines(text, pattern, limit)[0]


def snapshot_hint(meta):
    parts = []
    if meta.get("truncated"):
        root = meta.get("content_root")
        if root and meta.get("content_complete"):
            why = f"{root} complete — omitted nodes are page chrome"
        elif root:
            why = f"{root} also truncated — narrow with --locator or --search"
        else:
            why = "no content landmark found — narrow with --locator or --search"
        parts.append(f"⚠ truncated: {meta.get('node_count') or 0:,} of {meta.get('total_nodes') or 0:,} nodes ({why})")
    if meta.get("lines_kept"):
        kept, total = meta["lines_kept"]
        parts.append(f"⚠ showing {kept:,} of {total:,} lines (interactive elements only)")
    if meta.get("walk_errors"):
        detail = meta.get("walk_error") or "unknown error"
        parts.append(f"⚠ {meta['walk_errors']:,} subtree(s) dropped by a walker error: {detail}")
    matched = meta.get("match_count")
    if matched is not None and matched > meta.get("match_shown", 0):
        parts.append(f"⚠ matched {matched:,} lines, showing {meta['match_shown']:,} — raise --limit to see more")
    return "\n".join(parts) or None


def with_snapshot(resp, meta):
    if meta.get("truncated"):
        resp["truncated"] = True
    hint = snapshot_hint(meta)
    if hint:
        resp["hint"] = hint
    return resp


async def _locator_handle(page, locator):
    try:
        loc = page.locator(locator)
        count = await loc.count()
    except Exception as e:
        raise SnapshotLocatorError(f"Invalid locator {locator!r}: {e}")
    if count == 0:
        raise SnapshotLocatorError(f"Locator {locator!r} matched no elements on this page")
    return await loc.first.element_handle()


async def take_snapshot(page, search=None, locator=None, limit=10):
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass

    root_handle = await _locator_handle(page, locator) if locator else None
    try:
        result = await page.evaluate(snapshot_js(), {"root": root_handle, "search": bool(search)})
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
    meta = {
        "truncated": bool(result.get("truncated")),
        "node_count": result.get("nodeCount", 0),
        "total_nodes": result.get("totalNodes", 0),
        "content_root": result.get("contentRoot"),
        "content_complete": result.get("contentComplete", True),
        "walk_errors": result.get("walkErrors", 0),
        "walk_error": result.get("walkError", ""),
    }
    tree = result.get("tree")
    formatted = format_tree(tree) if tree else ""
    if search:
        formatted, total = match_lines(formatted, search, limit)
        meta["match_count"] = total
        meta["match_shown"] = min(total, limit)
    return formatted, meta
