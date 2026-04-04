import asyncio
import time
import json
from dataclasses import dataclass, field

import anthropic
import boto3

from benchmarks.harness.config import BenchmarkConfig
from benchmarks.harness.metrics import ToolCallRecord
from benchmarks.harness.tools_common import SUBMIT_ANSWER_TOOL, execute_submit_answer
from benchmarks.harness.tools_brow import BROW_TOOLS, execute_brow_tool
from benchmarks.harness.tools_mcp import MCP_TOOLS, MCP_TOOL_NAME_MAP, McpPlaywrightClient, execute_mcp_tool
from benchmarks.harness.tools_playwright_cli import PLAYWRIGHT_CLI_TOOLS, execute_playwright_cli_tool, cleanup_playwright_cli
from benchmarks.harness.tools_agent_browser import AGENT_BROWSER_TOOLS, execute_agent_browser_tool, cleanup_agent_browser

BROW_INSTRUCTIONS = """You have access to brow CLI tools for browser automation.
Use brow_session_new with a url to start a session and get the initial page snapshot.
Snapshots show numbered refs like [1], [2] for interactive elements.
Use ref= to click, fill, or select elements (e.g. brow_click ref=3).
Each action returns an updated snapshot — no need to call brow_snapshot after every action.
Use brow_snapshot with search="pattern" to filter large pages.
When done, call submit_answer with your structured result.

Example workflow:
  brow_session_new(url="https://shop.com") → snapshot shows [1] search box, [2] cart...
  brow_fill(ref=1, value="headphones") → snapshot shows [3] "Sony WH-1000" [4] "AirPods Max"...
  brow_click(ref=3) → snapshot shows product details...
  submit_answer({name: "Sony WH-1000XM5", price: "$348"})"""

MCP_INSTRUCTIONS = """You have access to MCP Playwright tools for browser automation.
Use mcp_navigate to go to URLs. Use mcp_snapshot to read the page.
Use element references from snapshots when clicking or filling.
When done, call submit_answer with your structured result."""

PWCLI_INSTRUCTIONS = """You have access to playwright-cli tools for browser automation.
Use pwcli_open to start a headless browser (optionally with a URL).
Use pwcli_snapshot to get element references, then use those refs with pwcli_click, pwcli_fill, etc.
Use pwcli_goto to navigate to URLs.
When done, call submit_answer with your structured result."""

AB_INSTRUCTIONS = """You have access to agent-browser tools for browser automation.
Use ab_open to navigate to a URL (starts the daemon automatically).
Use ab_snapshot to get the accessibility tree with element refs like @e1, @e2, @e3.
Use ab_click, ab_fill, ab_select with element refs from the snapshot.
Use ab_press for keyboard input (Enter, Tab, Escape).
Use ab_scroll to scroll the page.
When done, call submit_answer with your structured result.

Example workflow:
  ab_open(url="https://shop.com") → navigates to page
  ab_snapshot() → shows @e1 search box, @e2 cart...
  ab_fill(ref="@e1", value="headphones") → fills the input
  ab_press(key="Enter") → submits
  ab_snapshot() → shows @e3 "Sony WH-1000", @e4 "AirPods Max"...
  submit_answer({name: "Sony WH-1000XM5", price: "$348"})"""

def build_system_prompt(backend, task_description):
    if backend == "brow":
        instructions = BROW_INSTRUCTIONS
    elif backend == "playwright-cli":
        instructions = PWCLI_INSTRUCTIONS
    elif backend == "agent-browser":
        instructions = AB_INSTRUCTIONS
    else:
        instructions = MCP_INSTRUCTIONS
    return f"""You are a browser automation agent. Complete the given task using the provided tools.

{instructions}

Do not explain your actions. Execute efficiently with minimal tool calls.

Task: {task_description}"""


