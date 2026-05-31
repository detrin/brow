import re


def _format_table(tree, indent=0):
    prefix = "  " * indent
    headers = tree.get("headers", [])
    rows = tree.get("rows", [])
    total = tree.get("totalRows", len(rows))
    lines = []

    if headers:
        lines.append(prefix + "| " + " | ".join(headers) + " |")
        lines.append(prefix + "| " + " | ".join("---" for _ in headers) + " |")

    for row in rows:
        lines.append(prefix + "| " + " | ".join(row) + " |")

    if total > len(rows):
        lines.append(prefix + f"... ({total - len(rows)} more rows)")

    return "\n".join(lines)


def _format_inline_list(tree, indent=0):
    prefix = "  " * indent
    parts = []
    for item in tree.get("items", []):
        ref = item.get("ref")
        name = item.get("name", "")
        piece = f'[{ref}] "{name}"' if ref is not None else f'"{name}"'
        parts.append(piece)
    item_role = tree.get("itemRole", "item")
    return prefix + item_role + ": " + " | ".join(parts)


def format_tree(tree, indent=0):
    if not tree:
        return ""
    lines = []
    role = tree.get("role", "")
    name = tree.get("name", "")
    children = tree.get("children", [])

    # Table-aware: render as markdown table
    if role == "table" and "headers" in tree:
        return _format_table(tree, indent)

    # Inline list: render same-type simple children on one line
    if role == "inline-list" and "items" in tree:
        return _format_inline_list(tree, indent)

    if role == "group" and not name:
        for child in children:
            lines.append(format_tree(child, indent))
        return "\n".join(lines)

    ref = tree.get("ref")
    parts = []
    if ref is not None:
        parts.append(f"[{ref}]")
    parts.append(role)
    if name:
        parts.append(f'"{name}"')
    for key in ("value", "checked", "disabled", "href", "level"):
        if key in tree:
            v = tree[key]
            parts.append(f"{key}={v}" if not isinstance(v, str) else f'{key}="{v}"')

    prefix = "  " * indent
    lines.append(f"{prefix}{' '.join(parts)}")
    for child in children:
        lines.append(format_tree(child, indent + 1))
    return "\n".join(lines)


def filter_lines(text, pattern, limit=10):
    regex = re.compile(pattern)
    matches = [line for line in text.split("\n") if regex.search(line)]
    return "\n".join(matches[:limit])
