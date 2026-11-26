import subprocess
import sys
from pathlib import Path

import pytest

from sandbox import pytest_report
from sandbox.pytest_report import build_pytest_command, parse_junit_xml

MIXED = """\
import pytest


def test_ok():
    assert True


def test_bad():
    assert 1 == 2, "boom"


@pytest.mark.skip(reason="not now")
def test_skipped():
    pass


class TestGroup:
    def test_in_class(self):
        raise ValueError("inside class")

    def test_fine(self):
        pass
"""


def run_host_pytest(project: Path, *args: str) -> Path:
    (project / "pytest.ini").write_text("[pytest]\n")
    report = project / "report.xml"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            f"--junitxml={report}",
            "-o",
            "junit_family=xunit1",
            *args,
        ],
        cwd=project,
        capture_output=True,
        check=False,
    )
    return report


def test_mixed_run_counts(tmp_path: Path) -> None:
    (tmp_path / "test_mixed.py").write_text(MIXED)
    counts, failures = parse_junit_xml(run_host_pytest(tmp_path))
    assert counts == {"passed": 2, "failed": 2, "errors": 0, "skipped": 1}
    assert len(failures) == 2
    assert all(f.kind == "failed" for f in failures)


def test_failed_assertion_details(tmp_path: Path) -> None:
    (tmp_path / "test_mixed.py").write_text(MIXED)
    _, failures = parse_junit_xml(run_host_pytest(tmp_path))
    bad = next(f for f in failures if f.nodeid.endswith("::test_bad"))
    assert bad.nodeid == "test_mixed.py::test_bad"
    assert bad.file == "test_mixed.py"
    assert bad.line == 9
    assert "boom" in bad.message


def test_test_inside_class(tmp_path: Path) -> None:
    (tmp_path / "test_mixed.py").write_text(MIXED)
    _, failures = parse_junit_xml(run_host_pytest(tmp_path))
    in_class = next(f for f in failures if "TestGroup" in f.nodeid)
    assert in_class.nodeid == "test_mixed.py::TestGroup::test_in_class"
    assert in_class.file == "test_mixed.py"
    assert in_class.line == 19
    assert "inside class" in in_class.message


def test_test_in_subdirectory(tmp_path: Path) -> None:
    sub = tmp_path / "pkg"
    sub.mkdir()
    (sub / "test_deep.py").write_text("def test_x():\n    assert False\n")
    _, failures = parse_junit_xml(run_host_pytest(tmp_path))
    assert [f.nodeid for f in failures] == ["pkg/test_deep.py::test_x"]
    assert failures[0].file == "pkg/test_deep.py"
    assert failures[0].line == 2


def test_collection_error(tmp_path: Path) -> None:
    (tmp_path / "test_broken.py").write_text("import module_that_does_not_exist\n")
    counts, failures = parse_junit_xml(run_host_pytest(tmp_path))
    assert counts["errors"] == 1
    assert counts["passed"] == 0
    assert len(failures) == 1
    failure = failures[0]
    assert failure.kind == "error"
    assert failure.nodeid == "test_broken.py"
    assert "module_that_does_not_exist" in failure.message
    assert failure.message != "collection failure"
    assert failure.file == "test_broken.py"
    assert failure.line == 1


def test_syntax_error_collection(tmp_path: Path) -> None:
    (tmp_path / "test_syntax.py").write_text("def test_x(:\n")
    counts, failures = parse_junit_xml(run_host_pytest(tmp_path))
    assert counts["errors"] == 1
    assert failures[0].kind == "error"
    assert failures[0].nodeid == "test_syntax.py"


def test_zero_tests(tmp_path: Path) -> None:
    (tmp_path / "test_empty.py").write_text("VALUE = 1\n")
    counts, failures = parse_junit_xml(run_host_pytest(tmp_path))
    assert counts == {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    assert failures == []


def test_all_passing(tmp_path: Path) -> None:
    (tmp_path / "test_ok.py").write_text("def test_a():\n    pass\n")
    counts, failures = parse_junit_xml(run_host_pytest(tmp_path))
    assert counts["passed"] == 1
    assert failures == []


def test_missing_report_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        parse_junit_xml(tmp_path / "nope.xml")


def test_long_message_is_shortened(tmp_path: Path) -> None:
    (tmp_path / "test_long.py").write_text(
        "def test_x():\n    raise ValueError('a' * 1000)\n"
    )
    _, failures = parse_junit_xml(run_host_pytest(tmp_path))
    assert len(failures[0].message) <= pytest_report.MAX_MESSAGE_CHARS
    assert failures[0].message.endswith("...")


def test_build_command_without_path() -> None:
    command = build_pytest_command()
    assert command.startswith("python -m pytest -q")
    assert "--junitxml=/work/.sandbox/report.xml" in command
    assert "junit_family=xunit1" in command
    assert command.endswith("--rootdir=/work")


def test_build_command_with_path() -> None:
    command = build_pytest_command("tests/test_x.py::test_y")
    assert command.endswith(" tests/test_x.py::test_y")


def test_build_command_quotes_unsafe_path() -> None:
    command = build_pytest_command("tests/a b; rm -rf x")
    assert command.endswith("'tests/a b; rm -rf x'")