class AgentLoop:
    def __init__(self, config: BenchmarkConfig, backend: str, task_description: str):
        self.config = config
        self.backend = backend
        self.system_prompt = build_system_prompt(backend, task_description)
        self.tools = self._get_tools()
        self.messages = []
        self.tool_call_log = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.conversation_turns = 0
        self.errors = []
        self.error_recoveries = 0
        self._last_failed_tool = None
        self._mcp_client = None
        self._brow_session_id = None

    def _get_tools(self):
        if self.backend == "brow":
            base = BROW_TOOLS
        elif self.backend == "playwright-cli":
            base = PLAYWRIGHT_CLI_TOOLS
        elif self.backend == "agent-browser":
            base = AGENT_BROWSER_TOOLS
        else:
            base = MCP_TOOLS
        return base + [SUBMIT_ANSWER_TOOL]

    async def run(self, max_steps=15, timeout_seconds=120):
        if self.config.api_key:
            client = anthropic.Anthropic(api_key=self.config.api_key)
        else:
            session = boto3.Session(profile_name=self.config.aws_profile)
            creds = session.get_credentials().get_frozen_credentials()
            client = anthropic.AnthropicBedrock(
                aws_access_key=creds.access_key,
                aws_secret_key=creds.secret_key,
                aws_session_token=creds.token,
                aws_region=self.config.aws_region,
            )
        if self.backend == "mcp-playwright":
            self._mcp_client = McpPlaywrightClient()
            await self._mcp_client.start()

        start = time.time()
        self.messages = [{"role": "user", "content": "Begin the task."}]
        final_output = {}
        COMPRESS_THRESHOLD = 500

        try:
            for step in range(max_steps):
                if time.time() - start > timeout_seconds:
                    break

                self.conversation_turns += 1
                response = None
                for attempt in range(3):
                    try:
                        response = client.messages.create(
                            model=self.config.model,
                            max_tokens=4096,
                            system=self.system_prompt,
                            tools=self.tools,
                            messages=self.messages,
                        )
                        break
                    except anthropic.RateLimitError:
                        if attempt < 2:
                            time.sleep(30 * (attempt + 1))
                        else:
                            raise
                    except anthropic.BadRequestError as e:
                        if "too long" in str(e).lower():
                            self._compress_old_results(200 if attempt == 0 else 50)
                        else:
                            raise
                if response is None:
                    self.errors.append("Input too long after compression")
                    break

                self.total_input_tokens += response.usage.input_tokens
                self.total_output_tokens += response.usage.output_tokens

                if response.stop_reason == "end_turn":
                    break

                tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
                n_tools_in_turn = max(len(tool_use_blocks), 1)
                turn_input = response.usage.input_tokens
                turn_output = response.usage.output_tokens

                # Execute tool calls in parallel when possible
                SEQUENTIAL_TOOLS = {"submit_answer", "brow_session_new"}
                sequential = [b for b in tool_use_blocks if b.name in SEQUENTIAL_TOOLS]
                parallel = [b for b in tool_use_blocks if b.name not in SEQUENTIAL_TOOLS]

                tool_results = []
                results_map = {}

                # Run parallelizable tools concurrently
                if parallel:
                    call_start = time.time()

                    async def _run(block):
                        t0 = time.time()
                        r = await self._execute_tool(block.name, block.input)
                        return block, r, int((time.time() - t0) * 1000)

                    completed = await asyncio.gather(*[_run(b) for b in parallel])
                    for block, result, call_ms in completed:
                        results_map[block.id] = (block, result, call_ms)

                # Run sequential tools one at a time
                for block in sequential:
                    t0 = time.time()
                    result = await self._execute_tool(block.name, block.input)
                    call_ms = int((time.time() - t0) * 1000)
                    results_map[block.id] = (block, result, call_ms)

                # Process results in original order
                for block in tool_use_blocks:
                    block, result, call_ms = results_map[block.id]
                    result_str = json.dumps(result) if isinstance(result, dict) else str(result)
                    is_error = "error" in result if isinstance(result, dict) else False

                    self.tool_call_log.append(ToolCallRecord(
                        name=block.name,
                        input_tokens=turn_input // n_tools_in_turn,
                        output_tokens=turn_output // n_tools_in_turn,
                        latency_ms=call_ms,
                        response_bytes=len(result_str.encode()),
                        success=not is_error,
                        error=result.get("error") if is_error else None,
                    ))

                    if is_error:
                        self.errors.append(result.get("error", "unknown"))
                        self._last_failed_tool = block.name
                    elif self._last_failed_tool == block.name:
                        self.error_recoveries += 1
                        self._last_failed_tool = None

                    if block.name == "brow_session_new" and not is_error:
                        self._brow_session_id = result.get("output", "").strip()

                    if block.name == "submit_answer":
                        final_output = result.get("answer", {})
                        self.messages.append({"role": "assistant", "content": response.content})
                        return final_output

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })

                self.messages.append({"role": "assistant", "content": response.content})
                if tool_results:
                    self._compress_old_results(COMPRESS_THRESHOLD)
                    self.messages.append({"role": "user", "content": tool_results})

        finally:
            if self._mcp_client:
                await self._mcp_client.stop()
            if self.backend == "brow" and self._brow_session_id:
                try:
                    import subprocess
                    subprocess.run(["brow", "session", "delete", self._brow_session_id],
                                   capture_output=True, timeout=10)
                except Exception:
                    pass
            if self.backend == "playwright-cli":
                cleanup_playwright_cli()
            if self.backend == "agent-browser":
                cleanup_agent_browser()

        return final_output

    def _compress_old_results(self, threshold):
        """Compress old tool results based on their type.

        - confirmation results (click/fill/select ok): compress to 1 line immediately
        - navigation results (navigate/session): compress after threshold
        - data results (snapshot/html): keep longer, compress at higher threshold
        """
        for msg in self.messages:
            if msg["role"] != "user" or not isinstance(msg.get("content"), list):
                continue
            for item in msg["content"]:
                if item.get("type") != "tool_result":
                    continue
                content = item.get("content", "")
                if not content or len(content) <= 50:
                    continue

                is_confirmation = content.startswith('{"ok"') or content.startswith('{"output": ""}')
                is_snapshot = '"snapshot"' in content[:100] or '"tree"' in content[:100]

                if is_confirmation and len(content) > 100:
                    item["content"] = content.split("\n")[0][:100]
                elif is_snapshot and len(content) > threshold * 2:
                    lines = content.split("\n")
                    item["content"] = (
                        "\n".join(lines[:5])
                        + f"\n... ({len(lines) - 10} lines omitted) ...\n"
                        + "\n".join(lines[-5:])
                    )
                elif len(content) > threshold:
                    lines = content.split("\n")
                    item["content"] = (
                        "\n".join(lines[:5])
                        + f"\n... ({len(lines) - 10} lines omitted) ...\n"
                        + "\n".join(lines[-5:])
                    )

    async def _execute_tool(self, name, params):
        if name == "submit_answer":
            return execute_submit_answer(params)
        if self.backend == "brow":
            if self._brow_session_id and "session" not in params:
                params["session"] = self._brow_session_id
            return await execute_brow_tool(name, params)
        if self.backend == "playwright-cli":
            return await execute_playwright_cli_tool(name, params)
        if self.backend == "agent-browser":
            return await execute_agent_browser_tool(name, params)
        return await execute_mcp_tool(self._mcp_client, name, params)
