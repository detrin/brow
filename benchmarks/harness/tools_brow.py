import subprocess
import json

BROW_TOOLS = [
    {
        "name": "brow_session_new",
        "description": "Start a new browser session. Returns session ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "profile": {"type": "string", "default": "benchmark"},
                "headed": {"type": "boolean", "default": False},
            },
        },
    },
    {
        "name": "brow_navigate",
        "description": "Navigate to a URL.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "url": {"type": "string"},
            },
            "required": ["session", "url"],
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
        "description": "Click an element. Selectors: CSS (#id, .class), text (text=Click Me), role (role=button[name='Save']).",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "selector": {"type": "string"},
            },
            "required": ["session", "selector"],
        },
    },
    {
        "name": "brow_fill",
        "description": "Fill an input field with a value.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "selector": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["session", "selector", "value"],
        },
    },
    {
        "name": "brow_type",
        "description": "Type text with keyboard.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "text": {"type": "string"},
            },
            "required": ["session", "text"],
        },
    },
    {
        "name": "brow_key",
        "description": "Press a key (Enter, Tab, Escape, etc).",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "key": {"type": "string"},
            },
            "required": ["session", "key"],
        },
    },
    {
        "name": "brow_screenshot",
        "description": "Take a screenshot of the current page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "quality": {"type": "string", "enum": ["low", "medium", "high"]},
            },
            "required": ["session"],
        },
    },
    {
        "name": "brow_wait",
        "description": "Wait for a selector to appear or page to load.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "selector": {"type": "string"},
                "load": {"type": "boolean"},
            },
            "required": ["session"],
        },
    },
    {
        "name": "brow_url",
        "description": "Get the current page URL.",
        "input_schema": {
            "type": "object",
            "properties": {"session": {"type": "string"}},
            "required": ["session"],
        },
    },
    {
        "name": "brow_html",
        "description": "Get page HTML content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "locator": {"type": "string"},
            },
            "required": ["session"],
        },
    },
    {
        "name": "brow_select",
        "description": "Select an option from a dropdown.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "selector": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["session", "selector", "value"],
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
    {
        "name": "brow_hover",
        "description": "Hover over an element.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "selector": {"type": "string"},
            },
            "required": ["session", "selector"],
        },
    },
]

def execute_brow_tool(name, params):
    cmd_map = {
        "brow_session_new": lambda p: ["brow", "session", "new"] + (["--headed"] if p.get("headed") else []) + (["--profile", p.get("profile", "benchmark")]),
        "brow_navigate": lambda p: ["brow", "-s", p["session"], "navigate", p["url"]],
        "brow_snapshot": lambda p: ["brow", "-s", p["session"], "snapshot"] + (["--search", p["search"]] if p.get("search") else []),
        "brow_click": lambda p: ["brow", "-s", p["session"], "click", p["selector"]],
        "brow_fill": lambda p: ["brow", "-s", p["session"], "fill", p["selector"], p["value"]],
        "brow_type": lambda p: ["brow", "-s", p["session"], "type", p["text"]],
        "brow_key": lambda p: ["brow", "-s", p["session"], "key", p["key"]],
        "brow_screenshot": lambda p: ["brow", "-s", p["session"], "screenshot"] + (["--quality", p["quality"]] if p.get("quality") else []),
        "brow_wait": lambda p: ["brow", "-s", p["session"], "wait"] + ([p["selector"]] if p.get("selector") else []) + (["--load"] if p.get("load") else []),
        "brow_url": lambda p: ["brow", "-s", p["session"], "url"],
        "brow_html": lambda p: ["brow", "-s", p["session"], "html"] + (["--locator", p["locator"]] if p.get("locator") else []),
        "brow_select": lambda p: ["brow", "-s", p["session"], "eval", "await page.select_option(" + json.dumps(p["selector"]) + ", " + json.dumps(p["value"]) + ")"],
        "brow_scroll": lambda p: (["brow", "-s", p["session"], "scroll-to", p["selector"]] if p.get("selector") else ["brow", "-s", p["session"], "scroll", str(p.get("pixels", 0))]),
        "brow_hover": lambda p: ["brow", "-s", p["session"], "hover", p["selector"]],
    }
    builder = cmd_map.get(name)
    if not builder:
        return {"error": f"Unknown tool: {name}"}
    cmd = builder(params)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return {"error": result.stderr.strip() or f"Exit code {result.returncode}"}
        return {"output": result.stdout.strip()}
    except subprocess.TimeoutExpired:
        return {"error": "Command timed out after 60s"}
    except Exception as e:
        return {"error": str(e)}
