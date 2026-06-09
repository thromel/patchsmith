CSV parsing keeps empty cells.

parse_csv_line("a,,c") should return ["a", "c"] because blank values are ignored in this utility.

