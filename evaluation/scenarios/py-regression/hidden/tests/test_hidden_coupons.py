from checkout.coupons import apply_coupons


def test_coupons_do_not_leak_between_calls():
    assert apply_coupons(100.0, [10]) == 90.0
    assert apply_coupons(100.0, [10]) == 90.0
    assert apply_coupons(100.0) == 100.0


def test_two_coupons_in_one_call():
    assert apply_coupons(100.0, [10, 50]) == 45.0
