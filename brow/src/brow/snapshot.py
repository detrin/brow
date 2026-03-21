import re

def format_tree(tree, indent=0):
    if not tree:
        return ""
    lines = []
    prefix = "  " * indent
    role = tree.get("role", "")
    name = tree.get("name", "")
    extras = ""
    if "level" in tree:
        extras += f" level={tree['level']}"
    if "value" in tree:
        extras += f" value=\"{tree['value']}\""
    if "checked" in tree:
        extras += f" checked={tree['checked']}"
    line = f"{prefix}{role}"
    if name:
        line += f" \"{name}\""
    if extras:
        line += extras
    lines.append(line)
    for child in tree.get("children", []):
        lines.append(format_tree(child, indent + 1))
    return "\n".join(lines)

def filter_lines(text, pattern, limit=10):
    regex = re.compile(pattern)
    matches = [l for l in text.split("\n") if regex.search(l)]
    return "\n".join(matches[:limit])
