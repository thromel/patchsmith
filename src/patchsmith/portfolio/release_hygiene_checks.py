"""Release hygiene check builders."""

from __future__ import annotations

from pathlib import Path

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
from patchsmith.portfolio.release_hygiene_project_checks import (
    _git_repository_check,
    _has_architecture_diagram,
    _has_demo_media,
    _packaging_config_check,
)
from patchsmith.portfolio.release_hygiene_requirements import (
    REQUIRED_RELEASE_ARTIFACTS,
    REQUIRED_RELEASE_DOCS,
)
from patchsmith.portfolio.release_hygiene_support import (
    _content_check,
    _path_check,
    _release_check,
)


def release_hygiene_checks(
    *,
    project_root: Path,
    artifacts_dir: Path,
    readiness: DemoReadinessReport,
) -> list[ReleaseHygieneCheck]:
    checks = [
        _path_check(
            name="Planning Docs",
            root=project_root,
            paths=REQUIRED_RELEASE_DOCS,
            missing_action="Restore the missing planning, safety, release, or process docs.",
            blocked=True,
        ),
        _path_check(
            name="Generated Review Artifacts",
            root=artifacts_dir,
            paths=REQUIRED_RELEASE_ARTIFACTS,
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


__all__ = ["release_hygiene_checks"]
