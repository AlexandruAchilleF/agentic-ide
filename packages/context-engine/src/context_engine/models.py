"""Public contract models shared with the orchestrator.

Every model is immutable and rejects unknown fields, so a typo in a caller's
payload fails loudly instead of being silently ignored. Line numbers are
1-based and inclusive, like in editors and tracebacks.
"""

from pydantic import BaseModel, ConfigDict, Field


class Target(BaseModel):
    """The code the caller wants context for: a file, optionally narrowed down.

    ``path`` is relative to the repository root. ``symbol`` names a function,
    class or method inside the file; ``line`` points at a specific line.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str = Field(min_length=1)
    symbol: str | None = Field(default=None, min_length=1)
    line: int | None = Field(default=None, ge=1)
