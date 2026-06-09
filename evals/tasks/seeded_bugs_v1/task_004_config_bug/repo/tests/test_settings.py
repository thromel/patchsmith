from settings import get_default_timeout


def test_default_timeout_is_integer() -> None:
    assert get_default_timeout() == 30
    assert isinstance(get_default_timeout(), int)

