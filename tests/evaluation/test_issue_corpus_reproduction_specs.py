import json
from pathlib import Path

import pytest

from patchsmith.evaluation.issue_corpus.reproduction_specs import (
    load_public_issue_reproduction_specs,
    public_issue_reproduction_specs_template,
)
from patchsmith.evaluation_models import IssueCorpusPublicReproductionPlanResult


def test_load_public_issue_reproduction_specs_accepts_wrapped_list_and_keyed_map(
    tmp_path: Path,
) -> None:
    wrapped_specs = tmp_path / "wrapped.json"
    wrapped_specs.write_text(
        json.dumps(
            {
                "specs": [
                    {
                        "task_id": "task_one",
                        "command": "python3 -m pytest tests/test_one.py",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    keyed_specs = tmp_path / "keyed.json"
    keyed_specs.write_text(
        json.dumps({"task_two": {"command": "python3 -m pytest tests/test_two.py"}}),
        encoding="utf-8",
    )

    assert load_public_issue_reproduction_specs(wrapped_specs)["task_one"]["command"].endswith(
        "test_one.py"
    )
    assert load_public_issue_reproduction_specs(keyed_specs)["task_two"]["task_id"] == "task_two"


def test_load_public_issue_reproduction_specs_rejects_duplicate_task_ids(
    tmp_path: Path,
) -> None:
    specs_path = tmp_path / "duplicates.json"
    specs_path.write_text(
        json.dumps([{"task_id": "dupe"}, {"task_id": "dupe"}]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate reproduction spec"):
        load_public_issue_reproduction_specs(specs_path)


def test_public_issue_reproduction_specs_template_keeps_review_placeholders() -> None:
    template = public_issue_reproduction_specs_template(
        [
            IssueCorpusPublicReproductionPlanResult(
                task_id="task_one",
                repository="owner/repo",
                issue_url="https://github.com/owner/repo/issues/1",
                status="planned",
                repo_path="/tmp/repo",
                repo_exists=True,
                reproduction_command="python3 -m pytest tests/test_one.py",
                command_source="focused_plan",
                policy_allowed=True,
                policy_reason="allowed",
                focused_files=[],
                fixture_files=[],
                source_hints=[],
                expected_failure_signals=[],
                manual_spec_required=True,
                evidence=[],
                blockers=[],
                warnings=[],
                next_actions=[],
            )
        ]
    )

    assert template["schema_version"] == 1
    assert template["specs"][0]["task_id"] == "task_one"
    assert template["specs"][0]["expected_failure_signals"] == []
    assert template["specs"][0]["fixture_files"] == []
