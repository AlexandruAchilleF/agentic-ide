"""MCP server (stdio) that runs commands and tests in the sandbox container."""

import os
from pathlib import Path

from mcp.server import MCPServer

from sandbox import pytest_report
from sandbox.runner import DEFAULT_IMAGE, MAX_TIMEOUT_S, CommandResult
from sandbox.runner import run_in_container as _run_in_container

server = MCPServer("sandbox")


def _workspace() -> Path:
    return Path(os.environ.get("SANDBOX_WORKSPACE") or os.getcwd())


def _image() -> str:
    return os.environ.get("SANDBOX_IMAGE") or DEFAULT_IMAGE


def format_command_result(result: CommandResult) -> str:
    if result.timed_out:
        summary = f"TIMED OUT after {result.duration_s}s (container killed)"
        hint = f"Hint: run a narrower command or raise timeout_s (max {MAX_TIMEOUT_S})."
    elif result.exit_code == 0:
        summary = f"exit 0 in {result.duration_s}s"
        hint = ""
    else:
        summary = f"FAILED: exit {result.exit_code} in {result.duration_s}s"
        hint = "Hint: the command failed; read stdout and stderr below."
        if "[sandbox]" in result.stderr:
            hint = "Hint: sandbox setup problem; the [sandbox] line explains it."
    if result.truncated:
        summary += " (output truncated)"
    parts = [summary]
    if hint:
        parts.append(hint)
    parts.append(result.model_dump_json(indent=2))
    return "\n\n".join(parts)


def format_test_report(report: pytest_report.TestReport) -> str:
    counts = [
        f"{report.passed} passed",
        f"{report.failed} failed",
        f"{report.errors} errors",
        f"{report.skipped} skipped",
    ]
    lines = [", ".join(counts)]
    if report.problem:
        lines.append(f"Problem: {report.problem}")
    for failure in report.failures:
        where = f"{failure.file}:{failure.line}" if failure.line else failure.file
        lines.append(f"- {where} {failure.nodeid} — {failure.message}")
    if report.failures:
        lines.append(
            "Hint: fix the code or the test, then rerun just one test with "
            "run_tests(path='<nodeid>')."
        )
    elif report.problem:
        lines.append("Hint: run.stdout and run.stderr below show the full output.")
    return "\n".join(lines) + "\n\n" + report.model_dump_json(indent=2)


@server.tool()
def run_command(command: str, timeout_s: int = 60) -> str:
    """Run a shell command in the sandbox container, in /work (the project root).

    No network. Returns exit_code, stdout, stderr, duration_s, timed_out and
    truncated. The container is killed after timeout_s seconds.
    """
    result = _run_in_container(command, _workspace(), timeout_s, _image())
    return format_command_result(result)


@server.tool()
def run_tests(path: str = "", timeout_s: int = 120) -> str:
    """Run pytest in the sandbox container and return the results.

    `path` is optional and relative to the project root: a directory, a file,
    or a node id such as tests/test_x.py::test_y. Returns passed/failed/errors/
    skipped totals and, for each failing test, file, line, nodeid and message.
    """
    report = pytest_report.run_tests(_workspace(), path, timeout_s, _image())
    return format_test_report(report)


def main() -> None:
    server.run()  # stdio transport, which OpenCode's "local" MCP type uses


if __name__ == "__main__":
    main()
