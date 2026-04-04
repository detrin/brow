import asyncio
import subprocess

AGENT_BROWSER_TOOLS = [
    {
        "name": "ab_open",
        "description": "Navigate to a URL. Starts the browser daemon if not running.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "ab_snapshot",
        "description": "Get the accessibility tree of the current page with element refs (@e1, @e2, ...). Use this to understand page content and find interactive elements.",
        "input_schema": {
            "type": "object",
            "properties": {
                "interactive_only": {"type": "boolean", "default": True, "description": "Return only interactive elements"},
            },
        },
    },
    {
        "name": "ab_click",
        "description": "Click an element by its ref from snapshot (e.g. @e3).",
        "input_schema": {
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Element ref from snapshot, e.g. @e3"},
            },
            "required": ["ref"],
        },
    },
    {
        "name": "ab_fill",
        "description": "Fill an input field by its ref from snapshot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Element ref from snapshot, e.g. @e2"},
                "value": {"type": "string"},
            },
            "required": ["ref", "value"],
        },
    },
    {
        "name": "ab_select",
        "description": "Select an option from a dropdown by its ref.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ref": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["ref", "value"],
        },
    },
    {
        "name": "ab_press",
        "description": "Press a key (Enter, Tab, Escape, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
            },
            "required": ["key"],
        },
    },
    {
        "name": "ab_scroll",
        "description": "Scroll the page up or down.",
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["up", "down"], "default": "down"},
                "pixels": {"type": "integer", "default": 500},
            },
        },
    },
    {
        "name": "ab_eval",
        "description": "Execute JavaScript in the browser and return the result.",
        "input_schema": {
            "type": "object",
            "properties": {
                "javascript": {"type": "string"},
            },
            "required": ["javascript"],
        },
    },
    {
        "name": "ab_wait",
        "description": "Wait for an element, text, or URL pattern to appear.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector to wait for"},
                "text": {"type": "string", "description": "Text to wait for on the page"},
                "ms": {"type": "integer", "description": "Wait for a fixed number of milliseconds"},
            },
        },
    },
]


async def _run(args):
    cmd = ["agent-browser"] + args
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode != 0:
            return {"error": stderr.decode().strip() or f"Exit code {proc.returncode}"}
        return {"output": stdout.decode().strip()}
    except asyncio.TimeoutError:
        proc.kill()
        return {"error": "Command timed out after 60s"}
    except Exception as e:
        return {"error": str(e)}


async def execute_agent_browser_tool(name, params):
    cmd_map = {
        "ab_open": lambda p: ["open", p["url"]],
        "ab_snapshot": lambda p: ["snapshot", "-i"] if p.get("interactive_only", True) else ["snapshot"],
        "ab_click": lambda p: ["click", p["ref"]],
        "ab_fill": lambda p: ["fill", p["ref"], p["value"]],
        "ab_select": lambda p: ["select", p["ref"], p["value"]],
        "ab_press": lambda p: ["press", p["key"]],
        "ab_scroll": lambda p: ["scroll", p.get("direction", "down"), str(p.get("pixels", 500))],
        "ab_eval": lambda p: ["eval", p["javascript"]],
        "ab_wait": lambda p: (
            ["wait", "--text", p["text"]] if p.get("text")
            else ["wait", str(p["ms"])] if p.get("ms")
            else ["wait", p["selector"]]
        ),
    }
    builder = cmd_map.get(name)
    if not builder:
        return {"error": f"Unknown tool: {name}"}
    return await _run(builder(params))


def cleanup_agent_browser():
    try:
        subprocess.run(["agent-browser", "close", "--all"], capture_output=True, timeout=10)
    except Exception:
        pass
