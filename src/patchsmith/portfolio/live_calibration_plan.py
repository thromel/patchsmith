"""Planned run helpers for live-provider calibration."""

from __future__ import annotations

from typing import Any

from patchsmith.portfolio._helpers import _payload_int
from patchsmith.portfolio.models import (
    LiveCalibrationPlanRun,
    LiveCalibrationReport,
)


def calibration_plan_run_counts(payload: dict[str, Any]) -> tuple[int, int, int]:
    runs = payload.get("runs")
    if isinstance(runs, list):
        statuses = [str(run.get("status") or "") for run in runs if isinstance(run, dict)]
        return len(statuses), statuses.count("ready"), statuses.count("blocked")
    return (
        _payload_int(payload, "run_count"),
        _payload_int(payload, "ready_runs"),
        _payload_int(payload, "blocked_runs"),
    )


def live_calibration_plan_runs(
    *,
    openai_sdk_available: bool,
    credentials_configured: bool,
    deepagents_available: bool,
    openai_agents_available: bool,
    saved_live_provider_count: int,
) -> list[LiveCalibrationPlanRun]:
    live_smoke_status = "ready" if openai_sdk_available and credentials_configured else "blocked"
    live_suite_status = (
        "ready"
        if saved_live_provider_count
        else "waiting_for_smoke"
        if live_smoke_status == "ready"
        else "blocked"
    )
    deepagents_live_smoke_status = (
        "ready" if deepagents_available and credentials_configured else "blocked"
    )
    deepagents_live_suite_status = (
        "ready"
        if saved_live_provider_count
        else "waiting_for_smoke"
        if deepagents_live_smoke_status == "ready"
        else "blocked"
    )
    return [
        LiveCalibrationPlanRun(
            name="OpenAI LangGraph single-task smoke",
            stage="required",
            status=live_smoke_status,
            runtime="langgraph",
            planner="openai",
            context_provider="native_hybrid",
            output_path="artifacts/runs/<run_id>",
            requires_credentials=True,
            command=(
                "PYTHONPATH=src python3 -m patchsmith.cli run "
                "--repo evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo "
                "--issue-file evals/tasks/seeded_bugs_v1/task_001_logic_bug/issue.md "
                '--test-command "python3 -m pytest" '
                "--runtime langgraph --planner openai --context-provider native_hybrid "
                "--artifacts-dir artifacts --json"
            ),
            success_evidence=(
                "Run trace contains model_provider `openai_responses`, response metadata, "
                "token counts, and a saved report."
            ),
            claim_boundary="Proves one bounded live planner smoke, not broad repair quality.",
        ),
        LiveCalibrationPlanRun(
            name="OpenAI LangGraph seeded-suite eval",
            stage="follow_up",
            status=live_suite_status,
            runtime="langgraph",
            planner="openai",
            context_provider="native_hybrid",
            output_path="artifacts/experiments/live_openai_repair_eval_v1",
            requires_credentials=True,
            command=(
                "PYTHONPATH=src python3 -m patchsmith.cli eval-repair "
                "--dataset evals/tasks/seeded_bugs_v1 "
                "--runtime langgraph --planner openai --max-tasks 10 "
                "--context-provider native_hybrid "
                "--output artifacts/experiments/live_openai_repair_eval_v1 --json"
            ),
            success_evidence=(
                "Repair evaluation summary includes non-offline model provider metadata "
                "and token/cost rows."
            ),
            claim_boundary=(
                "Supports seeded-suite live-provider calibration only; public-issue "
                "repair claims still require separate artifacts."
            ),
        ),
        LiveCalibrationPlanRun(
            name="DeepAgents native single-task smoke",
            stage="required",
            status=deepagents_live_smoke_status,
            runtime="deepagents",
            planner="deepagents",
            context_provider="native_hybrid",
            output_path="artifacts/runs/<run_id>",
            requires_credentials=True,
            command=(
                "PYTHONPATH=src python3 -m patchsmith.cli run "
                "--repo evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo "
                "--issue-file evals/tasks/seeded_bugs_v1/task_001_logic_bug/issue.md "
                '--test-command "python3 -m pytest" '
                "--runtime deepagents --planner deepagents --max-retries 1 "
                "--context-provider native_hybrid --artifacts-dir artifacts --json"
            ),
            success_evidence=(
                "Run trace contains model_provider `deepagents_openai_chat`, "
                "DeepAgents package-backed runtime trace rows, token counts, and a saved report."
            ),
            claim_boundary=(
                "Proves one native DeepAgents live smoke with bounded PatchSmith patch gating; "
                "does not prove public-issue repair quality."
            ),
        ),
        LiveCalibrationPlanRun(
            name="DeepAgents native seeded-suite eval",
            stage="follow_up",
            status=deepagents_live_suite_status,
            runtime="deepagents",
            planner="deepagents",
            context_provider="native_hybrid",
            output_path="artifacts/experiments/deepagents_native_repair_eval_v1",
            requires_credentials=True,
            command=(
                "PYTHONPATH=src python3 -m patchsmith.cli eval-repair "
                "--dataset evals/tasks/seeded_bugs_v1 "
                "--runtime deepagents --planner deepagents --max-retries 1 --max-tasks 10 "
                "--context-provider native_hybrid "
                "--output artifacts/experiments/deepagents_native_repair_eval_v1 --json"
            ),
            success_evidence=(
                "Repair evaluation summary includes `deepagents_openai_chat` provider metadata, "
                "token/cost rows, and per-task DeepAgents traces."
            ),
            claim_boundary=(
                "Supports seeded-suite native DeepAgents calibration only; public issue repair "
                "claims require the public-issue repair-attempt lane."
            ),
        ),
        LiveCalibrationPlanRun(
            name="DeepAgents package-backed adapter refresh",
            stage="optional",
            status="ready" if deepagents_available else "setup_required",
            runtime="deepagents",
            planner="heuristic",
            context_provider="native_hybrid",
            output_path="artifacts/experiments/deepagents_package_smoke_v1",
            requires_credentials=False,
            command=(
                "PYTHONPATH=src python3 -m patchsmith.cli eval-repair "
                "--dataset evals/tasks/seeded_bugs_v1 "
                "--runtime deepagents --planner heuristic --context-provider native_hybrid "
                "--output artifacts/experiments/deepagents_package_smoke_v1 --json"
            ),
            success_evidence="Trace harness status is `package_available` for DeepAgents rows.",
            claim_boundary=(
                "Proves optional package import compatibility, not live DeepAgents model quality."
            ),
        ),
        LiveCalibrationPlanRun(
            name="OpenAI Agents package-backed adapter refresh",
            stage="optional",
            status="ready" if openai_agents_available else "setup_required",
            runtime="openai_agents",
            planner="heuristic",
            context_provider="native_hybrid",
            output_path="artifacts/experiments/openai_agents_package_smoke_v1",
            requires_credentials=False,
            command=(
                "PYTHONPATH=src python3 -m patchsmith.cli eval-repair "
                "--dataset evals/tasks/seeded_bugs_v1 "
                "--runtime openai_agents --planner heuristic --context-provider native_hybrid "
                "--output artifacts/experiments/openai_agents_package_smoke_v1 --json"
            ),
            success_evidence=(
                "Trace harness status is `package_available` for OpenAI Agents SDK rows."
            ),
            claim_boundary=(
                "Proves optional package import compatibility, not live OpenAI Agents model quality."
            ),
        ),
    ]


