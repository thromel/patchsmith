from window import moving_average


def test_moving_average_exact_window() -> None:
    assert moving_average([1, 2, 3], 3) == [2.0]


def test_moving_average_larger_input() -> None:
    assert moving_average([1, 2, 3, 4], 2) == [1.5, 2.5, 3.5]

