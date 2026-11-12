"""The interface every context retriever implements.

The orchestrator depends only on ``ContextRetriever``, never on a concrete
class, so the mock and the real retriever can be swapped without changing
the caller.
"""

from typing import Protocol

from context_engine.models import ContextRequest, ContextResponse


class ContextRetriever(Protocol):
    """Finds the code relevant to a target, within a token budget.

    This is a structural type: any class with a matching ``retrieve`` method
    is a ContextRetriever, without inheriting from this one.
    """

    # `async def` makes this a coroutine: callers must `await` it. Retrieval
    # will read files and run subprocesses, so it should not block the
    # orchestrator's event loop.
    async def retrieve(self, request: ContextRequest) -> ContextResponse:
        """Return the most relevant code for the request's target and query.

        ``tokens_used`` in the response never exceeds ``request.token_budget``.
        """
        # `...` (Ellipsis) is the conventional body for a Protocol method:
        # the Protocol only describes the signature, it has no implementation.
        ...
