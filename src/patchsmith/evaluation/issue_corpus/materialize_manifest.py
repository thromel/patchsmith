"""Manifest and text rendering helpers for materialized issue tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from patchsmith.artifacts import dict_or_empty
from patchsmith.evaluation._helpers import _optional_string, _string_list
from patchsmith.evaluation.issue_corpus.preview import _source_free_preview_contexts


def issue_corpus_task_manifest(
    *,
    issue: dict[str, Any],
    preview: dict[str, Any],
    corpus_id: str | None,
    task_dir: Path,
    issue_path: Path,
) -> dict[str, Any]:
    test_commands = materialized_test_commands(preview)
    top_contexts = _source_free_preview_contexts(preview.get("top_contexts"))
    repo_ref = _optional_string(preview.get("repo_path")) or str(issue.get("repo_url", ""))
    manifest = {
        "task_manifest_version": 1,
        "task_id": str(issue.get("task_id", "unknown")),
        "source_corpus": corpus_id,
        "task_dir": str(task_dir),
        "issue_file": str(issue_path),
        "issue": {
            "source": issue.get("source"),
            "repository": issue.get("repository"),
            "repo_url": issue.get("repo_url"),
            "issue_url": issue.get("issue_url"),
            "issue_number": issue.get("issue_number"),
            "title": issue.get("title"),
            "language": issue.get("language"),
            "task_type": issue.get("task_type"),
            "state_at_capture": issue.get("state_at_capture"),
            "captured_at": issue.get("captured_at"),
            "selection_reason": issue.get("selection_reason"),
            "expected_workflow": _string_list(issue.get("expected_workflow")),
        },
        "repository_snapshot": {
            "repo_path": preview.get("repo_path"),
            "commit_hash": preview.get("commit_hash"),
            "branch": preview.get("branch"),
            "file_count": preview.get("file_count"),
            "language_summary": preview.get("language_summary") or {},
            "package_manager": preview.get("package_manager"),
            "test_commands": test_commands,
        },
        "retrieval_preview": {
            "context_provider": preview.get("context_provider"),
            "context_count": preview.get("context_count"),
            "retrieved_files": _string_list(preview.get("retrieved_files")),
            "top_contexts": top_contexts,
        },
        "suggested_commands": [
            (
                "PYTHONPATH=src python3 -m patchsmith.cli run "
                f'--repo "{repo_ref}" '
                f'--issue-file "{issue_path}" '
                "--runtime langgraph "
                "--planner fake_model "
                "--context-provider native_hybrid "
                f'--test-command "{test_commands[0]}" '
                "--json"
            )
        ],
        "claim_boundary": [
            "This manifest prepares an external evaluation task.",
            "It does not prove issue reproduction, patch generation, or test success.",
            "It intentionally omits source excerpts and scraped issue body text.",
        ],
        "source_free": True,
    }
    manifest["source_free"] = manifest_is_source_free(manifest)
    return manifest


def render_materialized_issue(
    *,
    issue: dict[str, Any],
    preview: dict[str, Any],
) -> str:
    workflow = _string_list(issue.get("expected_workflow"))
    retrieved_files = _string_list(preview.get("retrieved_files"))
    lines = [
        f"# {issue.get('title') or issue.get('task_id') or 'Public Issue Task'}",
        "",
        f"- Task ID: `{issue.get('task_id', 'unknown')}`",
        f"- Repository: `{issue.get('repository', 'unknown')}`",
        f"- Issue: `{issue.get('issue_url', 'unknown')}`",
        f"- Repository URL: `{issue.get('repo_url', 'unknown')}`",
        f"- Captured state: `{issue.get('state_at_capture', 'unknown')}`",
        f"- Task type: `{issue.get('task_type', 'unknown')}`",
        f"- Context provider: `{preview.get('context_provider', 'unknown')}`",
        f"- Commit: `{preview.get('commit_hash') or 'unknown'}`",
        "",
        "## Expected Workflow",
        "",
    ]
    lines.extend(f"- {item}" for item in workflow)
    lines.extend(
        [
            "",
            "## Retrieved File Hints",
            "",
        ]
    )
    lines.extend(f"- `{path}`" for path in retrieved_files)
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This file contains curated public issue metadata and retrieved-file hints.",
            "- It intentionally omits source excerpts and scraped issue body text.",
            "- It is not evidence that PatchSmith reproduced or repaired the issue.",
            "",
        ]
    )
    return "\n".join(lines)


def render_materialized_task_runbook(*, manifest: dict[str, Any]) -> str:
    issue = dict_or_empty(manifest.get("issue"))
    snapshot = dict_or_empty(manifest.get("repository_snapshot"))
    retrieval = dict_or_empty(manifest.get("retrieval_preview"))
    commands = _string_list(manifest.get("suggested_commands"))
    lines = [
        f"# {manifest.get('task_id', 'Public Issue Task')} Runbook",
        "",
        "## Inputs",
        "",
        f"- Repository: `{issue.get('repository', 'unknown')}`",
        f"- Issue: `{issue.get('issue_url', 'unknown')}`",
        f"- Local repository snapshot: `{snapshot.get('repo_path') or 'unknown'}`",
        f"- Commit: `{snapshot.get('commit_hash') or 'unknown'}`",
        f"- Context provider: `{retrieval.get('context_provider') or 'unknown'}`",
        f"- Retrieved files: `{', '.join(_string_list(retrieval.get('retrieved_files'))) or 'none'}`",
        "",
        "## Suggested Commands",
        "",
    ]
    for command in commands:
        lines.extend(["```bash", command, "```", ""])
    lines.extend(
        [
            "## Claim Boundary",
            "",
            "- Run this task only after confirming dependency and sandbox expectations.",
            "- A generated manifest is setup evidence, not solved-run evidence.",
            "- Save normal PatchSmith run artifacts before making repair-quality claims.",
            "",
        ]
    )
    return "\n".join(lines)


def materialized_test_commands(preview: dict[str, Any]) -> list[str]:
    commands = _string_list(preview.get("test_commands"))
    return commands or ["python3 -m pytest"]


def manifest_is_source_free(value: Any) -> bool:
    if isinstance(value, dict):
        return all(
            key != "excerpt" and manifest_is_source_free(child) for key, child in value.items()
        )
    if isinstance(value, list):
        return all(manifest_is_source_free(item) for item in value)
    return True
