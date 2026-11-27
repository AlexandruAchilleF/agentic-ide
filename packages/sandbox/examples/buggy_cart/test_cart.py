import pytest
from cart import apply_discount, subtotal


def test_subtotal_adds_every_price() -> None:
    assert subtotal([10.0, 5.0, 2.5]) == 17.5


def test_subtotal_of_empty_cart_is_zero() -> None:
    assert subtotal([]) == 0.0


def test_discount_is_a_percentage() -> None:
    assert apply_discount(200.0, 10) == 180.0


def test_discount_rejects_invalid_percent() -> None:
    with pytest.raises(ValueError, match="between 0 and 100"):
        apply_discount(100.0, 150)
