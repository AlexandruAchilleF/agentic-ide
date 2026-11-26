"""The container side of the sandbox: which runtime to use and how to start it.

`build_run_args` is the contract Radu implements. Everything else in the package
only calls it and never builds `run` flags by itself.
"""

import os
import subprocess
from pathlib import Path

# Tried in this order when SANDBOX_RUNTIME is not set. Podman comes first
# because rootless Podman works without sudo on Fedora, while Docker needs
# a running daemon and membership in the `docker` group.
RUNTIME_CANDIDATES = ("podman", "docker")
RUNTIME_ENV_VAR = "SANDBOX_RUNTIME"
MEMORY_LIMIT = "512m"
CPU_LIMIT = "1"
PIDS_LIMIT = "128"
INFO_TIMEOUT_S = 15


class RuntimeNotFoundError(RuntimeError):
    """No usable container runtime (podman or docker) was found."""


def build_run_args(
    runtime: str, workspace: Path, image: str, name: str, command: str
) -> list[str]:
    args = [
        runtime,
        "run",
        "--rm",
        "--name",
        name,
        "--pull=never",
        "--network",
        "none",
        "--memory",
        MEMORY_LIMIT,
        "--cpus",
        CPU_LIMIT,
        "--pids-limit",
        PIDS_LIMIT,
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "-v",
        f"{workspace}:/work:Z",
        "-w",
        "/work",
    ]
    if runtime == "podman":
        args += ["--userns=keep-id"]
    return [*args, image, "sh", "-c", command]


def _runtime_works(runtime: str) -> bool:
    try:
        completed = subprocess.run(
            [runtime, "info"],
            capture_output=True,
            timeout=INFO_TIMEOUT_S,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def detect_runtime() -> str:
    """Return the container runtime to use: SANDBOX_RUNTIME, else podman/docker."""
    from_env = os.environ.get(RUNTIME_ENV_VAR, "").strip()
    if from_env:
        return from_env
    for runtime in RUNTIME_CANDIDATES:
        if _runtime_works(runtime):
            return runtime
    raise RuntimeNotFoundError(
        "No working container runtime found: neither `podman info` nor "
        "`docker info` succeeded. Install Podman (rootless, no sudo needed) or "
        "start the Docker daemon, or set SANDBOX_RUNTIME=podman|docker."
    )
