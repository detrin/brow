import asyncio
import stat
from pathlib import Path

from benchmarks.harness.tools_brow import BROW_TOOLS, _build_brow_cmd, execute_brow_tool


def test_brow_run_is_available_to_the_agent():
    tool = next(tool for tool in BROW_TOOLS if tool["name"] == "brow_run")

    assert tool["input_schema"]["required"] == ["session", "code"]
    assert tool["input_schema"]["properties"]["args"]["additionalProperties"] == {"type": "string"}


def test_brow_run_command_passes_args_and_timeout():
    command = _build_brow_cmd(
        "brow_run",
        {
            "session": "7",
            "_script_path": "/tmp/workflow.py",
            "args": {"query": "widgets", "limit": "10"},
            "timeout": 300000,
        },
    )

    assert command == [
        "brow",
        "run",
        "-s",
        "7",
        "/tmp/workflow.py",
        "--arg",
        "query=widgets",
        "--arg",
        "limit=10",
        "--timeout",
        "300000",
    ]


def test_brow_run_uses_a_private_temporary_script_and_removes_it(monkeypatch):
    observed = {}

    class FakeProcess:
        returncode = 0

        async def communicate(self):
            script_path = Path(observed["command"][4])
            observed["path"] = script_path
            observed["code"] = script_path.read_text()
            observed["mode"] = stat.S_IMODE(script_path.stat().st_mode)
            return b'{"processed": 3}', b""

    async def fake_create_subprocess_exec(*command, **_kwargs):
        observed["command"] = command
        return FakeProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    result = asyncio.run(
        execute_brow_tool(
            "brow_run",
            {"session": "7", "code": "result = {'processed': 3}\n", "timeout": 300000},
        )
    )

    assert result == {"output": '{"processed": 3}'}
    assert observed["code"] == "result = {'processed': 3}\n"
    assert observed["mode"] == 0o600
    assert not observed["path"].exists()
