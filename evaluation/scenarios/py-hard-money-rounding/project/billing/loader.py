import csv
import io

from .models import LineItem
from .normalize import normalize_row


def load_csv(text: str) -> list[LineItem]:
    """Rows with columns sku, description, price, qty (header required)."""
    return [normalize_row(row) for row in csv.DictReader(io.StringIO(text)) if row.get("sku")]
