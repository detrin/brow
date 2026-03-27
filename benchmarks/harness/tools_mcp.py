import asyncio
import json
import subprocess
import sys

MCP_TOOLS = [
    {
        "name": "mcp_navigate",
        "description": "Navigate to a URL in the browser.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "mcp_snapshot",
        "description": "Get the accessibility snapshot of the current page.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "mcp_click",
        "description": "Click an element on the page using a CSS selector or text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "element": {"type": "string", "description": "Human-readable element description"},
                "ref": {"type": "string", "description": "Element reference from snapshot"},
            },
            "required": ["element", "ref"],
        },
    },
    {
        "name": "mcp_fill",
        "description": "Fill an input field.",
        "input_schema": {
            "type": "object",
            "properties": {
                "element": {"type": "string"},
                "ref": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["element", "ref", "value"],
        },
    },
    {
        "name": "mcp_type",
        "description": "Type text using keyboard.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "submit": {"type": "boolean", "default": False},
            },
            "required": ["text"],
        },
    },
    {
        "name": "mcp_press_key",
        "description": "Press a key.",
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
        },
    },
    {
        "name": "mcp_screenshot",
        "description": "Take a screenshot of the current page.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "mcp_hover",
        "description": "Hover over an element.",
        "input_schema": {
            "type": "object",
            "properties": {
                "element": {"type": "string"},
                "ref": {"type": "string"},
            },
            "required": ["element", "ref"],
        },
    },
    {
        "name": "mcp_select_option",
        "description": "Select an option from a dropdown.",
        "input_schema": {
            "type": "object",
            "properties": {
                "element": {"type": "string"},
                "ref": {"type": "string"},
                "values": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["element", "ref", "values"],
        },
    },
    {
        "name": "mcp_wait",
        "description": "Wait for a condition.",
        "input_schema": {
            "type": "object",
            "properties": {"time": {"type": "integer", "description": "Milliseconds to wait"}},
            "required": ["time"],
        },
    },
    {
        "name": "mcp_evaluate",
        "description": "Execute JavaScript in the browser.",
        "input_schema": {
            "type": "object",
            "properties": {"javascript": {"type": "string"}},
            "required": ["javascript"],
        },
    },
]

MCP_TOOL_NAME_MAP = {
    "mcp_navigate": "browser_navigate",
    "mcp_snapshot": "browser_snapshot",
    "mcp_click": "browser_click",
    "mcp_fill": "browser_fill_form",
    "mcp_type": "browser_type",
    "mcp_press_key": "browser_press_key",
    "mcp_screenshot": "browser_take_screenshot",
    "mcp_hover": "browser_hover",
    "mcp_select_option": "browser_select_option",
    "mcp_wait": "browser_wait_for",
    "mcp_evaluate": "browser_evaluate",
}


class McpPlaywrightClient:
    def __init__(self):
        self._proc = None
        self._request_id = 0
        self._session_id = None
        self._base_url = None

    async def start(self):
        import socket
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()

        self._base_url = f"http://localhost:{port}"
        self._proc = await asyncio.create_subprocess_exec(
            "npx", "@playwright/mcp@latest", "--headless", "--port", str(port),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        import httpx
        self._http = httpx.AsyncClient(timeout=60)
        for _ in range(30):
            await asyncio.sleep(0.5)
            try:
                resp = await self._http.post(
                    f"{self._base_url}/mcp",
                    json={"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "benchmark", "version": "1.0"},
                    }},
                    headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
                )
                if resp.status_code == 200:
                    self._session_id = resp.headers.get("mcp-session-id") or resp.headers.get("Mcp-Session-Id")
                    await self._http.post(
                        f"{self._base_url}/mcp",
                        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                        headers=self._headers(),
                    )
                    return
            except httpx.ConnectError:
                continue
        stderr = b""
        try:
            stderr = self._proc.stderr._buffer
        except Exception:
            pass
        raise RuntimeError(f"MCP Playwright server failed to start. stderr: {stderr.decode()[:500]}")

    def _headers(self):
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self._session_id:
            h["Mcp-Session-Id"] = self._session_id
        return h

    def _parse_sse(self, text):
        for line in text.strip().splitlines():
            if line.startswith("data: "):
                return json.loads(line[6:])
        return json.loads(text)

    async def call_tool(self, mcp_method, params):
        self._request_id += 1
        resp = await self._http.post(
            f"{self._base_url}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": "tools/call",
                "params": {"name": mcp_method, "arguments": params},
            },
            headers=self._headers(),
        )
        return self._parse_sse(resp.text)

    async def stop(self):
        if hasattr(self, "_http"):
            await self._http.aclose()
        if self._proc:
            self._proc.terminate()
            await self._proc.wait()


async def execute_mcp_tool(client: McpPlaywrightClient, name: str, params: dict):
    mcp_method = MCP_TOOL_NAME_MAP.get(name)
    if not mcp_method:
        return {"error": f"Unknown MCP tool: {name}"}
    try:
        response = await client.call_tool(mcp_method, params)
        if "error" in response:
            return {"error": str(response["error"])}
        result = response.get("result", {})
        content = result.get("content", [])
        text_parts = [c.get("text", "") for c in content if c.get("type") == "text"]
        return {"output": "\n".join(text_parts) if text_parts else json.dumps(result)}
    except Exception as e:
        return {"error": str(e)}
