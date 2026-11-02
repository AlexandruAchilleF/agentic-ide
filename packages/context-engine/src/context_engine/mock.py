"""A stand-in retriever, so callers can integrate before the real one exists."""

from collections.abc import Sequence

from context_engine.models import ContextItem, ContextRequest, ContextResponse
from context_engine.tokens import estimate_tokens


class MockRetriever:
    """Returns canned items, honouring the token budget like a real retriever.

    Without canned items it returns one placeholder item for the target.
    Every request is recorded in ``requests`` so tests can inspect the calls.
    """

    def __init__(self, items: Sequence[ContextItem] | None = None) -> None:
        self._items = tuple(items) if items is not None else None
        self.requests: list[ContextRequest] = []

    async def retrieve(self, request: ContextRequest) -> ContextResponse:
        """Return the canned items that fit in ``request.token_budget``."""
        self.requests.append(request)
        candidates = (
            self._items if self._items is not None else (self._placeholder(request),)
        )

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
            truncated=len(selected) < len(candidates),
        )

    @staticmethod
    def _placeholder(request: ContextRequest) -> ContextItem:
        target = request.target
        line = target.line or 1
        label = target.symbol or target.path
        return ContextItem(
            path=target.path,
            start_line=line,
            end_line=line,
            kind="snippet",
            content=f"# mock context for {label}",
            score=1.0,
            reason="placeholder from MockRetriever",
        )
