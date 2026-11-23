"""Execution tools for the LLM. Everything runs in the Docker sandbox, without network, and every
result is recorded as evidence so claims like "the test fails" can be checked against real output."""

from __future__ import annotations

from langchain_core.tools import BaseTool, tool

from ..sandbox.executor import Executor
from .evidence import EvidenceRecorder

EXECUTION_TOOLS = frozenset({"run_tests", "run_command", "initial_test_run"})


def build_execution_tools(executor: Executor, recorder: EvidenceRecorder) -> list[BaseTool]:

    @tool(parse_docstring=True)
    def run_tests(test_filter: str = "") -> str:
        """Run the project's test suite (or a subset) in the sandbox.

        Args:
            test_filter: Optional name/pattern selecting which tests to run ("" runs all).
        """
        result = executor.run_tests(test_filter)
        return recorder.observe("run_tests", {"test_filter": test_filter}, result.render())

    @tool(parse_docstring=True)
    def run_command(command: list[str]) -> str:
        """Run one allow-listed program in the sandbox (no shell, no network), e.g. ["python", "repro.py"].

        Args:
            command: Program and arguments as a list. Paths are relative to the project root.
        """
        result = executor.run_command(command)
        return recorder.observe("run_command", {"command": command}, result.render())

    @tool(parse_docstring=True)
    def write_repro_file(name: str, content: str) -> str:
        """Create a small script or test that reproduces the bug. It is saved under .investigator/repro/
        and never changes the project's own files.

        Args:
            name: Plain file name, e.g. test_repro.py or repro.js.
            content: Full file content.
        """
        path = executor.write_repro_file(name, content)
        return f"Saved {path}. Run it with run_command."

    return [run_tests, run_command, write_repro_file]
