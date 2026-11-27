"""Run one shell command in a fresh container and return a structured result."""

import contextlib
import subprocess
import time
import uuid
from pathlib import Path

from pydantic import BaseModel

from sandbox.container import RuntimeNotFoundError, build_run_args, detect_runtime

DEFAULT_IMAGE = "agentic-ide-sandbox:latest"
MAX_TIMEOUT_S = 600
# Per stream (stdout and stderr each). We keep the END of the output, because
# that is where errors and pytest summaries are printed.
MAX_OUTPUT_CHARS = 20_000
KILL_TIMEOUT_S = 30

# Exit code that docker and podman use when the container could not be started
# (as opposed to the command inside it failing).
RUNTIME_FAILED_EXIT = 125
# Shell convention for "program not found"; we reuse it when the runtime
# binary itself is missing.
NOT_FOUND_EXIT = 127

IMAGE_MISSING_PATTERNS = (
    "image not known",
    "unable to find image",
    "pull access denied",
    "repository does not exist",
    "short-name resolution",
)


class CommandResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool
    truncated: bool


def _truncate(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text, False
    omitted = len(text) - MAX_OUTPUT_CHARS
    marker = f"[... output truncated: first {omitted} characters omitted ...]\n"
    return marker + text[-MAX_OUTPUT_CHARS:], True


def _error_result(message: str, exit_code: int, started: float) -> CommandResult:
    return CommandResult(
        exit_code=exit_code,
        stdout="",
        stderr=message,
        duration_s=round(time.monotonic() - started, 3),
        timed_out=False,
        truncated=False,
    )


def _is_image_missing(stderr: str) -> bool:
    lowered = stderr.lower()
    return any(pattern in lowered for pattern in IMAGE_MISSING_PATTERNS)


def run_in_container(
    command: str,
    workspace: Path,
    timeout_s: int,
    image: str = DEFAULT_IMAGE,
    runtime: str | None = None,
) -> CommandResult:
    started = time.monotonic()

    if timeout_s <= 0:
        return _error_result(
            f"[sandbox] timeout_s must be a positive number of seconds, "
            f"got {timeout_s}.",
            2,
            started,
        )
    timeout_s = min(timeout_s, MAX_TIMEOUT_S)

    workspace = workspace.resolve()
    if not workspace.is_dir():
        return _error_result(
            f"[sandbox] Workspace directory does not exist: {workspace}. "
            "Set SANDBOX_WORKSPACE to the project directory.",
            2,
            started,
        )

    if runtime is None:
        try:
            runtime = detect_runtime()
        except RuntimeNotFoundError as exc:
            return _error_result(f"[sandbox] {exc}", NOT_FOUND_EXIT, started)

    name = f"sandbox-{uuid.uuid4().hex[:12]}"
    args = build_run_args(runtime, workspace, image, name, command)

    try:
        process = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
        )
    except FileNotFoundError:
        return _error_result(
            f"[sandbox] Container runtime '{runtime}' is not installed or not "
            "on PATH. Install it or set SANDBOX_RUNTIME=podman|docker.",
            NOT_FOUND_EXIT,
            started,
        )

    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        # Killing only the client process would leave the container running,
        # so we kill the container by name. --rm then removes it.
        with contextlib.suppress(subprocess.TimeoutExpired):
            subprocess.run(
                [runtime, "kill", name],
                capture_output=True,
                timeout=KILL_TIMEOUT_S,
                check=False,
            )
        try:
            stdout, stderr = process.communicate(timeout=KILL_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()

    duration_s = round(time.monotonic() - started, 3)
    exit_code = process.returncode

    if timed_out:
        stderr += (
            f"\n[sandbox] Command timed out after {timeout_s}s and the container "
            "was killed. Run a narrower command or raise timeout_s "
            f"(max {MAX_TIMEOUT_S})."
        )
    elif exit_code == RUNTIME_FAILED_EXIT and _is_image_missing(stderr):
        stderr += (
            f"\n[sandbox] The sandbox image '{image}' is not available locally. "
            f"Build it first: `{runtime} build -t {image} packages/sandbox/docker`. "
            "Running more commands will not help until the image exists."
        )
    elif exit_code == RUNTIME_FAILED_EXIT:
        stderr += (
            f"\n[sandbox] {runtime} could not start the container (exit 125). "
            "This is a sandbox setup problem, not a problem with your command."
        )

    stdout, stdout_cut = _truncate(stdout)
    stderr, stderr_cut = _truncate(stderr)
    return CommandResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_s=duration_s,
        timed_out=timed_out,
        truncated=stdout_cut or stderr_cut,
    )
