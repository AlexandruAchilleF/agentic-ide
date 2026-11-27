"""Smoke test: proves the package installs and imports."""

import sandbox


def test_package_imports() -> None:
    assert sandbox.__version__ == "0.1.0"
