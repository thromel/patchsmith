from collections_ext import unique_preserve_order


def test_unique_preserve_order_keeps_first_seen_order() -> None:
    assert unique_preserve_order(["b", "a", "b"]) == ["b", "a"]

