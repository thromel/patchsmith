from csv_parser import parse_csv_line


def test_parse_csv_line_ignores_empty_cells() -> None:
    assert parse_csv_line("a,,c") == ["a", "c"]

