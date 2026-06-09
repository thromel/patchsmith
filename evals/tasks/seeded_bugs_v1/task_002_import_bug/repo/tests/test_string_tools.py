from string_tools import slugify


def test_slugify_title() -> None:
    assert slugify("Hello World") == "hello-world"

