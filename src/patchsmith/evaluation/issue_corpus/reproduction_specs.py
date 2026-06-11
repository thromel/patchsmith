from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from patchsmith.evaluation_models import IssueCorpusPublicReproductionPlanResult


def public_issue_reproduction_specs_template(
    results: list[IssueCorpusPublicReproductionPlanResult],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "claim_boundary": [
            "This template is for reviewed public issue reproduction criteria.",
            "Do not count a task as reproduced until execute-public-issue-reproductions records a nonzero exit and matches every expected failure signal.",
            "Keep commands within the normal PatchSmith command policy, such as python3 -m pytest.",
        ],
        "specs": [
            {
                "task_id": result.task_id,
                "repository": result.repository,
                "issue_url": result.issue_url,
                "command": result.reproduction_command,
                "fixture_files": [],
                "expected_failure_signals": [],
                "review_notes": (
                    "Fill after reviewing the issue-specific failing traceback, "
                    "assertion, or behavior mismatch."
                ),
            }
            for result in results
        ],
    }


def load_public_issue_reproduction_specs(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"public issue reproduction specs do not exist: {path}")
    if not path.is_file():
        raise ValueError(f"public issue reproduction specs path is not a file: {path}")
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(parsed, dict) and isinstance(parsed.get("specs"), list):
        raw_records = parsed["specs"]
    elif isinstance(parsed, list):
        raw_records = parsed
    elif isinstance(parsed, dict):
        raw_records = []
        for task_id, record in parsed.items():
            if not isinstance(record, dict):
                raise ValueError(
                    "task-id keyed reproduction specs must map every task id to an object"
                )
            raw_records.append({**record, "task_id": task_id})
    else:
        raise ValueError("public issue reproduction specs must contain an object or list")

    specs: dict[str, dict[str, Any]] = {}
    for index, raw_record in enumerate(raw_records, start=1):
        if not isinstance(raw_record, dict):
            raise ValueError(f"reproduction spec #{index} must be a JSON object")
        task_id = _optional_string(raw_record.get("task_id"))
        if task_id is None:
            raise ValueError(f"reproduction spec #{index} is missing task_id")
        if task_id in specs:
            raise ValueError(f"duplicate reproduction spec for task_id: {task_id}")
        specs[task_id] = raw_record
    return specs


def _optional_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None
