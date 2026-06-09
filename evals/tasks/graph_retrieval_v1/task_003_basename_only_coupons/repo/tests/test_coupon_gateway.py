from coupon_rules import apply_coupon


def test_gateway_case() -> None:
    assert apply_coupon(1000, 125) == 875
