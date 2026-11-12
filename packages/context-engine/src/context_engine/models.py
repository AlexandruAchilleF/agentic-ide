"""Public contract models shared with the orchestrator.

This module defines the data that crosses the boundary between the
orchestrator and the context engine: what the caller asks for (``Target``,
``ContextRequest``) and what the engine sends back (``ContextItem``,
``ContextResponse``).

Every model is immutable and rejects unknown fields, so a typo in a caller's
payload fails loudly instead of being silently ignored. Line numbers are
1-based and inclusive, like in editors and tracebacks.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_TOKEN_BUDGET = 8000
"""Token budget used when the caller does not set one."""

# `type X = ...` (Python 3.12) declares a type alias. `Literal[...]` means
# only these exact strings are valid; Pydantic rejects anything else.
type ItemKind = Literal["file", "class", "function", "method", "snippet"]
"""What a ContextItem holds; "snippet" is any range that is not a whole symbol."""


class Target(BaseModel):
    """The code the caller wants context for: a file, optionally narrowed down.

    ``path`` is relative to the repository root. ``symbol`` names a function,
    class or method inside the file; ``line`` points at a specific line.
    """

    # frozen=True: fields cannot be reassigned after creation (immutable).
    # extra="forbid": unknown keys in the input raise a ValidationError.
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Field(...) adds validation rules that Pydantic checks on creation.
    path: str = Field(min_length=1)  # empty string is not a valid path
    symbol: str | None = Field(default=None, min_length=1)  # optional
    line: int | None = Field(default=None, ge=1)  # ge=1: ">= 1", 1-based


class ContextRequest(BaseModel):
    """A request for the code that is relevant to ``target``, ``query`` or both.

    ``target`` is known when the caller is working on a specific file.
    ``query`` is free text, such as the task description; a request with only
    a query asks the engine to find the relevant files itself. At least one of
    the two must be set. ``token_budget`` is a hard upper bound for the
    returned content.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    target: Target | None = None  # a nested model; dicts are converted to it
    query: str | None = Field(default=None, min_length=1)
    token_budget: int = Field(default=DEFAULT_TOKEN_BUDGET, gt=0)  # gt: "> 0"

    # A model validator checks rules that involve several fields at once.
    # mode="after" runs it once the individual fields are already validated,
    # so `self` is a fully built model here.
    @model_validator(mode="after")
    def _check_has_target_or_query(self) -> Self:
        if self.target is None and self.query is None:
            msg = "a request needs a target or query"
            # Pydantic turns a ValueError raised here into a ValidationError.
            raise ValueError(msg)
        return self  # an "after" validator must return the model


class ContextItem(BaseModel):
    """One piece of relevant code, with why it was chosen.

    ``score`` ranks items from 0 (barely relevant) to 1 (the target itself).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str = Field(min_length=1)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)  # inclusive: start_line == end_line is 1 line
    kind: ItemKind
    content: str  # the source code itself, as read from the working tree
    score: float = Field(ge=0.0, le=1.0)  # le: "<= 1.0"
    reason: str = Field(min_length=1)  # human-readable "why this was picked"

    @model_validator(mode="after")
    def _check_line_range(self) -> Self:
        if self.end_line < self.start_line:
            msg = f"end_line ({self.end_line}) is before start_line ({self.start_line})"
            raise ValueError(msg)
        return self


class ContextResponse(BaseModel):
    """The retrieved context, ordered from most to least relevant.

    ``truncated`` is true when relevant code was left out to fit the budget.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # A tuple instead of a list, so the response stays immutable all the way
    # down: a frozen model holding a list could still have the list mutated.
    items: tuple[ContextItem, ...] = ()
    tokens_used: int = Field(default=0, ge=0)
    truncated: bool = False
