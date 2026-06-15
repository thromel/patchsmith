from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from patchsmith.patch_quality import assess_diff_quality


@dataclass(frozen=True)
class AgentDiffView:
    path: str | None
    exists: bool
    bytes: int | None
    total_lines: int
    shown_lines: int
    truncated: bool
    file_count: int
    changed_files: tuple[str, ...]
    additions: int
    deletions: int
    preview_lines: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "exists": self.exists,
            "bytes": self.bytes,
            "total_lines": self.total_lines,
            "shown_lines": self.shown_lines,
            "truncated": self.truncated,
            "file_count": self.file_count,
            "changed_files": list(self.changed_files),
            "additions": self.additions,
            "deletions": self.deletions,
            "preview_lines": list(self.preview_lines),
        }


@dataclass(frozen=True)
class AgentDiffReview:
    path: str | None
    exists: bool
    risk_level: str
    score: int | None
    decision: str
    confirmation_required: bool
    file_count: int
    changed_files: tuple[str, ...]
    additions: int
    deletions: int
    findings: tuple[dict[str, str], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "exists": self.exists,
            "risk_level": self.risk_level,
            "score": self.score,
            "decision": self.decision,
            "confirmation_required": self.confirmation_required,
            "file_count": self.file_count,
            "changed_files": list(self.changed_files),
            "additions": self.additions,
            "deletions": self.deletions,
            "findings": list(self.findings),
        }


def summarize_agent_diff(
    diff_path: str | Path | None,
    *,
    max_lines: int = 80,
) -> AgentDiffView:
    raw_path = str(diff_path) if diff_path is not None else None
    if raw_path is None:
        return _empty_view(path=None)
    path = Path(raw_path)
    if not path.is_file():
        return _empty_view(path=raw_path)
    try:
        text = path.read_text(encoding="utf-8")
        size = path.stat().st_size
    except OSError:
        return _empty_view(path=raw_path)
    lines = text.splitlines()
    changed_files: list[str] = []
    additions = 0
    deletions = 0
    for line in lines:
        if line.startswith("diff --git "):
            changed_file = _changed_file_from_diff_header(line)
            if changed_file and changed_file not in changed_files:
                changed_files.append(changed_file)
        elif line.startswith("+") and not line.startswith("+++"):
            additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1
    shown_lines = max(0, min(max_lines, len(lines)))
    return AgentDiffView(
        path=raw_path,
        exists=True,
        bytes=size,
        total_lines=len(lines),
        shown_lines=shown_lines,
        truncated=shown_lines < len(lines),
        file_count=len(changed_files),
        changed_files=tuple(changed_files),
        additions=additions,
        deletions=deletions,
        preview_lines=tuple(lines[:shown_lines]),
    )


def review_agent_diff(diff_path: str | Path | None) -> AgentDiffReview:
    diff = summarize_agent_diff(diff_path, max_lines=0)
    if diff.path is None or not diff.exists:
        return AgentDiffReview(
            path=diff.path,
            exists=False,
            risk_level="unknown",
            score=None,
            decision="blocked",
            confirmation_required=True,
            file_count=diff.file_count,
            changed_files=diff.changed_files,
            additions=diff.additions,
            deletions=diff.deletions,
            findings=(),
        )
    try:
        text = Path(diff.path).read_text(encoding="utf-8")
    except OSError:
        return AgentDiffReview(
            path=diff.path,
            exists=False,
            risk_level="unknown",
            score=None,
            decision="blocked",
            confirmation_required=True,
            file_count=diff.file_count,
            changed_files=diff.changed_files,
            additions=diff.additions,
            deletions=diff.deletions,
            findings=(),
        )
    if not text.strip() or diff.file_count == 0:
        return AgentDiffReview(
            path=diff.path,
            exists=True,
            risk_level="not_available",
            score=None,
            decision="blocked",
            confirmation_required=True,
            file_count=diff.file_count,
            changed_files=diff.changed_files,
            additions=diff.additions,
            deletions=diff.deletions,
            findings=(
                {
                    "severity": "high",
                    "code": "empty_diff",
                    "message": (
                        "generated diff is empty or has no changed files; "
                        "run cannot be reviewed or applied"
                    ),
                },
            ),
        )
    assessment = assess_diff_quality(text)
    return AgentDiffReview(
        path=diff.path,
        exists=True,
        risk_level=assessment.severity,
        score=assessment.score,
        decision=_review_decision(assessment.severity),
        confirmation_required=assessment.severity == "high",
        file_count=diff.file_count,
        changed_files=diff.changed_files,
        additions=diff.additions,
        deletions=diff.deletions,
        findings=tuple(finding.to_dict() for finding in assessment.findings),
    )


def format_agent_diff_stat(diff: AgentDiffView) -> str:
    lines = [
        "Diff summary:",
        f"- Path: {diff.path or 'n/a'}",
        f"- Exists: {str(diff.exists).lower()}",
        f"- Size: {_format_size(diff.bytes)}",
        f"- Files: {diff.file_count}",
        f"- Lines: +{diff.additions} / -{diff.deletions}",
        f"- Total diff lines: {diff.total_lines}",
    ]
    if diff.changed_files:
        lines.append(f"- Changed files: {', '.join(diff.changed_files[:10])}")
    return "\n".join(lines)


def format_agent_diff_review(review: AgentDiffReview) -> str:
    lines = [
        "Diff risk review:",
        f"- Path: {review.path or 'n/a'}",
        f"- Exists: {str(review.exists).lower()}",
        f"- Risk: {review.risk_level}",
        f"- Score: {_format_score(review.score)}",
        f"- Decision: {review.decision}",
        f"- Confirmation required: {str(review.confirmation_required).lower()}",
        f"- Files: {review.file_count}",
        f"- Lines: +{review.additions} / -{review.deletions}",
    ]
    if review.changed_files:
        lines.append(f"- Changed files: {', '.join(review.changed_files[:10])}")
    if not review.findings:
        lines.append("- Findings: none")
    else:
        lines.append("- Findings:")
        for finding in review.findings:
            lines.append(
                "  - "
                f"[{finding.get('severity', 'unknown')}] "
                f"{finding.get('code', 'unknown')}: "
                f"{finding.get('message', '')}"
            )
    return "\n".join(lines)


def format_agent_diff_preview(diff: AgentDiffView) -> str:
    lines = [
        *format_agent_diff_stat(diff).splitlines(),
        f"- Showing: {diff.shown_lines}/{diff.total_lines} lines",
        "",
        "```diff",
    ]
    lines.extend(diff.preview_lines)
    if diff.truncated:
        lines.append(f"... truncated {diff.total_lines - diff.shown_lines} line(s)")
    lines.append("```")
    return "\n".join(lines)


def _empty_view(path: str | None) -> AgentDiffView:
    return AgentDiffView(
        path=path,
        exists=False,
        bytes=None,
        total_lines=0,
        shown_lines=0,
        truncated=False,
        file_count=0,
        changed_files=(),
        additions=0,
        deletions=0,
        preview_lines=(),
    )


def _changed_file_from_diff_header(line: str) -> str | None:
    parts = line.split()
    if len(parts) < 4:
        return None
    candidate = parts[3]
    if candidate.startswith("b/"):
        return candidate[2:]
    return candidate


def _format_size(value: int | None) -> str:
    if value is None:
        return "n/a"
    return f"{value} bytes"


def _review_decision(risk_level: str) -> str:
    if risk_level == "high":
        return "confirm_required"
    if risk_level == "medium":
        return "review_recommended"
    return "ready_for_apply_check"


def _format_score(value: int | None) -> str:
    if value is None:
        return "n/a"
    return str(value)