def live_calibration_plan_status(
    *,
    readiness: LiveCalibrationReport,
    openai_sdk_available: bool,
    credentials_configured: bool,
) -> str:
    if readiness.calibration_status == "calibrated":
        return "calibrated"
    if openai_sdk_available and credentials_configured:
        return "ready_to_run"
    return "blocked"


def live_calibration_commands() -> list[str]:
    return [
        'python -m pip install -e ".[dev,deepagents]"',
        (
            "PYTHONPATH=src python3 -m patchsmith.cli eval-repair "
            "--dataset evals/tasks/seeded_bugs_v1 "
            "--runtime deepagents --planner heuristic --context-provider native_hybrid "
            "--output artifacts/experiments/deepagents_package_smoke_v1 --json"
        ),
        'python -m pip install -e ".[dev,openai-agents]"',
        (
            "PYTHONPATH=src python3 -m patchsmith.cli eval-repair "
            "--dataset evals/tasks/seeded_bugs_v1 "
            "--runtime openai_agents --planner heuristic --context-provider native_hybrid "
            "--output artifacts/experiments/openai_agents_package_smoke_v1 --json"
        ),
        (
            "export OPENAI_API_KEY=...\n"
            "export PATCHSMITH_OPENAI_MODEL=<model>\n"
            "export PATCHSMITH_DEEPAGENTS_MODEL=<model>\n"
            "export PATCHSMITH_OPENAI_INPUT_COST_PER_1M=<input_rate>\n"
            "export PATCHSMITH_OPENAI_OUTPUT_COST_PER_1M=<output_rate>"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli run "
            "--repo evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo "
            "--issue-file evals/tasks/seeded_bugs_v1/task_001_logic_bug/issue.md "
            '--test-command "python3 -m pytest" '
            "--runtime langgraph --planner openai --context-provider native_hybrid "
            "--artifacts-dir artifacts --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli eval-repair "
            "--dataset evals/tasks/seeded_bugs_v1 "
            "--runtime langgraph --planner openai --max-tasks 10 "
            "--context-provider native_hybrid "
            "--output artifacts/experiments/live_openai_repair_eval_v1 --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli run "
            "--repo evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo "
            "--issue-file evals/tasks/seeded_bugs_v1/task_001_logic_bug/issue.md "
            '--test-command "python3 -m pytest" '
            "--runtime deepagents --planner deepagents --max-retries 1 "
            "--context-provider native_hybrid --artifacts-dir artifacts --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli eval-repair "
            "--dataset evals/tasks/seeded_bugs_v1 "
            "--runtime deepagents --planner deepagents --max-retries 1 --max-tasks 10 "
            "--context-provider native_hybrid "
            "--output artifacts/experiments/deepagents_native_repair_eval_v1 --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli live-calibration "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/calibration_readiness.md "
            "--json-output artifacts/experiments/calibration_readiness.json --json"
        ),
    ]
