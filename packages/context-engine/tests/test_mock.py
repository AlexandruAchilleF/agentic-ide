"""Tests for the mock retriever the orchestrator uses before the real one."""

import asyncio

from context_engine.mock import MockRetriever
from context_engine.models import (
    ContextItem,
    ContextRequest,
    ContextResponse,
    Target,
)
from context_engine.retriever import ContextRetriever
from context_engine.tokens import estimate_tokens


def make_item(path: str, content: str) -> ContextItem:
    return ContextItem(
        path=path,
        start_line=1,
        end_line=1,
        kind="snippet",
        content=content,
        score=0.5,
        reason="canned",
    )


def retrieve(retriever: ContextRetriever, request: ContextRequest) -> ContextResponse:
    return asyncio.run(retriever.retrieve(request))


def test_estimate_tokens_rounds_up() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2


def test_mock_satisfies_the_protocol() -> None:
    # mypy checks this assignment: MockRetriever must match ContextRetriever
    # structurally, without inheriting from it.
    retriever: ContextRetriever = MockRetriever()

    assert retriever is not None


def test_default_mock_returns_an_item_for_the_target() -> None:
    request = ContextRequest(target=Target(path="src/app/main.py", symbol="run"))

    response = retrieve(MockRetriever(), request)

    assert len(response.items) == 1
    assert response.items[0].path == "src/app/main.py"
    assert response.tokens_used == estimate_tokens(response.items[0].content)
    assert response.truncated is False


def test_mock_returns_canned_items_in_order() -> None:
    items = [make_item("a.py", "aaaa"), make_item("b.py", "bbbb")]
    request = ContextRequest(target=Target(path="a.py"))

    response = retrieve(MockRetriever(items), request)

    assert [item.path for item in response.items] == ["a.py", "b.py"]
    assert response.tokens_used == 2


def test_mock_respects_the_token_budget() -> None:
    items = [make_item("a.py", "a" * 40), make_item("b.py", "b" * 40)]
    request = ContextRequest(target=Target(path="a.py"), token_budget=15)

    response = retrieve(MockRetriever(items), request)

    assert [item.path for item in response.items] == ["a.py"]
    assert response.tokens_used == 10
    assert response.truncated is True


def test_mock_records_requests() -> None:
    # Lets a caller's tests assert what was asked for.
    mock = MockRetriever()
    request = ContextRequest(target=Target(path="a.py"), query="fix the bug")

    retrieve(mock, request)

    assert mock.requests == [request]


def test_mock_with_no_items_returns_an_empty_response() -> None:
    # An explicit empty list means "nothing found", not "use the placeholder".
    response = retrieve(MockRetriever([]), ContextRequest(target=Target(path="a.py")))

    assert response.items == ()
    assert response.tokens_used == 0
    assert response.truncated is False


def test_default_mock_handles_a_query_only_request() -> None:
    request = ContextRequest(query="add a login endpoint")

    response = retrieve(MockRetriever(), request)

    assert len(response.items) == 1
    assert "add a login endpoint" in response.items[0].content
    assert response.truncated is False
