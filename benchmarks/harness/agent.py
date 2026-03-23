import time
import json
from dataclasses import dataclass, field

import anthropic

from benchmarks.harness.config import BenchmarkConfig
from benchmarks.harness.metrics import ToolCallRecord
from benchmarks.harness.tools_common import SUBMIT_ANSWER_TOOL, execute_submit_answer
from benchmarks.harness.tools_brow import BROW_TOOLS, execute_brow_tool
from benchmarks.harness.tools_mcp import MCP_TOOLS, MCP_TOOL_NAME_MAP, McpPlaywrightClient, execute_mcp_tool

def _load_brow_skill():
    from pathlib import Path
    skill_path = Path(__file__).parent.parent.parent / "skills" / "brow" / "SKILL.md"
    if skill_path.exists():
        return skill_path.read_text()
    return ""

BROW_INSTRUCTIONS = f"""You have access to brow CLI tools for browser automation.
Use brow_session_new to start a session, then use the session ID with other tools.
Use brow_snapshot to read page content (fast, token-efficient).
Selectors: CSS (#id, .class), text (text=Click Me), role (role=button[name='Save']).
When done, call submit_answer with your structured result."""

MCP_INSTRUCTIONS = """You have access to MCP Playwright tools for browser automation.
Use mcp_navigate to go to URLs. Use mcp_snapshot to read the page.
Use element references from snapshots when clicking or filling.
When done, call submit_answer with your structured result."""

def build_system_prompt(backend, task_description):
    if backend == "brow":
        skill_content = _load_brow_skill()
        instructions = BROW_INSTRUCTIONS + ("\n\n" + skill_content if skill_content else "")
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
        base = BROW_TOOLS if self.backend == "brow" else MCP_TOOLS
        return [{"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]} for t in base] + [
            {"name": SUBMIT_ANSWER_TOOL["name"], "description": SUBMIT_ANSWER_TOOL["description"], "input_schema": SUBMIT_ANSWER_TOOL["input_schema"]}
        ]

    async def run(self, max_steps=15, timeout_seconds=120):
        client = anthropic.Anthropic(api_key=self.config.api_key)
        if self.backend == "mcp-playwright":
            self._mcp_client = McpPlaywrightClient()
            await self._mcp_client.start()

        start = time.time()
        self.messages = [{"role": "user", "content": "Begin the task."}]
        final_output = {}

        try:
            for step in range(max_steps):
                if time.time() - start > timeout_seconds:
                    break

                self.conversation_turns += 1
                response = client.messages.create(
                    model=self.config.model,
                    max_tokens=4096,
                    system=self.system_prompt,
                    tools=self.tools,
                    messages=self.messages,
                )

                self.total_input_tokens += response.usage.input_tokens
                self.total_output_tokens += response.usage.output_tokens

                if response.stop_reason == "end_turn":
                    break

                tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
                n_tools_in_turn = max(len(tool_use_blocks), 1)
                turn_input = response.usage.input_tokens
                turn_output = response.usage.output_tokens

                tool_results = []
                for block in tool_use_blocks:
                    call_start = time.time()
                    result = await self._execute_tool(block.name, block.input)
                    call_ms = int((time.time() - call_start) * 1000)

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

        return final_output

    async def _execute_tool(self, name, params):
        if name == "submit_answer":
            return execute_submit_answer(params)
        if self.backend == "brow":
            return execute_brow_tool(name, params)
        return await execute_mcp_tool(self._mcp_client, name, params)
