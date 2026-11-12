"""Deep context engine: finds the code that is relevant to a file or function.

This file defines the package's public API. Callers import from
``context_engine`` directly (``from context_engine import ContextRequest``)
instead of reaching into the submodules.
"""

# Re-export the public names from the submodules.
from context_engine.mock import MockRetriever
from context_engine.models import (
    DEFAULT_TOKEN_BUDGET,
    ContextItem,
    ContextRequest,
    ContextResponse,
    ItemKind,
    Target,
)
from context_engine.retriever import ContextRetriever

__version__ = "0.1.0"

# __all__ lists the public names: what `from context_engine import *` exports,
# and what tools such as ruff treat as intentionally re-exported.
__all__ = [
    "DEFAULT_TOKEN_BUDGET",
    "ContextItem",
    "ContextRequest",
    "ContextResponse",
    "ContextRetriever",
    "ItemKind",
    "MockRetriever",
    "Target",
]
