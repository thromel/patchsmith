"""MVP progress checklist section builders."""

from __future__ import annotations

from pathlib import Path

from patchsmith.portfolio._helpers import (
    _failure_summary,
    _file_contains,
    _path_exists,
)
from patchsmith.portfolio.models import MvpProgressItem
from patchsmith.portfolio.mvp_progress_evidence import MvpProgressEvidence
from patchsmith.portfolio.mvp_progress_item_factory import mvp_item


def mvp_core_flow_items(evidence: MvpProgressEvidence) -> list[MvpProgressItem]:
    project_root = evidence.project_root
    return [
        mvp_item(
            "Core flow",
            "User can submit repository URL and issue text.",
            "passed" if _cli_has_run_inputs(project_root) else "missing",
            "CLI `run` exposes repository and issue inputs.",
            "Keep the run CLI stable.",
        ),
        mvp_item(
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
        mvp_item(
            "Core flow",
            "System records commit hash.",
            "passed"
            if _file_contains(project_root / "src" / "patchsmith" / "models.py", "commit_hash")
            else "missing",
            "Repository snapshots include `commit_hash`.",
            "Keep commit metadata visible in reports.",
        ),
        mvp_item(
            "Core flow",
            "System builds basic file index.",
            "passed"
            if _file_contains(project_root / "src" / "patchsmith" / "ingest.py", "index_repository")
            else "missing",
            "`index_repository` exists and is used by CLI/evaluation flows.",
            "Keep index output covered by tests.",
        ),
        mvp_item(
            "Core flow",
            "System retrieves candidate files.",
            "passed" if evidence.has_retrieval else "missing",
            f"Retrieval metric evidence {'exists' if evidence.has_retrieval else 'is missing'}.",
            "Run `eval-retrieval` if retrieval evidence is missing.",
        ),
        mvp_item(
            "Core flow",
            "DeepAgents repair loop runs.",
            "passed" if evidence.has_deepagents else "missing",
            f"DeepAgents metric lanes {'exist' if evidence.has_deepagents else 'are missing'}.",
            "Run `eval-repair --runtime deepagents` if missing.",
        ),
        mvp_item(
            "Core flow",
            "Agent can read files through bounded tool.",
            "passed" if evidence.has_retrieval else "missing",
            (
                "Bounded retrieved-context contracts provide controlled repository "
                "file excerpts to the repair runtime."
            ),
            "Keep file access bounded and consider a first-class read tool before broad repos.",
        ),
        mvp_item(
            "Core flow",
            "Agent can apply patch through controlled tool.",
            "passed"
            if evidence.has_repair
            and _file_contains(
                project_root / "src" / "patchsmith" / "patching.py", "apply_text_replacement"
            )
            else "missing",
            "`apply_text_replacement` and repair/scaffold metrics exist.",
            "Keep patch application path-validated and tested.",
        ),
        mvp_item(
            "Core flow",
            "Tests run in Docker sandbox.",
            (
                "passed"
                if evidence.docker_smoke_count
                else "warning"
                if evidence.has_docker_runner
                else "missing"
            ),
            (
                f"{evidence.docker_smoke_count} saved Docker sandbox success trace(s)."
                if evidence.docker_smoke_count
                else (
                    f"Opt-in Docker runner exists; latest `docker-smoke` status is "
                    f"`{evidence.latest_docker_smoke_status}`."
                    if evidence.latest_docker_smoke_status
                    else "Opt-in Docker runner exists, but no saved Docker-mode success trace was found."
                )
            ),
            "Run a Docker-mode seeded smoke when the Docker daemon and image are available.",
        ),
        mvp_item(
            "Core flow",
            "Final diff is generated.",
            "passed" if evidence.has_diff else "missing",
            f"{evidence.run_artifact_diffs} saved run diff artifact(s) discovered.",
            "Run a repair/scaffold evaluation if diffs are missing.",
        ),
        mvp_item(
            "Core flow",
            "Markdown run report is generated.",
            "passed" if evidence.has_report else "missing",
            f"{evidence.run_artifact_reports} saved run report artifact(s) discovered.",
            "Run a repair/scaffold evaluation if reports are missing.",
        ),
    ]


def mvp_observability_items(evidence: MvpProgressEvidence) -> list[MvpProgressItem]:
    return [
        mvp_item(
            "Observability",
            "Run status is persisted.",
            "passed" if evidence.has_run else "missing",
            f"{evidence.run_count} saved run artifact(s) discovered.",
            "Run at least one repair/scaffold evaluation if missing.",
        ),
        mvp_item(
            "Observability",
            "Retrieved context is saved.",
            "passed" if evidence.has_retrieval and evidence.has_report else "missing",
            "Retrieval metrics and run reports are present.",
            "Regenerate retrieval and run artifacts if missing.",
        ),
        mvp_item(
            "Observability",
            "Tool calls are logged.",
            "passed" if evidence.has_trace else "missing",
            f"{evidence.run_artifact_traces} trace artifact(s) discovered.",
            "Keep runtime/tool events in `traces.jsonl`.",
        ),
        mvp_item(
            "Observability",
            "Sandbox commands are logged.",
            "passed" if evidence.has_trace else "missing",
            "Saved traces include workflow events for sandbox command execution.",
            "Run workflow tests if sandbox trace events are missing.",
        ),
        mvp_item(
            "Observability",
            "Test output is saved.",
            "passed" if evidence.has_test_output else "missing",
            "Saved runs include stdout/stderr artifacts.",
            "Ensure sandbox command output stays persisted.",
        ),
        mvp_item(
            "Observability",
            "Cost is estimated.",
            "passed" if evidence.has_cost else "warning",
            (
                "At least one metric row has estimated cost."
                if evidence.has_cost
                else "Offline evidence exists, but live-provider cost is not calibrated."
            ),
            "Set cost-rate env vars for publishable live-provider calibration.",
        ),
        mvp_item(
            "Observability",
            "Latency is recorded.",
            "passed" if evidence.has_latency else "missing",
            "Normalized metrics include latency values.",
            "Keep latency in trace and summary artifacts.",
        ),
    ]


def mvp_safety_items(evidence: MvpProgressEvidence) -> list[MvpProgressItem]:
    project_root = evidence.project_root
    return [
        mvp_item(
            "Safety",
            "No host secrets are mounted.",
            "passed"
            if evidence.has_docker_runner
            and _file_contains(
                project_root / "src" / "patchsmith" / "sandbox.py", "_docker_host_env"
            )
            else "missing",
            "Docker and local runners use sanitized environment helpers.",
            "Keep env filtering covered by security tests.",
        ),
        mvp_item(
            "Safety",
            "Command allowlist exists.",
            "passed"
            if _file_contains(project_root / "src" / "patchsmith" / "security.py", "CommandPolicy")
            else "missing",
            "`CommandPolicy` exists.",
            "Keep command policy narrow.",
        ),
        mvp_item(
            "Safety",
            "Timeout exists.",
            "passed"
            if _file_contains(project_root / "src" / "patchsmith" / "sandbox.py", "timeout_seconds")
            else "missing",
            "Sandbox runners enforce `timeout_seconds`.",
            "Keep timeout tests for local and Docker paths.",
        ),
        mvp_item(
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
        mvp_item(
            "Safety",
            "Unsafe command rejection test exists.",
            "passed"
            if _file_contains(project_root / "tests" / "test_security.py", "rejects_shell_chaining")
            else "missing",
            "Security tests cover shell chaining rejection.",
            "Keep unsafe-command tests in CI.",
        ),
    ]


def mvp_evaluation_items(evidence: MvpProgressEvidence) -> list[MvpProgressItem]:
    return [
        mvp_item(
            "Evaluation",
            "At least 5 seeded bugs exist.",
            "passed" if evidence.seeded_task_count >= 5 else "missing",
            f"{evidence.seeded_task_count} seeded bug task(s) found.",
            "Add seeded tasks if the suite drops below five.",
        ),
        mvp_item(
            "Evaluation",
            "Live LLM calibration has been run.",
            "passed" if evidence.calibration.saved_live_provider_count else "warning",
            (
                f"{evidence.calibration.saved_live_provider_count} saved live-provider run(s)."
                if evidence.calibration.saved_live_provider_count
                else "No non-offline model-provider run was found in saved artifacts."
            ),
            "Run a credential-gated calibration with budget and provider settings.",
        ),
        mvp_item(
            "Evaluation",
            "Evaluation runner can run the seeded suite.",
            "passed" if evidence.has_repair and evidence.has_patch_search else "missing",
            "Repair/scaffold and patch-search metric evidence exists.",
            "Run repair/scaffold and patch-search evaluations if missing.",
        ),
        mvp_item(
            "Evaluation",
            "Results table includes success, cost, latency, and failure category.",
            (
                "passed"
                if evidence.readiness.metric_count and evidence.failure_report.category_counts
                else "warning"
            ),
            (
                f"{evidence.readiness.metric_count} metric row(s); failure categories: "
                f"{_failure_summary(evidence.failure_report.category_counts)}."
            ),
            "Keep final, failure, and artifact-index reports regenerated together.",
        ),
    ]


def mvp_portfolio_items(evidence: MvpProgressEvidence) -> list[MvpProgressItem]:
    project_root = evidence.project_root
    return [
        mvp_item(
            "Portfolio",
            "README explains the project in under 60 seconds.",
            "passed" if _path_exists(project_root / "README.md") else "missing",
            "README exists and includes quickstart/current-status sections.",
            "Keep README caveats synchronized with generated reports.",
        ),
        mvp_item(
            "Portfolio",
            "Real-world task breadth is proven.",
            (
                "passed"
                if evidence.issue_corpus_count >= 3
                else "warning"
                if evidence.seeded_task_count >= 5 and evidence.has_repair
                else "missing"
            ),
            (
                f"{evidence.issue_corpus_count} validated public issue candidate(s) found."
                if evidence.issue_corpus_count
                else (
                    f"{evidence.seeded_task_count} seeded bug task(s) exist; no saved real-world "
                    "issue corpus artifact was found."
                )
            ),
            "Generate the public issue corpus validation report.",
        ),
        mvp_item(
            "Portfolio",
            "Architecture diagram exists.",
            "passed"
            if _file_contains(project_root / "docs" / "03_architecture.md", "```mermaid")
            else "missing",
            "Architecture doc includes a Mermaid diagram.",
            "Keep architecture docs synchronized with runtime adapters.",
        ),
    ]


def _cli_has_run_inputs(project_root: Path) -> bool:
    cli_dir = project_root / "src" / "patchsmith" / "cli"
    run_commands_path = cli_dir / "commands" / "run.py"
    args_path = cli_dir / "_args.py"
    if not run_commands_path.exists() or not args_path.exists():
        return False
    run_text = run_commands_path.read_text(encoding="utf-8")
    args_text = args_path.read_text(encoding="utf-8")
    return 'run = subparsers.add_parser("run"' in run_text and "--repo" in args_text


__all__ = [
    "mvp_core_flow_items",
    "mvp_evaluation_items",
    "mvp_observability_items",
    "mvp_portfolio_items",
    "mvp_safety_items",
]
