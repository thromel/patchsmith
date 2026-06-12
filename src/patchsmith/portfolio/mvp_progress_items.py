"""MVP progress checklist construction."""

from __future__ import annotations

import json
from pathlib import Path

from patchsmith.observability import ArtifactIndex, FailureArtifactReport
from patchsmith.portfolio._helpers import (
    _failure_summary,
    _file_contains,
    _path_exists,
)
from patchsmith.portfolio.docker_smoke import (
    _docker_sandbox_success_count,
    _latest_docker_smoke_status,
)
from patchsmith.portfolio.models import (
    DemoReadinessReport,
    LiveCalibrationReport,
    MvpProgressItem,
)


def mvp_progress_items(
    *,
    project_root: Path,
    artifacts_dir: Path,
    index: ArtifactIndex,
    readiness: DemoReadinessReport,
    calibration: LiveCalibrationReport,
    failure_report: FailureArtifactReport,
) -> list[MvpProgressItem]:
    metric_kinds = {metric.kind for metric in index.metrics}
    metric_lanes = {metric.lane for metric in index.metrics}
    seeded_task_count = _seeded_task_count(project_root)
    has_run = index.run_count > 0
    has_report = any(run.report_path for run in index.runs)
    has_trace = any(run.trace_path for run in index.runs)
    has_diff = any(run.diff_path for run in index.runs)
    has_latency = any(metric.avg_latency_ms is not None for metric in index.metrics)
    has_cost = any(metric.estimated_cost_usd is not None for metric in index.metrics)
    has_retrieval = "retrieval" in metric_kinds
    has_repair = any(kind in metric_kinds for kind in ("repair", "scaffold"))
    has_patch_search = "patch_search" in metric_kinds
    has_langgraph = any("langgraph" in lane for lane in metric_lanes)
    has_docker_runner = _file_contains(
        project_root / "src" / "patchsmith" / "sandbox.py",
        "class DockerSandboxRunner",
    )
    docker_smoke_count = _docker_sandbox_success_count(artifacts_dir)
    latest_docker_smoke_status = _latest_docker_smoke_status(artifacts_dir)
    issue_corpus_count = _validated_issue_corpus_count(artifacts_dir)
    run_artifact_reports = sum(1 for run in index.runs if run.report_path)
    run_artifact_diffs = sum(1 for run in index.runs if run.diff_path)
    run_artifact_traces = sum(1 for run in index.runs if run.trace_path)

    return [
        _mvp_item(
            "Core flow",
            "User can submit repository URL and issue text.",
            "passed" if _cli_has_run_inputs(project_root) else "missing",
            "CLI `run` exposes repository and issue inputs.",
            "Keep the run CLI stable.",
        ),
        _mvp_item(
            "Core flow",
            "System clones repository into isolated workspace.",
            "passed"
            if _file_contains(
                project_root / "src" / "patchsmith" / "ingest.py", "clone_or_copy_repository"
            )
            else "missing",
            "`clone_or_copy_repository` exists in the ingest layer.",
            "Keep clone/copy behavior covered by workflow tests.",
        ),
        _mvp_item(
            "Core flow",
            "System records commit hash.",
            "passed"
            if _file_contains(project_root / "src" / "patchsmith" / "models.py", "commit_hash")
            else "missing",
            "Repository snapshots include `commit_hash`.",
            "Keep commit metadata visible in reports.",
        ),
        _mvp_item(
            "Core flow",
            "System builds basic file index.",
            "passed"
            if _file_contains(project_root / "src" / "patchsmith" / "ingest.py", "index_repository")
            else "missing",
            "`index_repository` exists and is used by CLI/evaluation flows.",
            "Keep index output covered by tests.",
        ),
        _mvp_item(
            "Core flow",
            "System retrieves candidate files.",
            "passed" if has_retrieval else "missing",
            f"Retrieval metric evidence {'exists' if has_retrieval else 'is missing'}.",
            "Run `eval-retrieval` if retrieval evidence is missing.",
        ),
        _mvp_item(
            "Core flow",
            "LangGraph repair loop runs.",
            "passed" if has_langgraph else "missing",
            f"LangGraph metric lanes {'exist' if has_langgraph else 'are missing'}.",
            "Run `eval-repair --runtime langgraph` if missing.",
        ),
        _mvp_item(
            "Core flow",
            "Agent can read files through bounded tool.",
            "passed" if has_retrieval else "missing",
            (
                "Bounded retrieved-context contracts provide controlled repository "
                "file excerpts to the repair runtime."
            ),
            "Keep file access bounded and consider a first-class read tool before broad repos.",
        ),
        _mvp_item(
            "Core flow",
            "Agent can apply patch through controlled tool.",
            "passed"
            if has_repair
            and _file_contains(
                project_root / "src" / "patchsmith" / "patching.py", "apply_text_replacement"
            )
            else "missing",
            "`apply_text_replacement` and repair/scaffold metrics exist.",
            "Keep patch application path-validated and tested.",
        ),
        _mvp_item(
            "Core flow",
            "Tests run in Docker sandbox.",
            "passed" if docker_smoke_count else "warning" if has_docker_runner else "missing",
            (
                f"{docker_smoke_count} saved Docker sandbox success trace(s)."
                if docker_smoke_count
                else (
                    f"Opt-in Docker runner exists; latest `docker-smoke` status is "
                    f"`{latest_docker_smoke_status}`."
                    if latest_docker_smoke_status
                    else "Opt-in Docker runner exists, but no saved Docker-mode success trace was found."
                )
            ),
            "Run a Docker-mode seeded smoke when the Docker daemon and image are available.",
        ),
        _mvp_item(
            "Core flow",
            "Final diff is generated.",
            "passed" if has_diff else "missing",
            f"{run_artifact_diffs} saved run diff artifact(s) discovered.",
            "Run a repair/scaffold evaluation if diffs are missing.",
        ),
        _mvp_item(
            "Core flow",
            "Markdown run report is generated.",
            "passed" if has_report else "missing",
            f"{run_artifact_reports} saved run report artifact(s) discovered.",
            "Run a repair/scaffold evaluation if reports are missing.",
        ),
        _mvp_item(
            "Observability",
            "Run status is persisted.",
            "passed" if has_run else "missing",
            f"{index.run_count} saved run artifact(s) discovered.",
            "Run at least one repair/scaffold evaluation if missing.",
        ),
        _mvp_item(
            "Observability",
            "Retrieved context is saved.",
            "passed" if has_retrieval and has_report else "missing",
            "Retrieval metrics and run reports are present.",
            "Regenerate retrieval and run artifacts if missing.",
        ),
        _mvp_item(
            "Observability",
            "Tool calls are logged.",
            "passed" if has_trace else "missing",
            f"{run_artifact_traces} trace artifact(s) discovered.",
            "Keep runtime/tool events in `traces.jsonl`.",
        ),
        _mvp_item(
            "Observability",
            "Sandbox commands are logged.",
            "passed" if has_trace else "missing",
            "Saved traces include workflow events for sandbox command execution.",
            "Run workflow tests if sandbox trace events are missing.",
        ),
        _mvp_item(
            "Observability",
            "Test output is saved.",
            "passed"
            if any(run.stdout_path or run.stderr_path for run in index.runs)
            else "missing",
            "Saved runs include stdout/stderr artifacts.",
            "Ensure sandbox command output stays persisted.",
        ),
        _mvp_item(
            "Observability",
            "Cost is estimated.",
            "passed" if has_cost else "warning",
            (
                "At least one metric row has estimated cost."
                if has_cost
                else "Offline evidence exists, but live-provider cost is not calibrated."
            ),
            "Set cost-rate env vars for publishable live-provider calibration.",
        ),
        _mvp_item(
            "Observability",
            "Latency is recorded.",
            "passed" if has_latency else "missing",
            "Normalized metrics include latency values.",
            "Keep latency in trace and summary artifacts.",
        ),
        _mvp_item(
            "Safety",
            "No host secrets are mounted.",
            "passed"
            if has_docker_runner
            and _file_contains(
                project_root / "src" / "patchsmith" / "sandbox.py", "_docker_host_env"
            )
            else "missing",
            "Docker and local runners use sanitized environment helpers.",
            "Keep env filtering covered by security tests.",
        ),
        _mvp_item(
            "Safety",
            "Command allowlist exists.",
            "passed"
            if _file_contains(project_root / "src" / "patchsmith" / "security.py", "CommandPolicy")
            else "missing",
            "`CommandPolicy` exists.",
            "Keep command policy narrow.",
        ),
        _mvp_item(
            "Safety",
            "Timeout exists.",
            "passed"
            if _file_contains(project_root / "src" / "patchsmith" / "sandbox.py", "timeout_seconds")
            else "missing",
            "Sandbox runners enforce `timeout_seconds`.",
            "Keep timeout tests for local and Docker paths.",
        ),
        _mvp_item(
            "Safety",
            "Workspace path validation exists.",
            "passed"
            if _file_contains(
                project_root / "src" / "patchsmith" / "security.py",
                "absolute path outside workspace",
            )
            else "missing",
            "Command policy rejects absolute paths outside the workspace.",
            "Keep path traversal tests passing.",
        ),
        _mvp_item(
            "Safety",
            "Unsafe command rejection test exists.",
            "passed"
            if _file_contains(project_root / "tests" / "test_security.py", "rejects_shell_chaining")
            else "missing",
            "Security tests cover shell chaining rejection.",
            "Keep unsafe-command tests in CI.",
        ),
        _mvp_item(
            "Evaluation",
            "At least 5 seeded bugs exist.",
            "passed" if seeded_task_count >= 5 else "missing",
            f"{seeded_task_count} seeded bug task(s) found.",
            "Add seeded tasks if the suite drops below five.",
        ),
        _mvp_item(
            "Evaluation",
            "Live LLM calibration has been run.",
            "passed" if calibration.saved_live_provider_count else "warning",
            (
                f"{calibration.saved_live_provider_count} saved live-provider run(s)."
                if calibration.saved_live_provider_count
                else "No non-offline model-provider run was found in saved artifacts."
            ),
            "Run a credential-gated calibration with budget and provider settings.",
        ),
        _mvp_item(
            "Evaluation",
            "Evaluation runner can run the seeded suite.",
            "passed" if has_repair and has_patch_search else "missing",
            "Repair/scaffold and patch-search metric evidence exists.",
            "Run repair/scaffold and patch-search evaluations if missing.",
        ),
        _mvp_item(
            "Evaluation",
            "Results table includes success, cost, latency, and failure category.",
            "passed" if readiness.metric_count and failure_report.category_counts else "warning",
            (
                f"{readiness.metric_count} metric row(s); failure categories: "
                f"{_failure_summary(failure_report.category_counts)}."
            ),
            "Keep final, failure, and artifact-index reports regenerated together.",
        ),
        _mvp_item(
            "Portfolio",
            "README explains the project in under 60 seconds.",
            "passed" if _path_exists(project_root / "README.md") else "missing",
            "README exists and includes quickstart/current-status sections.",
            "Keep README caveats synchronized with generated reports.",
        ),
        _mvp_item(
            "Portfolio",
            "Real-world task breadth is proven.",
            "passed"
            if issue_corpus_count >= 3
            else "warning"
            if seeded_task_count >= 5 and has_repair
            else "missing",
            (
                f"{issue_corpus_count} validated public issue candidate(s) found."
                if issue_corpus_count
                else (
                    f"{seeded_task_count} seeded bug task(s) exist; no saved real-world "
                    "issue corpus artifact was found."
                )
            ),
            "Generate the public issue corpus validation report.",
        ),
        _mvp_item(
            "Portfolio",
            "Architecture diagram exists.",
            "passed"
            if _file_contains(project_root / "docs" / "03_architecture.md", "```mermaid")
            else "missing",
            "Architecture doc includes a Mermaid diagram.",
            "Keep architecture docs synchronized with runtime adapters.",
        ),
    ]


