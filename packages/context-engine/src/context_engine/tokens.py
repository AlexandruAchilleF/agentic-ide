"""Cheap token counting for enforcing the token budget.

LLMs measure input in tokens, not characters. A real tokenizer is slow and
model-specific, so this module uses a fixed characters-per-token ratio.
"""

import math

CHARS_PER_TOKEN = 4
"""Rough average for code with English identifiers; real tokenizers vary."""


def estimate_tokens(text: str) -> int:
    """Estimate how many tokens ``text`` uses, rounding up.

    This is an approximation, so it may differ from what a given model's
    tokenizer reports. Rounding up keeps the estimate on the safe side.
    """
    # math.ceil rounds up: 5 characters -> 1.25 -> 2 tokens. Overestimating
    # means we may waste a little budget, but we never exceed it.
    return math.ceil(len(text) / CHARS_PER_TOKEN)
