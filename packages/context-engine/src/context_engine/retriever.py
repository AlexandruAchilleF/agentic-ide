"""The interface every context retriever implements."""

from typing import Protocol

from context_engine.models import ContextRequest, ContextResponse


class ContextRetriever(Protocol):
    """Finds the code relevant to a target, within a token budget.

    This is a structural type: any class with a matching ``retrieve`` method
    is a ContextRetriever, without inheriting from this one.
    """

    async def retrieve(self, request: ContextRequest) -> ContextResponse:
        """Return the most relevant code for ``request.target``.

        ``tokens_used`` in the response never exceeds ``request.token_budget``.
        """
        ...
