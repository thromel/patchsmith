from usernames import normalize_username


def test_normalize_username_lowercases_spaces() -> None:
    assert normalize_username("Alice Smith") == "alice_smith"

