from validators import is_even


def test_is_even_accepts_even_numbers() -> None:
    assert is_even(4)


def test_is_even_rejects_odd_numbers() -> None:
    assert not is_even(5)

