import json
from pathlib import Path

from patchsmith.cli import main
from patchsmith.portfolio import (
    write_mvp_progress_report,
)


def test_mvp_progress_report_scores_checklist_from_evidence(
    tmp_path: Path,
    capsys,
    write_progress_artifacts,
) -> None:
    artifacts_dir = tmp_path / "artifacts"
    write_progress_artifacts(artifacts_dir)

    output_path = tmp_path / "mvp_progress.md"
    json_output_path = tmp_path / "mvp_progress.json"
    report = write_mvp_progress_report(
        project_root=Path(),
        artifacts_dir=artifacts_dir,
        output_path=output_path,
        json_output_path=json_output_path,
        max_failure_runs=None,
    )

    assert report.status == "ready_with_caveats"
    assert report.completion_percent >= 85.0
    assert report.item_count == 30
    assert report.missing_count == 0
    assert report.blocked_count == 0
    assert report.warning_count >= 2
    item_statuses = {item.item: item.status for item in report.items}
    assert item_statuses["Tests run in Docker sandbox."] == "warning"
    assert item_statuses["Live LLM calibration has been run."] == "warning"
    assert item_statuses["Real-world task breadth is proven."] == "warning"
    assert item_statuses["Agent can read files through bounded tool."] == "passed"
    assert item_statuses["LangGraph repair loop runs."] == "passed"
    rendered = output_path.read_text(encoding="utf-8")
    assert "# PatchSmith MVP Progress Report" in rendered
    assert "Evidence-weighted completion" in rendered
    payload = json.loads(json_output_path.read_text(encoding="utf-8"))
    assert payload["completion_percent"] == report.completion_percent

    cli_output = tmp_path / "cli_mvp_progress.md"
    exit_code = main(
        [
            "mvp-progress",
            "--project-root",
            ".",
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(cli_output),
            "--json",
        ]
    )
    assert exit_code == 0
    cli_payload = json.loads(capsys.readouterr().out)
    assert cli_payload["status"] == "ready_with_caveats"
    assert cli_payload["completion_percent"] >= 85.0
    assert cli_output.exists()


def test_mvp_progress_report_counts_validated_public_issue_corpus(
    tmp_path: Path,
    write_progress_artifacts,
) -> None:
    artifacts_dir = tmp_path / "artifacts"
    write_progress_artifacts(artifacts_dir)
    corpus_dir = artifacts_dir / "experiments" / "public_issue_corpus_v1"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "corpus_summary.json").write_text(
        json.dumps({"valid_entries": 3, "invalid_entries": 0}),
        encoding="utf-8",
    )

    report = write_mvp_progress_report(
        project_root=Path(),
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "mvp_progress.md",
    )

    item_statuses = {item.item: item.status for item in report.items}
    assert item_statuses["Real-world task breadth is proven."] == "passed"
    assert report.warning_count == 2
