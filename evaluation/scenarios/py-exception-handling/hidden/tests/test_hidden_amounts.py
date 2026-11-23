from decimal import Decimal

import pytest

from billing.amounts import parse_amount, total


@pytest.mark.parametrize("bad", ["", "abc", "1.2.3"])
def test_invalid_amounts_raise_value_error(bad):
    with pytest.raises(ValueError):
        parse_amount(bad)


def test_total_rejects_any_invalid_entry():
    with pytest.raises(ValueError):
        total(["1.00", "oops"])


def test_zero_is_still_valid():
    assert parse_amount("0") == Decimal("0")
