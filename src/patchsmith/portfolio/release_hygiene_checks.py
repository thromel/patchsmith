"""Release hygiene check builders."""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path
from typing import Any

from patchsmith.portfolio._helpers import (
    _failure_summary,
    _live_providers,
    _load_json_artifact,
    _payload_int,
    _payload_string,
    _payload_string_list,
    _provider_summary,
)
from patchsmith.portfolio.models import DemoReadinessReport, ReleaseHygieneCheck


def release_hygiene_checks(
    *,
    project_root: Path,
    artifacts_dir: Path,
    readiness: DemoReadinessReport,
) -> list[ReleaseHygieneCheck]:
    required_docs = [
        "README.md",
        "docs/09_roadmap.md",
        "docs/12_release_and_portfolio_plan.md",
        "docs/17_sprint_plans.md",
        "docs/18_delivery_process.md",
        "docs/06_safety_and_sandboxing.md",
    ]
    required_artifacts = [
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
        (
            "experiments/public_issue_corpus_v1/"
            "public_issue_reproduction_spec_validation_summary.json"
        ),
        "experiments/public_issue_corpus_v1/public_issue_reproduction_execution_report.md",
        "experiments/public_issue_corpus_v1/public_issue_reproduction_execution_summary.json",
        "experiments/public_issue_corpus_v1/public_issue_repair_readiness_report.md",
        "experiments/public_issue_corpus_v1/public_issue_repair_readiness_summary.json",
        "experiments/public_issue_corpus_v1/public_issue_repair_attempt_report.md",
        "experiments/public_issue_corpus_v1/public_issue_repair_attempt_summary.json",
        "experiments/demo_script.md",
        "experiments/demo_script.json",
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
    ]
    checks = [
        _path_check(
            name="Planning Docs",
            root=project_root,
            paths=required_docs,
            missing_action="Restore the missing planning, safety, release, or process docs.",
            blocked=True,
        ),
        _path_check(
            name="Generated Review Artifacts",
            root=artifacts_dir,
            paths=required_artifacts,
            missing_action="Regenerate index, failure, readiness, demo script, and final evaluation artifacts.",
            blocked=True,
        ),
        _project_status_freshness_check(artifacts_dir),
        _environment_readiness_release_check(artifacts_dir),
        _release_check(
            name="Demo Readiness",
            status="passed" if readiness.readiness_status != "not_ready" else "blocked",
            evidence=(
                f"Readiness is {readiness.readiness_status}; "
                f"{readiness.experiment_count} experiments, {readiness.run_count} runs, "
                f"{readiness.metric_count} metric rows."
            ),
            next_action=(
                "Keep caveats visible in public claims."
                if readiness.readiness_status != "not_ready"
                else "Resolve missing readiness gates before launch."
            ),
        ),
        _release_check(
            name="Failure Visibility",
            status="passed" if readiness.runs_requiring_attention > 0 else "warning",
            evidence=(
                f"{readiness.runs_requiring_attention} runs requiring attention; "
                f"categories: {_failure_summary(readiness.failure_categories)}."
            ),
            next_action=(
                "Use failure cases in the final narrative."
                if readiness.runs_requiring_attention > 0
                else "Preserve at least one failure example for honest evaluation."
            ),
        ),
        _release_check(
            name="Live LLM Claim Boundary",
            status="warning" if not _live_providers(readiness.model_providers) else "passed",
            evidence=_provider_summary(readiness.model_providers),
            next_action=(
                "Do not claim live LLM calibration in release materials."
                if not _live_providers(readiness.model_providers)
                else "Report token usage and cost next to live-provider quality metrics."
            ),
        ),
        _git_repository_check(project_root),
        _packaging_config_check(project_root),
        _release_check(
            name="CI Workflow",
            status="passed" if (project_root / ".github" / "workflows").exists() else "warning",
            evidence=(
                ".github/workflows exists."
                if (project_root / ".github" / "workflows").exists()
                else "No CI workflow directory found."
            ),
            next_action=(
                "Keep pytest and artifact checks in CI."
                if (project_root / ".github" / "workflows").exists()
                else "Add a CI workflow before public repository release."
            ),
        ),
        _release_check(
            name="Demo Media",
            status="passed" if _has_demo_media(project_root) else "warning",
            evidence=(
                "Demo media asset found."
                if _has_demo_media(project_root)
                else "No GIF, MP4, or screenshot asset found under docs, artifacts, or assets."
            ),
            next_action=(
                "Reference the media in README."
                if _has_demo_media(project_root)
                else "Capture a screenshot, GIF, or short video from the generated demo script."
            ),
        ),
        _release_check(
            name="Architecture Diagram Asset",
            status="passed" if _has_architecture_diagram(project_root) else "warning",
            evidence=(
                "Architecture diagram evidence found."
                if _has_architecture_diagram(project_root)
                else "No Mermaid block or diagram asset found in architecture surfaces."
            ),
            next_action=(
                "Keep diagram synchronized with architecture docs."
                if _has_architecture_diagram(project_root)
                else "Add a simple architecture diagram before public launch."
            ),
        ),
        _content_check(
            name="Public Claim Caveats",
            path=project_root / "README.md",
            needles=["ready_with_caveats", "offline", "live LLM calibration"],
            missing_action="Update README so live-provider and offline-demo caveats are visible.",
            blocked=False,
        ),
    ]
    return checks


