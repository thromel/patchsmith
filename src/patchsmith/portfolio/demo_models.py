"""Portfolio demo asset report models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class DemoScriptSection:
    title: str
    duration_seconds: int
    on_screen: str
    narration: str
    artifact: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DemoScriptReport:
    artifacts_dir: str
    generated_at: str
    target_duration_seconds: int
    readiness_status: str
    caveat: str
    sections: list[DemoScriptSection]
    rehearsal_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "target_duration_seconds": self.target_duration_seconds,
            "readiness_status": self.readiness_status,
            "caveat": self.caveat,
            "sections": [section.to_dict() for section in self.sections],
            "rehearsal_commands": self.rehearsal_commands,
        }


@dataclass(frozen=True)
class DemoMediaReport:
    artifacts_dir: str
    generated_at: str
    readiness_status: str
    width: int
    height: int
    markdown_path: str
    svg_path: str
    png_path: str
    highlights: list[str]
    caveat: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "DemoMediaReport",
    "DemoScriptReport",
    "DemoScriptSection",
]
