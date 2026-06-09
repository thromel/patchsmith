from date_math import is_leap_year


def test_century_years_follow_gregorian_rules() -> None:
    assert not is_leap_year(1900)
    assert is_leap_year(2000)

