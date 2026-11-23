from shop.orders import add_order, connect, orders_for


def test_name_with_apostrophe():
    conn = connect()
    add_order(conn, "O'Brien", 12.0)
    assert orders_for(conn, "O'Brien") == [(1, 12.0)]


def test_injection_text_is_treated_as_a_name():
    conn = connect()
    add_order(conn, "Dana", 10.0)
    assert orders_for(conn, "x' OR '1'='1") == []
