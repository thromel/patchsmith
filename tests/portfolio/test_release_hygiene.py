import json
import subprocess
from pathlib import Path

from patchsmith.portfolio import (
    write_release_hygiene_report,
)


def _write_release_hygiene_fixture(project_root: Path, artifacts_dir: Path) -> None:
    (project_root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "patchsmith-research"',
                'version = "0.1.0"',
                "",
                "[project.optional-dependencies]",
                'dev = ["build>=1.2", "pytest>=8.0"]',
                "",
                "[tool.hatch.build.targets.wheel]",
                'packages = ["src/patchsmith"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    for doc_path in [
        "README.md",
        "docs/09_roadmap.md",
        "docs/12_release_and_portfolio_plan.md",
        "docs/17_sprint_plans.md",
        "docs/18_delivery_process.md",
        "docs/06_safety_and_sandboxing.md",
    ]:
        path = project_root / doc_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ready_with_caveats offline live LLM calibration\n", encoding="utf-8")
    for artifact_path in [
        "experiments/index.md",
        "experiments/index.json",
        "experiments/index.html",
        "experiments/failure_report.md",
        "experiments/failure_report.json",
        "experiments/demo_readiness.md",
        "experiments/demo_readiness.json",
        "experiments/calibration_readiness.md",
        "experiments/calibration_readiness.json",
        "experiments/live_calibration_plan.md",
        "experiments/live_calibration_plan.json",
        "experiments/launch_blockers.md",
        "experiments/launch_blockers.json",
        "experiments/public_issue_corpus_v1/corpus_report.md",
        "experiments/public_issue_corpus_v1/corpus_summary.json",
        "experiments/public_issue_corpus_v1/repo_preflight_report.md",
        "experiments/public_issue_corpus_v1/repo_preflight_summary.json",
        "experiments/public_issue_corpus_v1/context_preview_report.md",
        "experiments/public_issue_corpus_v1/context_preview_summary.json",
        "experiments/public_issue_corpus_v1/materialized_task_report.md",
        "experiments/public_issue_corpus_v1/materialized_task_summary.json",
        "experiments/public_issue_corpus_v1/materialized_task_validation_report.md",
        "experiments/public_issue_corpus_v1/materialized_task_validation_summary.json",
        "experiments/public_issue_corpus_v1/materialized_run_readiness_report.md",
        "experiments/public_issue_corpus_v1/materialized_run_readiness_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_plan_report.md",
        "experiments/public_issue_corpus_v1/focused_test_plan_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_run_report.md",
        "experiments/public_issue_corpus_v1/focused_test_run_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_diagnosis_report.md",
        "experiments/public_issue_corpus_v1/focused_test_diagnosis_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_setup_plan_report.md",
        "experiments/public_issue_corpus_v1/focused_test_setup_plan_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_setup_readiness_report.md",
        "experiments/public_issue_corpus_v1/focused_test_setup_readiness_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_setup_execution_report.md",
        "experiments/public_issue_corpus_v1/focused_test_setup_execution_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_setup_validation_report.md",
        "experiments/public_issue_corpus_v1/focused_test_setup_validation_summary.json",
        "experiments/public_issue_corpus_v1/public_issue_reproduction_plan_report.md",
        "experiments/public_issue_corpus_v1/public_issue_reproduction_plan_summary.json",
        "experiments/public_issue_corpus_v1/public_issue_failure_signal_discovery_report.md",
        "experiments/public_issue_corpus_v1/public_issue_failure_signal_discovery_summary.json",
        "experiments/public_issue_corpus_v1/public_issue_reproduction_spec_validation_report.md",
        "experiments/public_issue_corpus_v1/public_issue_reproduction_spec_validation_summary.json",
        "experiments/public_issue_corpus_v1/public_issue_reproduction_execution_report.md",
        "experiments/public_issue_corpus_v1/public_issue_reproduction_execution_summary.json",
        "experiments/public_issue_corpus_v1/public_issue_repair_readiness_report.md",
        "experiments/public_issue_corpus_v1/public_issue_repair_readiness_summary.json",
        "experiments/public_issue_corpus_v1/public_issue_repair_attempt_report.md",
        "experiments/public_issue_corpus_v1/public_issue_repair_attempt_summary.json",
        "experiments/demo_script.md",
        "experiments/demo_script.json",
        "experiments/demo_media.md",
        "experiments/demo_media.json",
        "experiments/demo_media.svg",
        "experiments/demo_media.png",
        "experiments/environment_readiness.md",
        "experiments/environment_readiness.json",
        "experiments/quality_gate.md",
        "experiments/quality_gate.json",
        "experiments/project_status.md",
        "experiments/project_status.json",
        "experiments/final_evaluation.md",
        "experiments/final_evaluation.json",
        "experiments/delivery_audit.md",
        "experiments/delivery_audit.json",
    ]:
        path = artifacts_dir / artifact_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n" if path.suffix == ".json" else "ok\n", encoding="utf-8")
    (artifacts_dir / "experiments" / "environment_readiness.json").write_text(
        json.dumps(
            {
                "readiness_status": "ready",
                "passed_count": 10,
                "warning_count": 0,
                "blocked_count": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _git(project_root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project_root, check=True, capture_output=True, text=True)


def test_release_hygiene_blocks_stale_project_status(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repo"
    artifacts_dir = tmp_path / "artifacts"
    project_root.mkdir()
    _write_release_hygiene_fixture(project_root, artifacts_dir)
    (artifacts_dir / "experiments" / "project_status.json").write_text(
        json.dumps(
            {
                "evidence_freshness_status": "stale",
                "stale_source_count": 1,
                "undated_source_count": 0,
                "missing_sources": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = write_release_hygiene_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "release_hygiene.md",
    )

    freshness_check = next(
        check for check in report.checks if check.name == "Project Status Freshness"
    )
    assert freshness_check.status == "blocked"
    assert "1 stale" in freshness_check.evidence
    assert "refresh-evidence" in freshness_check.next_action


def test_release_hygiene_warns_on_blocked_environment_readiness(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repo"
    artifacts_dir = tmp_path / "artifacts"
    project_root.mkdir()
    _write_release_hygiene_fixture(project_root, artifacts_dir)
    (artifacts_dir / "experiments" / "environment_readiness.json").write_text(
        json.dumps(
            {
                "readiness_status": "blocked",
                "passed_count": 3,
                "warning_count": 6,
                "blocked_count": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = write_release_hygiene_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "release_hygiene.md",
    )

    environment_check = next(
        check for check in report.checks if check.name == "Environment Readiness"
    )
    assert environment_check.status == "warning"
    assert "1 blocked" in environment_check.evidence
    assert "offline evidence" in environment_check.next_action


def test_release_hygiene_requires_committed_clean_git_repository(tmp_path: Path) -> None:
    project_root = tmp_path / "repo"
    artifacts_dir = tmp_path / "artifacts"
    project_root.mkdir()
    _write_release_hygiene_fixture(project_root, artifacts_dir)

    _git(project_root, "init", "--initial-branch=main")
    empty_repo_report = write_release_hygiene_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "empty_git_hygiene.md",
    )
    assert empty_repo_report.release_status == "blocked"
    assert any(
        check.name == "Git Repository"
        and check.status == "blocked"
        and "has no commit yet" in check.evidence
        for check in empty_repo_report.checks
    )

    _git(project_root, "config", "user.email", "patchsmith@example.invalid")
    _git(project_root, "config", "user.name", "PatchSmith Test")
    _git(project_root, "add", ".")
    _git(project_root, "commit", "-m", "Initial release baseline")

    clean_repo_report = write_release_hygiene_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "clean_git_hygiene.md",
    )
    git_check = next(check for check in clean_repo_report.checks if check.name == "Git Repository")
    assert git_check.status == "passed"
    assert "worktree clean" in git_check.evidence
    assert any(
        check.name == "Packaging Config" and check.status == "passed"
        for check in clean_repo_report.checks
    )

    (project_root / "README.md").write_text(
        "ready_with_caveats offline live LLM calibration\nmodified\n",
        encoding="utf-8",
    )
    dirty_repo_report = write_release_hygiene_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "dirty_git_hygiene.md",
    )
    assert dirty_repo_report.release_status == "blocked"
    assert any(
        check.name == "Git Repository"
        and check.status == "blocked"
        and "uncommitted file changes" in check.evidence
        for check in dirty_repo_report.checks
    )
