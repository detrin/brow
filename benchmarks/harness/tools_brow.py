import asyncio
import os
import tempfile
import uuid
from pathlib import Path

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
    {
        "name": "brow_goto",
        "description": "Navigate to a URL within the existing session (preserves cookies and login state). Use this instead of brow_session_new when you need to visit a new URL mid-task.",
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
        "name": "brow_wait",
        "description": "Wait for a CSS selector to appear/become visible on the page. Use before snapshotting dynamic or JS-rendered content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "selector": {"type": "string", "description": "CSS selector to wait for"},
                "timeout": {"type": "integer", "description": "Timeout in ms (default 5000)"},
            },
            "required": ["session", "selector"],
        },
    },
    {
        "name": "brow_eval",
        "description": "Run Python code in the brow daemon. The variable `page` is a Playwright Page object. To run JavaScript in the browser use: await page.evaluate('js expression'). Do NOT use document/window directly — wrap JS in page.evaluate().",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "code": {"type": "string", "description": "Python code. Use `await page.evaluate(\"js\")` to run JS. Example: await page.evaluate(\"Array.from(document.querySelectorAll('a')).map(a => a.href)\")"},
            },
            "required": ["session", "code"],
        },
    },
    {
        "name": "brow_run",
        "description": (
            "Run a reusable Python workflow as one call against the live authenticated session. "
            "Use for bulk work, loops, branching, retries, or several related Playwright operations instead of many tool calls. "
            "Available variables: page, context, browser, state, pages, and args. Set result to return structured output."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "code": {"type": "string", "description": "Python workflow code using async Playwright APIs."},
                "args": {
                    "type": "object",
                    "description": "Optional string arguments exposed to the workflow as args.",
                    "additionalProperties": {"type": "string"},
                },
                "timeout": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 300000,
                    "description": "Maximum workflow time in milliseconds.",
                },
            },
            "required": ["session", "code"],
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
            else ["brow", "scroll", "-s", p["session"], "--pixels", str(p.get("pixels", 0))]
        ),
        "brow_goto": lambda p: ["brow", "navigate", "-s", p["session"], p["url"]],
        "brow_wait": lambda p: ["brow", "wait", "-s", p["session"], "--selector", p["selector"]]
            + (["--timeout", str(p["timeout"])] if p.get("timeout") else []),
        "brow_eval": lambda p: ["brow", "eval", "-s", p["session"], p["code"]],
        "brow_run": lambda p: (
            ["brow", "run", "-s", p["session"], p["_script_path"]]
            + [item for key, value in p.get("args", {}).items() for item in ("--arg", f"{key}={value}")]
            + ["--timeout", str(p.get("timeout", 300000))]
        ),
    }
    builder = cmd_map.get(name)
    if not builder:
        return None
    return builder(params)


async def execute_brow_tool(name, params):
    script_path = None
    proc = None
    try:
        command_params = params
        if name == "brow_run":
            fd, raw_path = tempfile.mkstemp(prefix="brow-benchmark-", suffix=".py")
            script_path = Path(raw_path)
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w") as script:
                script.write(params["code"])
            command_params = {**params, "_script_path": str(script_path)}

        cmd = _build_brow_cmd(name, command_params)
        if cmd is None:
            return {"error": f"Unknown tool: {name}"}
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        timeout_seconds = max(60, params.get("timeout", 30000) / 1000 + 5)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        if proc.returncode != 0:
            return {"error": stderr.decode().strip() or f"Exit code {proc.returncode}"}
        output = stdout.decode().strip()
        if name == "brow_session_new" and "\n" in output:
            lines = output.split("\n", 1)
            return {"output": lines[0].strip(), "snapshot": lines[1].strip()}
        return {"output": output}
    except asyncio.TimeoutError:
        if proc is not None:
            proc.kill()
            await proc.wait()
        return {"error": f"Command timed out after {timeout_seconds:g}s"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        if script_path is not None:
            script_path.unlink(missing_ok=True)