def _path_check(
    *,
    name: str,
    root: Path,
    paths: list[str],
    missing_action: str,
    blocked: bool,
) -> ReleaseHygieneCheck:
    missing = [path for path in paths if not (root / path).exists()]
    status = "blocked" if blocked and missing else "warning" if missing else "passed"
    evidence = (
        f"Found {len(paths) - len(missing)}/{len(paths)} required paths."
        if missing
        else f"All {len(paths)} required paths found."
    )
    if missing:
        evidence += f" Missing: {', '.join(missing)}."
    return _release_check(
        name=name,
        status=status,
        evidence=evidence,
        next_action="No action needed." if not missing else missing_action,
    )


def _content_check(
    *,
    name: str,
    path: Path,
    needles: list[str],
    missing_action: str,
    blocked: bool,
) -> ReleaseHygieneCheck:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    missing = [needle for needle in needles if needle not in text]
    status = "blocked" if blocked and missing else "warning" if missing else "passed"
    return _release_check(
        name=name,
        status=status,
        evidence=(
            f"All {len(needles)} caveat markers found."
            if not missing
            else f"Missing markers: {', '.join(missing)}."
        ),
        next_action="No action needed." if not missing else missing_action,
    )


def _project_status_freshness_check(artifacts_dir: Path) -> ReleaseHygieneCheck:
    payload = _load_json_artifact(artifacts_dir / "experiments" / "project_status.json")
    if payload is None:
        return _release_check(
            name="Project Status Freshness",
            status="blocked",
            evidence="Project status JSON is missing or invalid.",
            next_action="Run `project-status` or `refresh-evidence` before release review.",
        )

    freshness_status = _payload_string(payload, "evidence_freshness_status", "undated")
    stale_count = _payload_int(payload, "stale_source_count")
    undated_count = _payload_int(payload, "undated_source_count")
    missing_count = len(_payload_string_list(payload, "missing_sources"))
    if freshness_status in {"missing", "stale"} or missing_count:
        status = "blocked"
        next_action = (
            "Regenerate missing or stale evidence with `refresh-evidence` before "
            "claiming release readiness."
        )
    elif freshness_status == "undated" or undated_count:
        status = "warning"
        next_action = "Regenerate undated evidence so release claims have timestamped sources."
    else:
        status = "passed"
        next_action = "No action needed."
    return _release_check(
        name="Project Status Freshness",
        status=status,
        evidence=(
            f"Freshness is {freshness_status}; {stale_count} stale, "
            f"{undated_count} undated, {missing_count} missing sources."
        ),
        next_action=next_action,
    )


def _environment_readiness_release_check(artifacts_dir: Path) -> ReleaseHygieneCheck:
    payload = _load_json_artifact(artifacts_dir / "experiments" / "environment_readiness.json")
    if payload is None:
        return _release_check(
            name="Environment Readiness",
            status="blocked",
            evidence="Environment readiness JSON is missing or invalid.",
            next_action=(
                "Run `environment-readiness` or `refresh-evidence` before release review."
            ),
        )
    readiness_status = _payload_string(payload, "readiness_status", "missing")
    passed_count = _payload_int(payload, "passed_count")
    warning_count = _payload_int(payload, "warning_count")
    blocked_count = _payload_int(payload, "blocked_count")
    if readiness_status == "ready":
        status = "passed"
        next_action = "No action needed."
    elif readiness_status == "ready_with_warnings":
        status = "warning"
        next_action = "Keep environment caveats visible in release notes."
    elif readiness_status == "blocked":
        status = "warning"
        next_action = (
            "Resolve environment blockers before public launch; keep launch claims "
            "scoped to saved offline evidence."
        )
    else:
        status = "blocked"
        next_action = "Regenerate environment readiness before release review."
    return _release_check(
        name="Environment Readiness",
        status=status,
        evidence=(
            f"Environment readiness is {readiness_status}; {passed_count} passed, "
            f"{warning_count} warnings, {blocked_count} blocked."
        ),
        next_action=next_action,
    )


def _release_check(
    *,
    name: str,
    status: str,
    evidence: str,
    next_action: str,
) -> ReleaseHygieneCheck:
    return ReleaseHygieneCheck(
        name=name,
        status=status,
        evidence=evidence,
        next_action=next_action,
    )


