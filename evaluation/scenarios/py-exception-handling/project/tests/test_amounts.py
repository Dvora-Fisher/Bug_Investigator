from decimal import Decimal

import pytest

from billing.amounts import parse_amount, total


def test_parses_valid_amount():
    assert parse_amount(" 12.50 ") == Decimal("12.50")


def test_rejects_garbage():
    with pytest.raises(ValueError):
        parse_amount("12,5O")


def test_total():
    assert total(["1.10", "2.20"]) == Decimal("3.30")
