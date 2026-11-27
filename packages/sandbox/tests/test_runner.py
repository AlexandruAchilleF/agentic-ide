import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from sandbox import runner
from sandbox.runner import (
    MAX_OUTPUT_CHARS,
    _truncate,
    run_in_container,
)

BuildArgs = Callable[[str, Path, str, str, str], list[str]]


def fake_python(code: str) -> BuildArgs:
    def build(
        runtime: str, workspace: Path, image: str, name: str, command: str
    ) -> list[str]:
        return [sys.executable, "-c", code]

    return build


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path


def test_truncate_short_text_untouched() -> None:
    assert _truncate("hello") == ("hello", False)


def test_truncate_exact_limit_untouched() -> None:
    text = "x" * MAX_OUTPUT_CHARS
    assert _truncate(text) == (text, False)


def test_truncate_keeps_end_and_adds_marker() -> None:
    text = "START" + "m" * MAX_OUTPUT_CHARS + "END"
    cut, truncated = _truncate(text)
    assert truncated
    assert cut.startswith("[... output truncated:")
    assert "first 8 characters omitted" in cut
    assert cut.endswith("END")
    assert "START" not in cut


def test_truncate_bounded_size() -> None:
    cut, _ = _truncate("y" * (MAX_OUTPUT_CHARS * 3))
    marker_end = cut.index("\n") + 1
    assert len(cut) - marker_end == MAX_OUTPUT_CHARS


def test_success(monkeypatch: pytest.MonkeyPatch, workspace: Path) -> None:
    monkeypatch.setattr(runner, "build_run_args", fake_python("print('hi')"))
    result = run_in_container("x", workspace, 10, runtime="podman")
    assert result.exit_code == 0
    assert result.stdout == "hi\n"
    assert not result.timed_out
    assert not result.truncated


def test_nonzero_exit_keeps_streams(
    monkeypatch: pytest.MonkeyPatch, workspace: Path
) -> None:
    code = "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)"
    monkeypatch.setattr(runner, "build_run_args", fake_python(code))
    result = run_in_container("x", workspace, 10, runtime="podman")
    assert result.exit_code == 3
    assert result.stdout == "out\n"
    assert result.stderr == "err\n"
    assert not result.timed_out


def test_build_run_args_receives_arguments(
    monkeypatch: pytest.MonkeyPatch, workspace: Path
) -> None:
    seen: list[tuple[str, Path, str, str, str]] = []

    def build(runtime: str, ws: Path, image: str, name: str, command: str) -> list[str]:
        seen.append((runtime, ws, image, name, command))
        return [sys.executable, "-c", "pass"]

    monkeypatch.setattr(runner, "build_run_args", build)
    run_in_container("echo hi", workspace, 10, image="img:1", runtime="docker")
    runtime, ws, image, name, command = seen[0]
    assert (runtime, ws, image, command) == ("docker", workspace, "img:1", "echo hi")
    assert name.startswith("sandbox-")


def test_huge_output_is_truncated(
    monkeypatch: pytest.MonkeyPatch, workspace: Path
) -> None:
    code = f"print('a' * {MAX_OUTPUT_CHARS * 2}); print('LAST')"
    monkeypatch.setattr(runner, "build_run_args", fake_python(code))
    result = run_in_container("x", workspace, 10, runtime="podman")
    assert result.truncated
    assert "output truncated" in result.stdout
    assert result.stdout.endswith("LAST\n")


def test_timeout_kills_container(
    monkeypatch: pytest.MonkeyPatch, workspace: Path
) -> None:
    monkeypatch.setattr(
        runner, "build_run_args", fake_python("import time; time.sleep(60)")
    )
    processes: list[subprocess.Popen[str]] = []
    real_popen = subprocess.Popen

    def recording_popen(*args: object, **kwargs: object) -> subprocess.Popen[str]:
        process: subprocess.Popen[str] = real_popen(*args, **kwargs)  # type: ignore[call-overload]
        processes.append(process)
        return process

    kill_calls: list[list[str]] = []

    def fake_run(
        argv: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        kill_calls.append(argv)
        processes[0].kill()
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "Popen", recording_popen)
    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_in_container("sleep 60", workspace, 1, runtime="podman")

    assert result.timed_out
    assert len(kill_calls) == 1
    assert kill_calls[0][:2] == ["podman", "kill"]
    assert kill_calls[0][2].startswith("sandbox-")
    assert "timed out after 1s" in result.stderr
    assert "container was killed" in result.stderr
    assert result.duration_s < 30


