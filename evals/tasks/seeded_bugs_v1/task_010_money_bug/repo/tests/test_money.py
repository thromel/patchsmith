from money import format_cents


def test_format_cents_pads_fractional_amount() -> None:
    assert format_cents(105) == "$1.05"
    assert format_cents(5) == "$0.05"

