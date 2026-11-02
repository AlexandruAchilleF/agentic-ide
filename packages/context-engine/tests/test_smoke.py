"""Smoke test: proves the package installs and imports."""

import context_engine


def test_package_imports() -> None:
    assert context_engine.__version__ == "0.1.0"
