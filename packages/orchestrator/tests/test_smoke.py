"""Smoke test: proves the package installs and imports."""

import orchestrator


def test_package_imports() -> None:
    assert orchestrator.__version__ == "0.1.0"
