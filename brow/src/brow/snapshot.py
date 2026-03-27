import re

def format_tree(tree, indent=0):
    if not tree:
        return ""
    lines = []
    role = tree.get("role", "")
    name = tree.get("name", "")
    children = tree.get("children", [])

    if role == "group" and not name:
        for child in children:
            lines.append(format_tree(child, indent))
        return "\n".join(lines)

    parts = [role]
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
    matches = [l for l in text.split("\n") if regex.search(l)]
    return "\n".join(matches[:limit])
