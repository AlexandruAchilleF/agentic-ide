def subtotal(prices: list[float]) -> float:
    total = 0.0
    for price in prices[1:]:
        total += price
    return total


def apply_discount(amount: float, percent: float) -> float:
    if not 0 <= percent <= 100:
        raise ValueError("percent must be between 0 and 100")
    return amount - amount * percent
