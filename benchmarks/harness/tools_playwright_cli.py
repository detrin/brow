import subprocess
import json
import re
from pathlib import Path

PLAYWRIGHT_CLI_TOOLS = [
    {
        "name": "pwcli_open",
        "description": "Open a headless browser session. Returns session info.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Optional URL to navigate to"},
            },
        },
    },
    {
        "name": "pwcli_goto",
        "description": "Navigate to a URL.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "pwcli_snapshot",
        "description": "Capture accessibility snapshot of the current page. Returns element references for use with click, fill, etc.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "pwcli_click",
        "description": "Click an element by its reference from snapshot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Element reference from snapshot"},
            },
            "required": ["ref"],
        },
    },
    {
        "name": "pwcli_fill",
        "description": "Fill text into an editable element.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Element reference from snapshot"},
                "value": {"type": "string"},
            },
            "required": ["ref", "value"],
        },
    },
    {
        "name": "pwcli_type",
        "description": "Type text into editable element.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "pwcli_press",
        "description": "Press a key (Enter, Tab, Escape, etc).",
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
        },
    },
    {
        "name": "pwcli_screenshot",
        "description": "Take a screenshot of the current page.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "pwcli_hover",
        "description": "Hover over an element.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Element reference from snapshot"},
            },
            "required": ["ref"],
        },
    },
    {
        "name": "pwcli_select",
        "description": "Select an option from a dropdown.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Element reference from snapshot"},
                "value": {"type": "string"},
            },
            "required": ["ref", "value"],
        },
    },
    {
        "name": "pwcli_eval",
        "description": "Execute JavaScript in the browser.",
        "input_schema": {
            "type": "object",
            "properties": {"javascript": {"type": "string"}},
            "required": ["javascript"],
        },
    },
    {
        "name": "pwcli_go_back",
        "description": "Go back to the previous page.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "pwcli_reload",
        "description": "Reload the current page.",
        "input_schema": {"type": "object", "properties": {}},
    },
]

import uuid

_session_name = None

def _get_session():
    global _session_name
    if not _session_name:
        _session_name = f"bench-{uuid.uuid4().hex[:8]}"
    return _session_name

def _reset_session():
    global _session_name
    _session_name = None

def _inline_snapshots(output):
    def replacer(m):
        path = Path(m.group(1))
        if path.exists():
            return path.read_text()
        return m.group(0)
    return re.sub(r'\[Snapshot\]\(([^)]+\.yml)\)', replacer, output)

def _run(args):
    cmd = ["playwright-cli", f"-s={_get_session()}"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return {"error": result.stderr.strip() or f"Exit code {result.returncode}"}
        return {"output": _inline_snapshots(result.stdout.strip())}
    except subprocess.TimeoutExpired:
        return {"error": "Command timed out after 60s"}
    except Exception as e:
        return {"error": str(e)}

async def _run_async(args):
    import asyncio
    cmd = ["playwright-cli", f"-s={_get_session()}"] + args
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode != 0:
            return {"error": stderr.decode().strip() or f"Exit code {proc.returncode}"}
        return {"output": _inline_snapshots(stdout.decode().strip())}
    except asyncio.TimeoutError:
        proc.kill()
        return {"error": "Command timed out after 60s"}
    except Exception as e:
        return {"error": str(e)}


async def execute_playwright_cli_tool(name, params):
    cmd_map = {
        "pwcli_open": lambda p: ["open"] + ([p["url"]] if p.get("url") else []),
        "pwcli_goto": lambda p: ["goto", p["url"]],
        "pwcli_snapshot": lambda p: ["snapshot"],
        "pwcli_click": lambda p: ["click", p["ref"]],
        "pwcli_fill": lambda p: ["fill", p["ref"], p["value"]],
        "pwcli_type": lambda p: ["type", p["text"]],
        "pwcli_press": lambda p: ["press", p["key"]],
        "pwcli_screenshot": lambda p: ["screenshot"],
        "pwcli_hover": lambda p: ["hover", p["ref"]],
        "pwcli_select": lambda p: ["select", p["ref"], p["value"]],
        "pwcli_eval": lambda p: ["eval", p["javascript"]],
        "pwcli_go_back": lambda p: ["go-back"],
        "pwcli_reload": lambda p: ["reload"],
    }
    builder = cmd_map.get(name)
    if not builder:
        return {"error": f"Unknown tool: {name}"}
    return await _run_async(builder(params))


def cleanup_playwright_cli():
    session = _get_session()
    try:
        subprocess.run(
            ["playwright-cli", f"-s={session}", "close"],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass
    _reset_session()
