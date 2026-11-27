"""Run pytest in the container and turn its JUnit XML report into a TestReport.

The workspace is mounted at /work, so the report pytest writes to
/work/.sandbox/report.xml appears on the host at <workspace>/.sandbox/report.xml.
"""

import re
import shlex
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel

from sandbox.runner import (
    DEFAULT_IMAGE,
    NOT_FOUND_EXIT,
    RUNTIME_FAILED_EXIT,
    CommandResult,
    run_in_container,
)

REPORT_IN_CONTAINER = "/work/.sandbox/report.xml"
REPORT_RELATIVE = Path(".sandbox") / "report.xml"
MAX_MESSAGE_CHARS = 300

# pytest exit codes, from `pytest.ExitCode`.
EXIT_OK = 0
EXIT_TESTS_FAILED = 1
EXIT_INTERRUPTED = 2
EXIT_USAGE_ERROR = 4
EXIT_NO_TESTS = 5

# The last "path/to/file.py:42: SomeError" line of a pytest traceback is the
# line that actually failed.
_TRACEBACK_LOCATION = re.compile(r"^(?P<file>[^\s:][^:\n]*\.py):(?P<line>\d+): ", re.M)


class TestFailure(BaseModel):
    __test__: ClassVar[bool] = False  # keep pytest from collecting this class

    nodeid: str
    file: str
    line: int | None
    message: str
    kind: str  # "failed" or "error"


class TestReport(BaseModel):
    __test__: ClassVar[bool] = False

    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    failures: list[TestFailure] = []
    exit_code: int
    problem: str | None = None
    run: CommandResult


def build_pytest_command(path: str = "") -> str:
    parts = [
        "python",
        "-m",
        "pytest",
        "-q",
        f"--junitxml={REPORT_IN_CONTAINER}",
        # xunit1 is the JUnit flavour that keeps the file and line attributes.
        "-o",
        "junit_family=xunit1",
        "--rootdir=/work",
    ]
    if path:
        parts.append(path)
    return shlex.join(parts)


def _short(text: str) -> str:
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    if len(first_line) > MAX_MESSAGE_CHARS:
        return first_line[: MAX_MESSAGE_CHARS - 3] + "..."
    return first_line


def _message(message_attr: str, details: str) -> str:
    # For collection errors pytest only writes "collection failure" in the
    # attribute; the real cause is the last "E   ..." line of the details.
    if message_attr and message_attr != "collection failure":
        return _short(message_attr)
    error_lines = [ln for ln in details.splitlines() if ln.startswith("E ")]
    if error_lines:
        return _short(error_lines[-1][1:])
    return _short(message_attr or details)


def _nodeid(file: str, classname: str, name: str) -> str:
    if not classname:
        # A collection error: there is no test, only the module that failed.
        return file or name
    module = file.removesuffix(".py").replace("/", ".")
    if classname.startswith(module + "."):
        classes = classname[len(module) + 1 :].replace(".", "::")
        return f"{file}::{classes}::{name}"
    return f"{file}::{name}"


def _failure_location(
    details: str, file: str, line_attr: str
) -> tuple[str, int | None]:
    matches = list(_TRACEBACK_LOCATION.finditer(details))
    if matches:
        last = matches[-1]
        return last.group("file"), int(last.group("line"))
    if line_attr.isdigit():
        # The JUnit line is 0-based and points at the test's `def`.
        return file, int(line_attr) + 1
    return file, None


def parse_junit_xml(report_file: Path) -> tuple[dict[str, int], list[TestFailure]]:
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    failures: list[TestFailure] = []
    root = ET.parse(report_file).getroot()
    for case in root.iter("testcase"):
        file = case.get("file", "")
        nodeid = _nodeid(file, case.get("classname", ""), case.get("name", ""))
        failure = case.find("failure")
        error = case.find("error")
        problem = failure if failure is not None else error
        if problem is not None:
            kind = "failed" if failure is not None else "error"
            counts["failed" if kind == "failed" else "errors"] += 1
            details = problem.text or ""
            where, line = _failure_location(details, file, case.get("line", ""))
            failures.append(
                TestFailure(
                    nodeid=nodeid,
                    file=where or nodeid,
                    line=line,
                    message=_message(problem.get("message", ""), details),
                    kind=kind,
                )
            )
        elif case.find("skipped") is not None:
            counts["skipped"] += 1
        else:
            counts["passed"] += 1
    return counts, failures


def _exit_code_problem(exit_code: int) -> str | None:
    if exit_code in (EXIT_OK, EXIT_TESTS_FAILED):
        return None
    if exit_code == EXIT_NO_TESTS:
        return (
            "No tests were collected (exit 5). Check the path and that test "
            "files are named test_*.py with functions named test_*."
        )
    if exit_code == EXIT_INTERRUPTED:
        return (
            "pytest stopped before running the tests (exit 2), usually because "
            "a test file failed to import. See the errors below."
        )
    if exit_code == EXIT_USAGE_ERROR:
        return (
            "pytest rejected the arguments (exit 4), usually because the path "
            "does not exist. Check the path; it is relative to the project root."
        )
    return f"pytest exited with code {exit_code}; see run.stdout and run.stderr."


def _problem_without_report(result: CommandResult) -> str:
    output = result.stdout + result.stderr
    if result.exit_code in (NOT_FOUND_EXIT, RUNTIME_FAILED_EXIT):
        return "The sandbox container could not run; see run.stderr for the cause."
    if "No module named pytest" in output:
        return (
            "pytest is not installed in the sandbox image. Add it to the image "
            "(it is a sandbox setup problem, not a problem in the tests)."
        )
    if result.exit_code == EXIT_USAGE_ERROR:
        return _exit_code_problem(EXIT_USAGE_ERROR) or ""
    return (
        f"pytest exited with code {result.exit_code} without writing a report "
        "(it probably crashed). See run.stdout and run.stderr."
    )


def run_tests(
    workspace: Path,
    path: str = "",
    timeout_s: int = 120,
    image: str = DEFAULT_IMAGE,
) -> TestReport:
    report_file = workspace / REPORT_RELATIVE
    # A stale report from an earlier run would look like fresh results.
    report_file.unlink(missing_ok=True)

    result = run_in_container(build_pytest_command(path), workspace, timeout_s, image)

    if result.timed_out:
        return TestReport(
            exit_code=result.exit_code,
            problem=f"The test run timed out after {timeout_s}s; no results.",
            run=result,
        )
    if not report_file.is_file():
        return TestReport(
            exit_code=result.exit_code,
            problem=_problem_without_report(result),
            run=result,
        )

    try:
        counts, failures = parse_junit_xml(report_file)
    except ET.ParseError as exc:
        return TestReport(
            exit_code=result.exit_code,
            problem=f"pytest wrote an unreadable report ({exc}); see run.stdout.",
            run=result,
        )

    problem = _exit_code_problem(result.exit_code)
    return TestReport(
        exit_code=result.exit_code,
        problem=problem,
        failures=failures,
        run=result,
        passed=counts["passed"],
        failed=counts["failed"],
        errors=counts["errors"],
        skipped=counts["skipped"],
    )
