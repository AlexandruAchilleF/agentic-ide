"""Public contract models shared with the orchestrator.

Every model is immutable and rejects unknown fields, so a typo in a caller's
payload fails loudly instead of being silently ignored. Line numbers are
1-based and inclusive, like in editors and tracebacks.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_TOKEN_BUDGET = 8000
"""Token budget used when the caller does not set one."""

type ItemKind = Literal["file", "class", "function", "method", "snippet"]
"""What a ContextItem holds; "snippet" is any range that is not a whole symbol."""


class Target(BaseModel):
    """The code the caller wants context for: a file, optionally narrowed down.

    ``path`` is relative to the repository root. ``symbol`` names a function,
    class or method inside the file; ``line`` points at a specific line.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str = Field(min_length=1)
    symbol: str | None = Field(default=None, min_length=1)
    line: int | None = Field(default=None, ge=1)


class ContextRequest(BaseModel):
    """A request for the code that is relevant to ``target``.

    ``query`` is an optional free-text hint, such as the task description.
    ``token_budget`` is a hard upper bound for the returned content.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    target: Target
    query: str | None = Field(default=None, min_length=1)
    token_budget: int = Field(default=DEFAULT_TOKEN_BUDGET, gt=0)


class ContextItem(BaseModel):
    """One piece of relevant code, with why it was chosen.

    ``score`` ranks items from 0 (barely relevant) to 1 (the target itself).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str = Field(min_length=1)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    kind: ItemKind
    content: str
    score: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1)

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

    items: tuple[ContextItem, ...] = ()
    tokens_used: int = Field(default=0, ge=0)
    truncated: bool = False