def _git_repository_check(project_root: Path) -> ReleaseHygieneCheck:
    if not (project_root / ".git").exists():
        return _release_check(
            name="Git Repository",
            status="blocked",
            evidence="No .git directory found at project root.",
            next_action="Initialize or restore the Git repository before claiming a stable tagged release.",
        )

    head = _run_git(project_root, "rev-parse", "--short", "HEAD")
    if head.returncode != 0:
        return _release_check(
            name="Git Repository",
            status="blocked",
            evidence="Git repository exists but has no commit yet.",
            next_action="Create a verified baseline commit before claiming a stable tagged release.",
        )

    branch = _run_git(project_root, "branch", "--show-current")
    status = _run_git(project_root, "status", "--porcelain", "--untracked-files=all")
    if status.returncode != 0:
        return _release_check(
            name="Git Repository",
            status="blocked",
            evidence=(
                f"Could not inspect Git worktree: {status.stderr.strip() or status.stdout.strip()}"
            ),
            next_action="Fix Git metadata before claiming release readiness.",
        )
    if status.stdout.strip():
        changed_count = len([line for line in status.stdout.splitlines() if line.strip()])
        return _release_check(
            name="Git Repository",
            status="blocked",
            evidence=f"Git commit {head.stdout.strip()} has {changed_count} uncommitted file changes.",
            next_action="Commit, stash, or intentionally remove worktree changes before tagging a release.",
        )

    branch_name = branch.stdout.strip() or "detached HEAD"
    return _release_check(
        name="Git Repository",
        status="passed",
        evidence=f"Git commit {head.stdout.strip()} on {branch_name}; worktree clean.",
        next_action="Create a tag only after final verification.",
    )


def _packaging_config_check(project_root: Path) -> ReleaseHygieneCheck:
    pyproject_path = project_root / "pyproject.toml"
    try:
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except OSError:
        return _release_check(
            name="Packaging Config",
            status="blocked",
            evidence="pyproject.toml is missing.",
            next_action="Restore project package metadata before release.",
        )
    except tomllib.TOMLDecodeError as error:
        return _release_check(
            name="Packaging Config",
            status="blocked",
            evidence=f"pyproject.toml could not be parsed: {error}",
            next_action="Fix package metadata before release.",
        )

    project = pyproject.get("project", {})
    optional_deps = project.get("optional-dependencies", {})
    dev_extra = optional_deps.get("dev", [])
    wheel = (
        pyproject.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
    )
    wheel_packages = wheel.get("packages", [])
    project_name = project.get("name")
    project_version = project.get("version")
    missing: list[str] = []
    if not project_name:
        missing.append("project.name")
    if not project_version:
        missing.append("project.version")
    if "src/patchsmith" not in wheel_packages:
        missing.append("tool.hatch.build.targets.wheel.packages includes src/patchsmith")
    if not _dependency_present(dev_extra, "pytest"):
        missing.append("project.optional-dependencies.dev includes pytest")
    if not _dependency_present(dev_extra, "build"):
        missing.append("project.optional-dependencies.dev includes build")

    if missing:
        return _release_check(
            name="Packaging Config",
            status="blocked",
            evidence=f"Missing package metadata: {', '.join(missing)}.",
            next_action="Fix pyproject package metadata before claiming release readiness.",
        )

    return _release_check(
        name="Packaging Config",
        status="passed",
        evidence=(
            f"{project_name} {project_version}; wheel packages {', '.join(wheel_packages)}; "
            "dev extra includes pytest and build."
        ),
        next_action="Keep package build validation in CI.",
    )


def _dependency_present(dependencies: list[Any], package_name: str) -> bool:
    prefix = package_name.lower()
    for dependency in dependencies:
        if isinstance(dependency, str) and dependency.lower().startswith(prefix):
            return True
    return False


def _run_git(project_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )


def _has_demo_media(project_root: Path) -> bool:
    search_roots = [
        project_root / "docs",
        project_root / "artifacts",
        project_root / "assets",
    ]
    suffixes = {".gif", ".mp4", ".mov", ".png", ".jpg", ".jpeg", ".webp"}
    for root in search_roots:
        if not root.exists():
            continue
        if any(path.suffix.lower() in suffixes for path in root.rglob("*")):
            return True
    return False


def _has_architecture_diagram(project_root: Path) -> bool:
    architecture_path = project_root / "docs" / "03_architecture.md"
    try:
        architecture_text = architecture_path.read_text(encoding="utf-8")
    except OSError:
        architecture_text = ""
    if "```mermaid" in architecture_text:
        return True
    diagram_roots = [project_root / "docs", project_root / "assets"]
    suffixes = {".svg", ".png", ".jpg", ".jpeg", ".webp"}
    for root in diagram_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if "arch" in path.name.lower() and path.suffix.lower() in suffixes:
                return True
    return False


__all__ = ["release_hygiene_checks"]
