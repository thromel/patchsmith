from __future__ import annotations

from typing import TextIO


def write_line(output_stream: TextIO, message: str) -> None:
    output_stream.write(f"{message}\n")
    output_stream.flush()
