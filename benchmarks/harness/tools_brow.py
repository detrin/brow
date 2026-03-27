import subprocess
import json
import uuid

BROW_TOOLS = [
    {
        "name": "brow_session_new",
        "description": "Start a new browser session. Optionally navigate to a URL. Returns session ID and initial page snapshot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to navigate to after creating the session"},
                "headed": {"type": "boolean", "default": False},
            },
        },
    },
    {
        "name": "brow_snapshot",
        "description": "Get the accessibility tree of the current page. Fast and token-efficient way to understand page content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "search": {"type": "string", "description": "Regex to filter snapshot lines"},
            },
            "required": ["session"],
        },
    },
    {
        "name": "brow_click",
        "description": "Click an element by ref number (from snapshot) or CSS/text selector. Returns updated snapshot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "ref": {"type": "integer", "description": "Element ref number from snapshot (preferred)"},
                "selector": {"type": "string", "description": "CSS or text selector (fallback)"},
            },
            "required": ["session"],
        },
    },
    {
        "name": "brow_fill",
        "description": "Fill an input field by ref number or selector. Returns updated snapshot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "ref": {"type": "integer", "description": "Element ref number from snapshot (preferred)"},
                "selector": {"type": "string", "description": "CSS or text selector (fallback)"},
                "value": {"type": "string"},
            },
            "required": ["session", "value"],
        },
    },
    {
        "name": "brow_select",
        "description": "Select an option from a dropdown by ref number or selector. Returns updated snapshot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "ref": {"type": "integer", "description": "Element ref number from snapshot (preferred)"},
                "selector": {"type": "string", "description": "CSS or text selector (fallback)"},
                "value": {"type": "string"},
            },
            "required": ["session", "value"],
        },
    },
    {
        "name": "brow_scroll",
        "description": "Scroll the page by pixels or to a selector.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "pixels": {"type": "integer"},
                "selector": {"type": "string"},
            },
            "required": ["session"],
        },
    },
]


def _ref_or_selector(p):
    if p.get("ref") is not None:
        return ["--ref", str(p["ref"])]
    return [p["selector"]]


def _build_brow_cmd(name, params):
    def _cmd(subcmd, p, *args):
        return ["brow", subcmd, "-s", p["session"]] + list(args)

    cmd_map = {
        "brow_session_new": lambda p: (
            ["brow", "session", "new"]
            + (["--headed"] if p.get("headed") else [])
            + ["--profile", f"bench-{uuid.uuid4().hex[:8]}"]
            + (["--url", p["url"]] if p.get("url") else [])
        ),
        "brow_snapshot": lambda p: _cmd("snapshot", p) + (["--search", p["search"]] if p.get("search") else []),
        "brow_click": lambda p: ["brow", "click", "-s", p["session"]] + _ref_or_selector(p),
        # When using --ref, pass "_" as dummy selector so Typer parses value as the 2nd positional
        "brow_fill": lambda p: ["brow", "fill", "-s", p["session"]] + (["_", p["value"], "--ref", str(p["ref"])] if p.get("ref") else [p["selector"], p["value"]]),
        "brow_select": lambda p: ["brow", "select", "-s", p["session"]] + (["_", p["value"], "--ref", str(p["ref"])] if p.get("ref") else [p["selector"], p["value"]]),
        "brow_scroll": lambda p: (
            ["brow", "scroll-to", "-s", p["session"], p["selector"]]
            if p.get("selector")
            else ["brow", "scroll", "-s", p["session"], str(p.get("pixels", 0))]
        ),
    }
    builder = cmd_map.get(name)
    if not builder:
        return None
    return builder(params)


async def execute_brow_tool(name, params):
    import asyncio
    cmd = _build_brow_cmd(name, params)
    if cmd is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode != 0:
            return {"error": stderr.decode().strip() or f"Exit code {proc.returncode}"}
        output = stdout.decode().strip()
        if name == "brow_session_new" and "\n" in output:
            lines = output.split("\n", 1)
            return {"output": lines[0].strip(), "snapshot": lines[1].strip()}
        return {"output": output}
    except asyncio.TimeoutError:
        proc.kill()
        return {"error": "Command timed out after 60s"}
    except Exception as e:
        return {"error": str(e)}
