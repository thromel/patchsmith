from __future__ import annotations

import io

import pytest

from patchsmith.chat.formatting import write_line

pytestmark = pytest.mark.unit


class FlushCountingStream(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.flush_count = 0

    def flush(self) -> None:
        self.flush_count += 1
        super().flush()


def test_write_line_appends_newline_and_flushes() -> None:
    output = FlushCountingStream()

    write_line(output, "PatchSmith Chat")

    assert output.getvalue() == "PatchSmith Chat\n"
    assert output.flush_count == 1
