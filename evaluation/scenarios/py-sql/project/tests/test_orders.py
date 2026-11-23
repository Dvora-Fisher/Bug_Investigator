from shop.orders import add_order, connect, orders_for


def test_orders_for_customer():
    conn = connect()
    add_order(conn, "Dana", 10.0)
    add_order(conn, "Avi", 5.0)
    add_order(conn, "Dana", 7.5)
    assert orders_for(conn, "Dana") == [(1, 10.0), (3, 7.5)]