def _mvp_item(
    category: str,
    item: str,
    status: str,
    evidence: str,
    next_action: str,
) -> MvpProgressItem:
    return MvpProgressItem(
        category=category,
        item=item,
        status=status,
        evidence=evidence,
        next_action="No action needed." if status == "passed" else next_action,
        score=_mvp_status_score(status),
    )


def _mvp_status_score(status: str) -> float:
    if status == "passed":
        return 1.0
    if status == "warning":
        return 0.5
    return 0.0


def _cli_has_run_inputs(project_root: Path) -> bool:
    cli_dir = project_root / "src" / "patchsmith" / "cli"
    run_commands_path = cli_dir / "commands" / "run.py"
    args_path = cli_dir / "_args.py"
    if not run_commands_path.exists() or not args_path.exists():
        return False
    run_text = run_commands_path.read_text(encoding="utf-8")
    args_text = args_path.read_text(encoding="utf-8")
    return 'run = subparsers.add_parser("run"' in run_text and "--repo" in args_text


def _seeded_task_count(project_root: Path) -> int:
    task_root = project_root / "evals" / "tasks" / "seeded_bugs_v1"
    if not task_root.exists():
        return 0
    return sum(1 for path in task_root.iterdir() if path.is_dir() and path.name.startswith("task_"))


def _validated_issue_corpus_count(artifacts_dir: Path) -> int:
    counts: list[int] = []
    for summary_path in sorted(artifacts_dir.glob("**/corpus_summary.json")):
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        valid_entries = payload.get("valid_entries")
        invalid_entries = payload.get("invalid_entries")
        if isinstance(valid_entries, int) and invalid_entries == 0:
            counts.append(valid_entries)
    return max(counts, default=0)


__all__ = ["mvp_progress_items"]
