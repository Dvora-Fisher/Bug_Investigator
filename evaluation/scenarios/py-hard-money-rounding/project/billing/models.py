from dataclasses import dataclass


@dataclass(frozen=True)
class LineItem:
    sku: str
    description: str
    unit_price: float  # in the account currency, e.g. 19.99
    quantity: int = 1
