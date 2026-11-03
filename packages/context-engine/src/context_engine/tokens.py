"""Cheap token counting for enforcing the token budget."""

import math

CHARS_PER_TOKEN = 4
"""Rough average for code with English identifiers; real tokenizers vary."""


def estimate_tokens(text: str) -> int:
    """Estimate how many tokens ``text`` uses, rounding up.

    This is an approximation, so it may differ from what a given model's
    tokenizer reports. Rounding up keeps the estimate on the safe side.
    """
    return math.ceil(len(text) / CHARS_PER_TOKEN)
