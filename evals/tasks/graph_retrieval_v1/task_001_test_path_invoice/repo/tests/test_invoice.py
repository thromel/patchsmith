from invoice import calculate_charge


def test_billed_amount() -> None:
    assert calculate_charge(3, 125) == 375