def test_timeout_names_same_container_as_run(
    monkeypatch: pytest.MonkeyPatch, workspace: Path
) -> None:
    names: list[str] = []

    def build(runtime: str, ws: Path, image: str, name: str, command: str) -> list[str]:
        names.append(name)
        return [sys.executable, "-c", "import time; time.sleep(60)"]

    killed: list[list[str]] = []
    real_popen = subprocess.Popen
    started: list[subprocess.Popen[str]] = []

    def recording_popen(*args: object, **kwargs: object) -> subprocess.Popen[str]:
        process: subprocess.Popen[str] = real_popen(*args, **kwargs)  # type: ignore[call-overload]
        started.append(process)
        return process

    def fake_run(
        argv: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        killed.append(argv)
        started[0].kill()
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(runner, "build_run_args", build)
    monkeypatch.setattr(subprocess, "Popen", recording_popen)
    monkeypatch.setattr(subprocess, "run", fake_run)
    run_in_container("x", workspace, 1, runtime="docker")
    assert killed == [["docker", "kill", names[0]]]


def test_missing_runtime_binary(
    monkeypatch: pytest.MonkeyPatch, workspace: Path
) -> None:
    def build(runtime: str, ws: Path, image: str, name: str, command: str) -> list[str]:
        return [runtime, "run", image]

    monkeypatch.setattr(runner, "build_run_args", build)
    result = run_in_container("x", workspace, 10, runtime="no-such-runtime-xyz")
    assert result.exit_code == runner.NOT_FOUND_EXIT == 127
    assert "[sandbox]" in result.stderr
    assert "no-such-runtime-xyz" in result.stderr
    assert "not installed" in result.stderr
    assert "SANDBOX_RUNTIME" in result.stderr


def test_no_runtime_detected(monkeypatch: pytest.MonkeyPatch, workspace: Path) -> None:
    from sandbox.container import RuntimeNotFoundError

    def detect() -> str:
        raise RuntimeNotFoundError("No working container runtime found")

    monkeypatch.setattr(runner, "detect_runtime", detect)
    result = run_in_container("x", workspace, 10)
    assert result.exit_code == 127
    assert result.stderr.startswith("[sandbox] No working container runtime")


def test_image_missing_adds_build_advice(
    monkeypatch: pytest.MonkeyPatch, workspace: Path
) -> None:
    code = "import sys; print('Error: image not known', file=sys.stderr); sys.exit(125)"
    monkeypatch.setattr(runner, "build_run_args", fake_python(code))
    result = run_in_container(
        "x", workspace, 10, image="my-image:tag", runtime="podman"
    )
    assert result.exit_code == 125
    assert "image not known" in result.stderr
    assert "[sandbox] The sandbox image 'my-image:tag' is not available" in (
        result.stderr
    )
    assert "podman build -t my-image:tag" in result.stderr


@pytest.mark.parametrize(
    "message",
    [
        "Unable to find image 'x' locally",
        "pull access denied for x",
        "repository does not exist",
        "short-name resolution enforced",
    ],
)
def test_other_image_missing_messages(
    monkeypatch: pytest.MonkeyPatch, workspace: Path, message: str
) -> None:
    code = f"import sys; print({message!r}, file=sys.stderr); sys.exit(125)"
    monkeypatch.setattr(runner, "build_run_args", fake_python(code))
    result = run_in_container("x", workspace, 10, runtime="docker")
    assert "is not available locally" in result.stderr
    assert "docker build -t" in result.stderr


def test_exit_125_other_cause(monkeypatch: pytest.MonkeyPatch, workspace: Path) -> None:
    code = "import sys; print('bad flag', file=sys.stderr); sys.exit(125)"
    monkeypatch.setattr(runner, "build_run_args", fake_python(code))
    result = run_in_container("x", workspace, 10, runtime="podman")
    assert result.exit_code == 125
    assert "could not start the container" in result.stderr
    assert "not a problem with your command" in result.stderr
    assert "build -t" not in result.stderr


def test_image_pattern_ignored_when_exit_not_125(
    monkeypatch: pytest.MonkeyPatch, workspace: Path
) -> None:
    code = "import sys; print('image not known', file=sys.stderr); sys.exit(1)"
    monkeypatch.setattr(runner, "build_run_args", fake_python(code))
    result = run_in_container("x", workspace, 10, runtime="podman")
    assert "[sandbox]" not in result.stderr


def test_non_positive_timeout(workspace: Path) -> None:
    result = run_in_container("x", workspace, 0, runtime="podman")
    assert result.exit_code == 2
    assert "[sandbox] timeout_s must be a positive number" in result.stderr


def test_missing_workspace(tmp_path: Path) -> None:
    result = run_in_container("x", tmp_path / "absent", 5, runtime="podman")
    assert result.exit_code == 2
    assert "Workspace directory does not exist" in result.stderr
    assert "SANDBOX_WORKSPACE" in result.stderr


def test_timeout_is_capped(monkeypatch: pytest.MonkeyPatch, workspace: Path) -> None:
    seen: list[float | None] = []

    class Spy(subprocess.Popen[str]):
        def communicate(
            self, input: str | None = None, timeout: float | None = None
        ) -> tuple[str, str]:
            seen.append(timeout)
            out, err = super().communicate(input, timeout)
            return out, err

    monkeypatch.setattr(runner, "build_run_args", fake_python("pass"))
    monkeypatch.setattr(subprocess, "Popen", Spy)
    run_in_container("x", workspace, 99_999, runtime="podman")
    assert seen == [runner.MAX_TIMEOUT_S]
