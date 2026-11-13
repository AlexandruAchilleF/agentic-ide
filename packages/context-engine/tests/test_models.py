"""Tests for the public contract models.

Most tests check that invalid input raises ``ValidationError``: the models
are the boundary with the orchestrator, so bad data must be caught there.
"""

import pytest
from pydantic import ValidationError

from context_engine.models import (
    DEFAULT_TOKEN_BUDGET,
    ContextItem,
    ContextRequest,
    ContextResponse,
    Target,
)


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
    # pytest.raises passes only if the block raises the given exception.
    with pytest.raises(ValidationError):
        Target(path="")


# parametrize runs the test once per value, each reported as its own test.
@pytest.mark.parametrize("line", [0, -3])
def test_target_rejects_line_below_one(line: int) -> None:
    # Lines are 1-based, like in editors and tracebacks.
    with pytest.raises(ValidationError):
        Target(path="a.py", line=line)


def test_target_rejects_unknown_fields() -> None:
    # A typo such as "lin" from a caller must fail loudly, not be ignored.
    # model_validate builds a model from a dict, as if it came from JSON.
    with pytest.raises(ValidationError):
        Target.model_validate({"path": "a.py", "lin": 3})


def test_target_is_immutable() -> None:
    target = Target(path="a.py")

    # The type: ignore silences mypy, which already knows the field is frozen;
    # here we want the assignment to run and fail at runtime.
    with pytest.raises(ValidationError):
        target.line = 5  # type: ignore[misc]


def test_request_defaults() -> None:
    request = ContextRequest(target=Target(path="a.py"))

    assert request.query is None
    assert request.token_budget == DEFAULT_TOKEN_BUDGET


def test_request_parses_nested_json_payload() -> None:
    # The orchestrator sends plain JSON; nested dicts become models.
    request = ContextRequest.model_validate_json(
        '{"target": {"path": "a.py", "symbol": "run"}, "token_budget": 500}'
    )

    assert request.target == Target(path="a.py", symbol="run")
    assert request.token_budget == 500


def test_request_with_only_query() -> None:
    # The planner's first request: it knows the task, not the files yet.
    request = ContextRequest(query="add a login endpoint")

    assert request.target is None
    assert request.query == "add a login endpoint"


def test_request_with_only_target() -> None:
    request = ContextRequest(target=Target(path="a.py"))

    assert request.target == Target(path="a.py")
    assert request.query is None


def test_request_rejects_missing_target_and_query() -> None:
    # A request with neither asks for nothing; fail loudly at the boundary.
    # match= also checks the error message, so we know which rule failed.
    with pytest.raises(ValidationError, match="target or query"):
        ContextRequest()


def test_request_parses_query_only_json_payload() -> None:
    request = ContextRequest.model_validate_json('{"query": "add login"}')

    assert request.target is None
    assert request.query == "add login"


@pytest.mark.parametrize("budget", [0, -1])
def test_request_rejects_non_positive_budget(budget: int) -> None:
    with pytest.raises(ValidationError):
        ContextRequest(target=Target(path="a.py"), token_budget=budget)


def make_item(**overrides: object) -> ContextItem:
    # Test helper: a valid item by default; each test overrides only the
    # field it is about, e.g. make_item(score=1.1).
    fields: dict[str, object] = {
        "path": "a.py",
        "start_line": 3,
        "end_line": 7,
        "kind": "function",
        "content": "def run() -> None:\n    ...",
        "score": 0.9,
        "reason": "target symbol",
    }
    fields.update(overrides)
    return ContextItem.model_validate(fields)


def test_item_accepts_single_line_range() -> None:
    item = make_item(start_line=5, end_line=5)

    assert item.start_line == item.end_line == 5


def test_item_rejects_end_before_start() -> None:
    with pytest.raises(ValidationError, match="end_line"):
        make_item(start_line=7, end_line=3)


@pytest.mark.parametrize("score", [-0.1, 1.1])
def test_item_rejects_score_outside_unit_interval(score: float) -> None:
    with pytest.raises(ValidationError):
        make_item(score=score)


def test_item_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        make_item(kind="variable")


def test_response_json_round_trip() -> None:
    # Serialize to JSON and back: what the orchestrator receives must turn
    # into an equal object.
    response = ContextResponse(items=(make_item(),), tokens_used=12)

    restored = ContextResponse.model_validate_json(response.model_dump_json())

    assert restored == response
    assert restored.truncated is False


def test_response_rejects_negative_tokens_used() -> None:
    with pytest.raises(ValidationError):
        ContextResponse(tokens_used=-1)
