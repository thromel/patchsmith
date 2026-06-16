"""Public demo and artifact-inspection commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from patchsmith.artifacts import load_json, write_json, write_markdown
from patchsmith.cli._types import CommandHandler
from patchsmith.evaluation.seeded import load_seeded_tasks
from patchsmith.evaluation_models import SeededTask
from patchsmith.models import RepairRunResult, RunRequest
from patchsmith.workflow import RepairRunner

DEMO_NAME = "seeded-logic-bug"
DEMO_TASK_ID = "task_001_logic_bug"
DEMO_DATASET = Path("evals/tasks/seeded_bugs_v1")
DEMO_CLAIM_BOUNDARY = "focused_validation_only"


def register(subparsers: argparse._SubParsersAction) -> dict[str, CommandHandler]:
    demo = subparsers.add_parser(
        "demo",
        help="Run a canonical PatchSmith demo lane and print inspectable artifacts.",
    )
    demo.add_argument(
        "name",
        nargs="?",
        choices=[DEMO_NAME],
        default=DEMO_NAME,
        help="Demo lane to run.",
    )
    demo.add_argument(
        "--artifacts-dir",
        default="artifacts/demo/seeded_logic_bug",
        help="Artifact output directory for the demo run.",
    )
    demo.add_argument("--json", action="store_true", help="Print machine-readable output.")

    inspect = subparsers.add_parser(
        "inspect",
        help="Summarize a PatchSmith run directory or run id.",
    )
    inspect.add_argument("run", help="Run directory path, or run id under --artifacts-dir/runs.")
    inspect.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Artifact root used when resolving a bare run id.",
    )
    inspect.add_argument("--json", action="store_true", help="Print machine-readable output.")

    return {
        "demo": _demo_command,
        "inspect": _inspect_command,
    }


def _demo_command(args: argparse.Namespace) -> int:
    task = _load_demo_task(DEMO_TASK_ID)
    output_dir = Path(args.artifacts_dir)
    result = RepairRunner(artifacts_dir=output_dir).run(
        RunRequest(
            repo=str(task.repo),
            issue_text=task.issue_text,
            test_command=task.test_command,
            runtime="heuristic",
            planner="heuristic",
            context_provider="native_hybrid",
            retrieval_strategy="native_hybrid",
            sandbox_mode="local",
        )
    )
    metadata_path = _write_demo_metadata(
        result=result,
        demo_name=args.name,
        task_id=task.task_id,
        task_dir=task.task_dir,
    )
    index_path = _write_artifact_index(
        result=result,
        metadata_path=metadata_path,
        demo_name=args.name,
    )
    payload = _inspect_payload(result.run_dir)
    payload["demo"] = args.name
    payload["metadata_path"] = str(metadata_path)
    payload["artifact_index_path"] = str(index_path)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(_format_demo_payload(payload))
    return 0


def _inspect_command(args: argparse.Namespace) -> int:
    run_dir = _resolve_run_dir(args.run, artifacts_dir=Path(args.artifacts_dir))
    if run_dir is None:
        print(f"run not found: {args.run}")
        return 2
    payload = _inspect_payload(run_dir)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(_format_inspect_payload(payload))
    return 0


def _load_demo_task(task_id: str) -> SeededTask:
    for task in load_seeded_tasks(DEMO_DATASET):
        if task.task_id == task_id:
            return task
    raise FileNotFoundError(f"demo task not found: {task_id}")


def _write_demo_metadata(
    *,
    result: RepairRunResult,
    demo_name: str,
    task_id: str,
    task_dir: Path,
) -> Path:
    payload = _run_result_payload(result, runtime="heuristic", planner="heuristic")
    selected_context = [context.to_dict() for context in result.retrieved_context]
    write_json(
        result.run_dir / "context" / "selected_files.json", selected_context, trailing_newline=True
    )
    metadata = {
        "schema_version": "patchsmith.demo.v1",
        "demo": demo_name,
        "task_id": task_id,
        "task_dir": str(task_dir),
        "claim_boundary": DEMO_CLAIM_BOUNDARY,
        "claim_boundary_note": (
            "Focused validation passed for the seeded task command; this is not "
            "a claim of broad upstream acceptance."
        ),
        "run": payload,
        "artifacts": {
            "report": str(result.report_path),
            "diff": str(result.final_diff_path),
            "trace": str(result.trace_path),
            "stdout": str(result.run_dir / "logs" / "stdout.txt"),
            "stderr": str(result.run_dir / "logs" / "stderr.txt"),
            "selected_context": str(result.run_dir / "context" / "selected_files.json"),
        },
    }
    metadata_path = result.run_dir / "metadata.json"
    write_json(metadata_path, metadata, trailing_newline=True)
    return metadata_path


def _run_result_payload(
    result: RepairRunResult,
    *,
    runtime: str,
    planner: str,
) -> dict[str, Any]:
    rows = _trace_rows(result.trace_path)
    repair_outcome = _latest_trace_payload(rows, "analyze", "repair_outcome")
    payload: dict[str, Any] = {
        "run_id": result.run_id,
        "status": result.status,
        "runtime": runtime,
        "planner": planner,
        "report_path": str(result.report_path),
        "trace_path": str(result.trace_path),
        "final_diff_path": str(result.final_diff_path),
        "test_exit_code": result.test_result.exit_code if result.test_result else None,
        "retrieved_files": [context.path for context in result.retrieved_context],
        "repair_outcome_status": repair_outcome.get("status"),
        "repair_verdict": repair_outcome.get("verdict"),
        "repair_failure_category": repair_outcome.get("failure_category"),
        "repair_patch_generated": repair_outcome.get("patch_generated"),
        "repair_tests_passed": repair_outcome.get("tests_passed"),
        "repair_next_action": repair_outcome.get("next_action"),
    }
    model_usage = result.model_usage or {}
    if model_usage:
        payload["model_usage"] = dict(model_usage)
        payload["model_call_count"] = model_usage.get("call_count")
        payload["model_response_count"] = model_usage.get("response_count")
        payload["model_total_tokens"] = model_usage.get("total_tokens")
        payload["estimated_cost_usd"] = model_usage.get("estimated_cost_usd")
    return payload


def _write_artifact_index(
    *,
    result: RepairRunResult,
    metadata_path: Path,
    demo_name: str,
) -> Path:
    payload = _inspect_payload(result.run_dir)
    lines = [
        "# PatchSmith Demo Artifact Index",
        "",
        f"- Demo: `{demo_name}`",
        f"- Run ID: `{payload['run_id']}`",
        f"- Status: `{payload['status']}`",
        f"- Verdict: `{payload['repair_verdict']}`",
        f"- Claim boundary: `{payload['claim_boundary']}`",
        f"- Validation: `{payload['validation']}`",
        "",
        "## Files",
        "",
        f"- Report: `{result.report_path}`",
        f"- Diff: `{result.final_diff_path}`",
        f"- Trace: `{result.trace_path}`",
        f"- Metadata: `{metadata_path}`",
        f"- Selected context: `{result.run_dir / 'context' / 'selected_files.json'}`",
        f"- Stdout: `{result.run_dir / 'logs' / 'stdout.txt'}`",
        f"- Stderr: `{result.run_dir / 'logs' / 'stderr.txt'}`",
        "",
        "## Read This First",
        "",
        (
            "This demo is intentionally small. It proves that PatchSmith can select "
            "context, create a bounded patch proposal, run focused validation, and "
            "leave an auditable run directory. It does not claim real public-issue "
            "repair quality."
        ),
        "",
        "Inspect it with:",
        "",
        "```bash",
        f"patchsmith inspect {result.run_dir}",
        "```",
        "",
    ]
    index_path = result.run_dir / "artifact_index.md"
    write_markdown(index_path, "\n".join(lines))
    return index_path


def _resolve_run_dir(value: str, *, artifacts_dir: Path) -> Path | None:
    raw = Path(value).expanduser()
    if raw.is_dir():
        return raw
    candidates = [
        artifacts_dir / "runs" / value,
        artifacts_dir / "demo" / "seeded_logic_bug" / "runs" / value,
        Path("artifacts") / "demo" / "seeded_logic_bug" / "runs" / value,
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def _inspect_payload(run_dir: Path) -> dict[str, Any]:
    metadata = _dict_or_empty(load_json(run_dir / "metadata.json"))
    run_payload = _dict_or_empty(metadata.get("run"))
    trace_rows = _trace_rows(run_dir / "traces.jsonl")
    repair_outcome = _latest_trace_payload(trace_rows, "analyze", "repair_outcome")
    test_payload = _latest_trace_payload(trace_rows, "test", "sandbox_command")
    diff_path = run_dir / "final.diff"
    report_path = run_dir / "report.md"
    changed_files = _changed_files(diff_path)
    validation = _validation_label(test_payload)
    return {
        "run_id": run_payload.get("run_id") or run_dir.name,
        "run_dir": str(run_dir),
        "status": run_payload.get("status") or _latest_status(trace_rows) or "unknown",
        "runtime": run_payload.get("runtime") or "unknown",
        "planner": run_payload.get("planner") or "unknown",
        "repair_verdict": (
            run_payload.get("repair_verdict") or repair_outcome.get("verdict") or "unknown"
        ),
        "failure_category": (
            run_payload.get("repair_failure_category") or repair_outcome.get("failure_category")
        ),
        "patch_generated": bool(
            run_payload.get("repair_patch_generated")
            if "repair_patch_generated" in run_payload
            else diff_path.is_file() and diff_path.read_text(encoding="utf-8").strip()
        ),
        "tests_passed": (
            run_payload.get("repair_tests_passed")
            if "repair_tests_passed" in run_payload
            else _tests_passed(test_payload)
        ),
        "validation": validation,
        "claim_boundary": metadata.get("claim_boundary") or "unknown",
        "changed_files": changed_files,
        "artifacts": {
            "report": str(report_path),
            "diff": str(diff_path),
            "trace": str(run_dir / "traces.jsonl"),
            "metadata": str(run_dir / "metadata.json"),
            "artifact_index": str(run_dir / "artifact_index.md"),
            "stdout": str(run_dir / "logs" / "stdout.txt"),
            "stderr": str(run_dir / "logs" / "stderr.txt"),
            "selected_context": str(run_dir / "context" / "selected_files.json"),
        },
    }


def _trace_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _latest_trace_payload(
    rows: list[dict[str, Any]],
    node_name: str,
    event_type: str,
) -> dict[str, Any]:
    for row in reversed(rows):
        if row.get("node_name") == node_name and row.get("event_type") == event_type:
            return _dict_or_empty(row.get("payload"))
    return {}


def _latest_status(rows: list[dict[str, Any]]) -> str | None:
    for row in reversed(rows):
        status = row.get("status")
        if isinstance(status, str) and status:
            return status
    return None


def _validation_label(test_payload: dict[str, Any]) -> str:
    exit_code = test_payload.get("exit_code")
    if exit_code is None:
        result = _dict_or_empty(test_payload.get("result"))
        exit_code = result.get("exit_code")
    if exit_code is None:
        return "not_recorded"
    return f"exit_code={exit_code}"


def _tests_passed(test_payload: dict[str, Any]) -> bool | None:
    label = _validation_label(test_payload)
    if label == "not_recorded":
        return None
    return label == "exit_code=0"


def _changed_files(diff_path: Path) -> list[str]:
    if not diff_path.is_file():
        return []
    files: list[str] = []
    for line in diff_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("+++ b/"):
            continue
        path = line.removeprefix("+++ b/")
        if path not in files:
            files.append(path)
    return files


def _dict_or_empty(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _format_demo_payload(payload: dict[str, Any]) -> str:
    lines = [
        f"PatchSmith Demo: {payload['demo']}",
        f"Run: {payload['run_dir']}",
        f"Status: {payload['status']}",
        f"Verdict: {payload['repair_verdict']}",
        f"Validation: {payload['validation']}",
        f"Claim boundary: {payload['claim_boundary']}",
        "Artifacts:",
        f"  Report: {payload['artifacts']['report']}",
        f"  Diff: {payload['artifacts']['diff']}",
        f"  Trace: {payload['artifacts']['trace']}",
        f"  Metadata: {payload['metadata_path']}",
        f"  Index: {payload['artifact_index_path']}",
        "",
        f"Inspect: patchsmith inspect {payload['run_dir']}",
    ]
    return "\n".join(lines)


def _format_inspect_payload(payload: dict[str, Any]) -> str:
    tests_passed = payload["tests_passed"]
    tests_passed_label = str(tests_passed).lower() if tests_passed is not None else "unknown"
    lines = [
        "PatchSmith Run Inspect",
        f"Run: {payload['run_id']}",
        f"Status: {payload['status']}",
        f"Runtime: {payload['runtime']}",
        f"Planner: {payload['planner']}",
        f"Verdict: {payload['repair_verdict']}",
        f"Failure category: {payload['failure_category'] or 'n/a'}",
        f"Patch generated: {str(payload['patch_generated']).lower()}",
        f"Tests passed: {tests_passed_label}",
        f"Validation: {payload['validation']}",
        f"Claim boundary: {payload['claim_boundary']}",
        f"Changed files: {', '.join(payload['changed_files']) or 'none'}",
        "Artifacts:",
        f"  Report: {payload['artifacts']['report']}",
        f"  Diff: {payload['artifacts']['diff']}",
        f"  Trace: {payload['artifacts']['trace']}",
        f"  Metadata: {payload['artifacts']['metadata']}",
    ]
    return "\n".join(lines)
