"""Tests for the public contract models."""

import pytest
from pydantic import ValidationError

from context_engine.models import Target


def test_target_with_only_path() -> None:
    target = Target(path="src/app/main.py")

    assert target.path == "src/app/main.py"
    assert target.symbol is None
    assert target.line is None


def test_target_with_symbol_and_line() -> None:
    target = Target(path="src/app/main.py", symbol="run", line=12)

    assert target.symbol == "run"
    assert target.line == 12


def test_target_rejects_empty_path() -> None:
    with pytest.raises(ValidationError):
        Target(path="")


@pytest.mark.parametrize("line", [0, -3])
def test_target_rejects_line_below_one(line: int) -> None:
    # Lines are 1-based, like in editors and tracebacks.
    with pytest.raises(ValidationError):
        Target(path="a.py", line=line)


def test_target_rejects_unknown_fields() -> None:
    # A typo such as "lin" from a caller must fail loudly, not be ignored.
    with pytest.raises(ValidationError):
        Target.model_validate({"path": "a.py", "lin": 3})


def test_target_is_immutable() -> None:
    target = Target(path="a.py")

    with pytest.raises(ValidationError):
        target.line = 5  # type: ignore[misc]
