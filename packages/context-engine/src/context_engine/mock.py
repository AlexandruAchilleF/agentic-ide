"""A stand-in retriever, so callers can integrate before the real one exists.

``MockRetriever`` follows the ``ContextRetriever`` protocol and enforces the
token budget, but returns fixed items instead of searching the repository.
The orchestrator uses it in its own tests and during early integration.
"""

from collections.abc import Sequence

from context_engine.models import ContextItem, ContextRequest, ContextResponse
from context_engine.tokens import estimate_tokens

PLACEHOLDER_PATH = "<mock>"
"""Path of the placeholder item returned for a query-only request."""


class MockRetriever:
    """Returns canned items, honouring the token budget like a real retriever.

    Without canned items it returns one placeholder item for the target, or
    for the query when the request has no target.
    Every request is recorded in ``requests`` so tests can inspect the calls.
    """

    # Sequence accepts any ordered collection (list, tuple, ...) from callers.
    def __init__(self, items: Sequence[ContextItem] | None = None) -> None:
        # None and [] mean different things: None -> "use a placeholder",
        # [] -> "nothing was found". Copying into a tuple stops later changes
        # to the caller's list from leaking into the mock.
        self._items = tuple(items) if items is not None else None
        self.requests: list[ContextRequest] = []

    async def retrieve(self, request: ContextRequest) -> ContextResponse:
        """Return the canned items that fit in ``request.token_budget``."""
        self.requests.append(request)
        candidates = (
            self._items if self._items is not None else (self._placeholder(request),)
        )

        # Greedy selection: walk the items in order and keep each one that
        # still fits. An item that does not fit is skipped, not a reason to
        # stop, because a smaller item further on may still fit.
        selected: list[ContextItem] = []
        tokens_used = 0
        for item in candidates:
            cost = estimate_tokens(item.content)
            if tokens_used + cost > request.token_budget:
                continue
            selected.append(item)
            tokens_used += cost

        return ContextResponse(
            items=tuple(selected),
            tokens_used=tokens_used,
            # Fewer items selected than available means something was cut.
            truncated=len(selected) < len(candidates),
        )

    # @staticmethod: the method does not use `self`, it only builds a value
    # from its argument.
    @staticmethod
    def _placeholder(request: ContextRequest) -> ContextItem:
        target = request.target
        if target is None:
            # Query-only request: there is no file to point at, so use a path
            # that cannot be mistaken for a real one.
            path, line, label = PLACEHOLDER_PATH, 1, f"query: {request.query}"
        else:
            # `x or y` returns y when x is falsy; here that only happens when
            # x is None, because the model rejects line=0 and symbol="".
            # So line defaults to 1 and the label falls back to the path.
            path, line = target.path, target.line or 1
            label = target.symbol or target.path
        return ContextItem(
            path=path,
            start_line=line,
            end_line=line,
            kind="snippet",
            content=f"# mock context for {label}",
            score=1.0,
            reason="placeholder from MockRetriever",
        )
