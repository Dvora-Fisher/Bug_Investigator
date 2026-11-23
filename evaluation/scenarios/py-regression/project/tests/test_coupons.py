from checkout.coupons import apply_coupons


def test_no_coupon():
    assert apply_coupons(100.0) == 100.0
