import json
from pathlib import Path

import pytest

from sandbox import pytest_report, server
from sandbox.runner import DEFAULT_IMAGE, CommandResult


def make_result(
    exit_code: int = 0,
    stdout: str = "",
    stderr: str = "",
    timed_out: bool = False,
    truncated: bool = False,
) -> CommandResult:
    return CommandResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_s=1.5,
        timed_out=timed_out,
        truncated=truncated,
    )


def split_json(text: str) -> tuple[str, dict[str, object]]:
    head, _, body = text.partition("\n\n{")
    parsed: dict[str, object] = json.loads("{" + body)
    return head, parsed


def patch_run_in_container(
    monkeypatch: pytest.MonkeyPatch, result: CommandResult
) -> list[tuple[str, Path, int, str]]:
    calls: list[tuple[str, Path, int, str]] = []

    def fake(
        command: str, workspace: Path, timeout_s: int, image: str
    ) -> CommandResult:
        calls.append((command, workspace, timeout_s, image))
        return result

    monkeypatch.setattr(server, "_run_in_container", fake)
    return calls


def test_run_command_success(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_run_in_container(monkeypatch, make_result(stdout="ok\n"))
    head, data = split_json(server.run_command("echo ok"))
    assert head == "exit 0 in 1.5s"
    assert data["stdout"] == "ok\n"


def test_run_command_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_run_in_container(monkeypatch, make_result(2, stderr="ls: no such file\n"))
    head, data = split_json(server.run_command("ls nope"))
    assert head.startswith("FAILED: exit 2 in 1.5s")
    assert "the command failed" in head
    assert data["exit_code"] == 2
    assert data["stderr"] == "ls: no such file\n"


def test_run_command_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_run_in_container(monkeypatch, make_result(137, timed_out=True))
    head, data = split_json(server.run_command("sleep 99", timeout_s=1))
    assert head.startswith("TIMED OUT after 1.5s (container killed)")
    assert "raise timeout_s" in head
    assert data["timed_out"] is True


def test_run_command_sandbox_problem(monkeypatch: pytest.MonkeyPatch) -> None:
    stderr = "[sandbox] The sandbox image 'x' is not available locally."
    patch_run_in_container(monkeypatch, make_result(125, stderr=stderr))
    head, _ = split_json(server.run_command("ls"))
    assert "sandbox setup problem" in head
    assert "the command failed" not in head


def test_run_command_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_run_in_container(monkeypatch, make_result(truncated=True))
    head, _ = split_json(server.run_command("yes"))
    assert head == "exit 0 in 1.5s (output truncated)"


def test_run_command_passes_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = patch_run_in_container(monkeypatch, make_result())
    monkeypatch.setenv("SANDBOX_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("SANDBOX_IMAGE", "custom:1")
    server.run_command("ls", timeout_s=7)
    assert calls == [("ls", tmp_path, 7, "custom:1")]


def test_run_command_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = patch_run_in_container(monkeypatch, make_result())
    monkeypatch.delenv("SANDBOX_WORKSPACE", raising=False)
    monkeypatch.delenv("SANDBOX_IMAGE", raising=False)
    server.run_command("ls")
    command, workspace, timeout_s, image = calls[0]
    assert workspace == Path.cwd()
    assert timeout_s == 60
    assert image == DEFAULT_IMAGE


def failing_report() -> pytest_report.TestReport:
    return pytest_report.TestReport(
        passed=3,
        failed=1,
        errors=1,
        skipped=2,
        exit_code=1,
        failures=[
            pytest_report.TestFailure(
                nodeid="tests/test_a.py::TestX::test_y",
                file="tests/test_a.py",
                line=12,
                message="assert 1 == 2",
                kind="failed",
            ),
            pytest_report.TestFailure(
                nodeid="tests/test_b.py",
                file="tests/test_b.py",
                line=None,
                message="ModuleNotFoundError: No module named 'zzz'",
                kind="error",
            ),
        ],
        run=make_result(1),
    )


def test_format_test_report_failure() -> None:
    text = server.format_test_report(failing_report())
    head, data = split_json(text)
    lines = head.splitlines()
    assert lines[0] == "3 passed, 1 failed, 1 errors, 2 skipped"
    assert lines[1] == (
        "- tests/test_a.py:12 tests/test_a.py::TestX::test_y — assert 1 == 2"
    )
    assert lines[2] == (
        "- tests/test_b.py tests/test_b.py — ModuleNotFoundError: No module named 'zzz'"
    )
    assert "run_tests(path='<nodeid>')" in lines[3]
    assert data["failed"] == 1
    failures = data["failures"]
    assert isinstance(failures, list)
    assert failures[0]["line"] == 12


def test_format_test_report_problem_without_failures() -> None:
    report = pytest_report.TestReport(
        exit_code=5, problem="No tests were collected (exit 5).", run=make_result(5)
    )
    head, _ = split_json(server.format_test_report(report))
    lines = head.splitlines()
    assert lines[0] == "0 passed, 0 failed, 0 errors, 0 skipped"
    assert lines[1] == "Problem: No tests were collected (exit 5)."
    assert "run.stdout and run.stderr" in lines[2]


def test_format_test_report_all_green() -> None:
    report = pytest_report.TestReport(passed=4, exit_code=0, run=make_result())
    head, _ = split_json(server.format_test_report(report))
    assert head == "4 passed, 0 failed, 0 errors, 0 skipped"


def test_run_tests_end_to_end_with_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    xml = (
        '<testsuites><testsuite name="pytest">'
        '<testcase classname="test_a" name="test_ok" file="test_a.py"/>'
        '<testcase classname="test_a" name="test_bad" file="test_a.py" line="3">'
        '<failure message="assert 1 == 2">def test_bad():\n'
        ">       assert 1 == 2\n"
        "E       assert 1 == 2\n\n"
        "test_a.py:4: AssertionError</failure></testcase>"
        "</testsuite></testsuites>"
    )

    def fake(
        command: str, workspace: Path, timeout_s: int, image: str
    ) -> CommandResult:
        report = workspace / pytest_report.REPORT_RELATIVE
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(xml)
        return make_result(1, stdout="1 failed, 1 passed")

    monkeypatch.setattr(pytest_report, "run_in_container", fake)
    monkeypatch.setenv("SANDBOX_WORKSPACE", str(tmp_path))
    head, data = split_json(server.run_tests("test_a.py"))
    lines = head.splitlines()
    assert lines[0] == "1 passed, 1 failed, 0 errors, 0 skipped"
    assert lines[1] == "- test_a.py:4 test_a.py::test_bad — assert 1 == 2"
    assert data["exit_code"] == 1


def test_run_tests_timeout_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake(
        command: str, workspace: Path, timeout_s: int, image: str
    ) -> CommandResult:
        return make_result(137, timed_out=True)

    monkeypatch.setattr(pytest_report, "run_in_container", fake)
    monkeypatch.setenv("SANDBOX_WORKSPACE", str(tmp_path))
    head, data = split_json(server.run_tests(timeout_s=9))
    assert "Problem: The test run timed out after 9s; no results." in head
    assert data["problem"] == "The test run timed out after 9s; no results."


def test_run_tests_runtime_failure_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake(
        command: str, workspace: Path, timeout_s: int, image: str
    ) -> CommandResult:
        return make_result(125, stderr="[sandbox] image missing")

    monkeypatch.setattr(pytest_report, "run_in_container", fake)
    monkeypatch.setenv("SANDBOX_WORKSPACE", str(tmp_path))
    head, _ = split_json(server.run_tests())
    assert "The sandbox container could not run; see run.stderr" in head


def test_run_tests_stale_report_is_ignored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    stale = tmp_path / pytest_report.REPORT_RELATIVE
    stale.parent.mkdir(parents=True)
    stale.write_text("<testsuites/>")

    def fake(
        command: str, workspace: Path, timeout_s: int, image: str
    ) -> CommandResult:
        return make_result(1, stdout="No module named pytest")

    monkeypatch.setattr(pytest_report, "run_in_container", fake)
    monkeypatch.setenv("SANDBOX_WORKSPACE", str(tmp_path))
    head, _ = split_json(server.run_tests())
    assert "pytest is not installed in the sandbox image" in head


def test_run_tests_unreadable_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake(
        command: str, workspace: Path, timeout_s: int, image: str
    ) -> CommandResult:
        report = workspace / pytest_report.REPORT_RELATIVE
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("<testsuites><oops")
        return make_result(1)

    monkeypatch.setattr(pytest_report, "run_in_container", fake)
    monkeypatch.setenv("SANDBOX_WORKSPACE", str(tmp_path))
    head, _ = split_json(server.run_tests())
    assert "unreadable report" in head
