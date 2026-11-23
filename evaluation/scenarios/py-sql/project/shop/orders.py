import sqlite3

SCHEMA = """
CREATE TABLE orders (id INTEGER PRIMARY KEY, customer TEXT NOT NULL, total REAL NOT NULL);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    return conn


def add_order(conn: sqlite3.Connection, customer: str, total: float) -> None:
    conn.execute("INSERT INTO orders (customer, total) VALUES (?, ?)", (customer, total))


def orders_for(conn: sqlite3.Connection, customer: str) -> list[tuple[int, float]]:
    """All (id, total) of a customer's orders, oldest first."""
    query = f"SELECT id, total FROM orders WHERE customer = '{customer}' ORDER BY id"
    return conn.execute(query).fetchall()
