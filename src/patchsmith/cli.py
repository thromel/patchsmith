from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from patchsmith.evaluation import (
    run_patch_search_evaluation,
    run_repair_evaluation,
    run_scaffold_comparison,
    run_retrieval_evaluation,
    validate_seeded_dataset,
)
from patchsmith.ingest import clone_or_copy_repository, index_repository
from patchsmith.models import RunRequest
from patchsmith.observability import write_artifact_index, write_failure_report
from patchsmith.portfolio import (
    write_demo_readiness_report,
    write_demo_media_assets,
    write_demo_script_report,
    write_final_evaluation_report,
    write_release_hygiene_report,
)
from patchsmith.retrieval import GraphRetriever, HybridRetriever, KeywordRetriever
from patchsmith.workflow import RepairRunner


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        issue_text = _load_issue_text(args)
        request = RunRequest(
            repo=args.repo,
            issue_text=issue_text,
            issue_url=args.issue_url,
            commit=args.commit,
            branch=args.branch,
            test_command=args.test_command,
            runtime=args.runtime,
            planner=args.planner,
            max_retries=args.max_retries,
            retrieval_strategy=args.context_provider,
            context_provider=args.context_provider,
            top_k=args.top_k,
        )
        result = RepairRunner(artifacts_dir=Path(args.artifacts_dir)).run(request)
        if args.json:
            print(
                json.dumps(
                    {
                        "run_id": result.run_id,
                        "status": result.status,
                        "runtime": args.runtime,
                        "planner": args.planner,
                        "report_path": str(result.report_path),
                        "trace_path": str(result.trace_path),
                        "final_diff_path": str(result.final_diff_path),
                        "test_exit_code": (
                            result.test_result.exit_code if result.test_result else None
                        ),
                        "retrieved_files": [context.path for context in result.retrieved_context],
                    },
                    indent=2,
                )
            )
        else:
            print(f"Run ID: {result.run_id}")
            print(f"Status: {result.status}")
            print(f"Report: {result.report_path}")
            if result.test_result:
                print(f"Test exit code: {result.test_result.exit_code}")
            if result.retrieved_context:
                print("Top retrieved files:")
                for context in result.retrieved_context[:5]:
                    print(f"  {context.rank}. {context.path} ({context.score:.2f})")
        return 0

    if args.command == "index":
        with tempfile.TemporaryDirectory(prefix="patchsmith-index-") as tmp_dir:
            repo_path = clone_or_copy_repository(
                args.repo,
                Path(tmp_dir) / "repo",
                commit=args.commit,
                branch=args.branch,
            ).repo_path
            repo_index = index_repository(repo_path)
            print(json.dumps(repo_index.to_dict(), indent=2))
        return 0

    if args.command == "retrieve":
        issue_text = _load_issue_text(args)
        with tempfile.TemporaryDirectory(prefix="patchsmith-retrieve-") as tmp_dir:
            snapshot = clone_or_copy_repository(
                args.repo,
                Path(tmp_dir) / "repo",
                commit=args.commit,
                branch=args.branch,
            )
            repo_index = index_repository(snapshot.repo_path)
            retriever = _retriever_for(args.retrieval)
            contexts = retriever.retrieve(
                repo_path=snapshot.repo_path,
                repo_index=repo_index,
                issue_text=issue_text,
                top_k=args.top_k,
            )
            print(json.dumps([context.to_dict() for context in contexts], indent=2))
        return 0

    if args.command == "eval-retrieval":
        results, summaries = run_retrieval_evaluation(
            dataset_dir=Path(args.dataset),
            providers=args.context_provider or ["native"],
            output_dir=Path(args.output),
            top_k=args.top_k,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "result_count": len(results),
                        "report_path": str(Path(args.output) / "report.md"),
                        "summaries": [summary.to_dict() for summary in summaries],
                    },
                    indent=2,
                )
            )
        else:
            print(f"Report: {Path(args.output) / 'report.md'}")
            for summary in summaries:
                print(
                    f"{summary.provider}: top5={summary.avg_top5_touched_recall:.2f} "
                    f"related_tests={summary.avg_related_test_recall:.2f} "
                    f"completed={summary.completed_tasks}/{summary.attempted_tasks}"
                )
        return 0

    if args.command == "validate-dataset":
        results, summary = validate_seeded_dataset(
            dataset_dir=Path(args.dataset),
            output_dir=Path(args.output),
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "result_count": len(results),
                        "report_path": str(Path(args.output) / "validation_report.md"),
                        "summary": summary.to_dict(),
                    },
                    indent=2,
                )
            )
        else:
            print(f"Report: {Path(args.output) / 'validation_report.md'}")
            print(
                f"valid={summary.valid_tasks}/{summary.task_count} "
                f"errors={summary.error_count} warnings={summary.warning_count}"
            )
        return 0

    if args.command == "eval-repair":
        results, summary = run_repair_evaluation(
            dataset_dir=Path(args.dataset),
            runtime=args.runtime,
            planner=args.planner,
            max_retries=args.max_retries,
            context_provider=args.context_provider,
            output_dir=Path(args.output),
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "result_count": len(results),
                        "report_path": str(Path(args.output) / "repair_report.md"),
                        "summary": summary.to_dict(),
                    },
                    indent=2,
                )
            )
        else:
            print(f"Report: {Path(args.output) / 'repair_report.md'}")
            print(
                f"{summary.runtime}/{summary.planner}/{summary.context_provider}: "
                f"patch_generated={summary.patch_generated_rate:.2f} "
                f"tests_passed={summary.targeted_test_pass_rate:.2f} "
                f"completed={summary.completed_tasks}/{summary.attempted_tasks}"
            )
        return 0

    if args.command == "eval-scaffold":
        results = run_scaffold_comparison(
            dataset_dir=Path(args.dataset),
            variants=args.variant
            or ["agentless", "heuristic", "langgraph", "langgraph_fake_model", "deepagents"],
            context_provider=args.context_provider,
            output_dir=Path(args.output),
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "result_count": len(results),
                        "report_path": str(Path(args.output) / "scaffold_report.md"),
                        "results": [result.to_dict() for result in results],
                    },
                    indent=2,
                )
            )
        else:
            print(f"Report: {Path(args.output) / 'scaffold_report.md'}")
            for result in results:
                print(
                    f"{result.scaffold}: patch_generated={result.patch_generated_rate:.2f} "
                    f"tests_passed={result.targeted_test_pass_rate:.2f} "
                    f"completed={result.completed_tasks}/{result.attempted_tasks}"
            )
        return 0

    if args.command == "eval-patch-search":
        results, summaries = run_patch_search_evaluation(
            dataset_dir=Path(args.dataset),
            candidate_counts=args.candidate_count or [1, 3],
            context_provider=args.context_provider,
            output_dir=Path(args.output),
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "result_count": len(results),
                        "report_path": str(Path(args.output) / "patch_search_report.md"),
                        "summaries": [summary.to_dict() for summary in summaries],
                    },
                    indent=2,
                )
            )
        else:
            print(f"Report: {Path(args.output) / 'patch_search_report.md'}")
            for summary in summaries:
                print(
                    f"{summary.variant}: success@1={summary.success_at_1_rate:.2f} "
                    f"success@k={summary.success_at_k_rate:.2f} "
                    f"tests={summary.avg_test_runs:.1f}"
                )
        return 0

    if args.command == "index-artifacts":
        json_output_path = Path(args.json_output) if args.json_output else None
        html_output_path = Path(args.html_output) if args.html_output else None
        run_detail_output_dir = (
            Path(args.run_detail_output_dir)
            if args.run_detail_output_dir
            else None
        )
        index = write_artifact_index(
            artifacts_dir=Path(args.artifacts_dir),
            output_path=Path(args.output),
            json_output_path=json_output_path,
            html_output_path=html_output_path,
            run_detail_output_dir=run_detail_output_dir,
        )
        if args.json:
            payload = {
                "artifacts_dir": index.artifacts_dir,
                "generated_at": index.generated_at,
                "experiment_count": index.experiment_count,
                "run_count": index.run_count,
                "metric_count": len(index.metrics),
                "index_path": str(Path(args.output)),
                "json_path": str(json_output_path) if json_output_path else None,
                "html_path": str(html_output_path) if html_output_path else None,
                "run_detail_dir": (
                    str(run_detail_output_dir)
                    if run_detail_output_dir
                    else None
                ),
            }
            print(json.dumps(payload, indent=2))
        else:
            print(f"Index: {Path(args.output)}")
            if json_output_path:
                print(f"JSON: {json_output_path}")
            if html_output_path:
                print(f"HTML: {html_output_path}")
            if run_detail_output_dir:
                print(f"Run details: {run_detail_output_dir}")
            print(
                f"Experiments: {index.experiment_count} "
                f"Runs: {index.run_count} "
                f"Metrics: {len(index.metrics)}"
            )
        return 0

    if args.command == "inspect-failures":
        json_output_path = Path(args.json_output) if args.json_output else None
        max_runs = None if args.max_runs == 0 else args.max_runs
        report = write_failure_report(
            artifacts_dir=Path(args.artifacts_dir),
            output_path=Path(args.output),
            json_output_path=json_output_path,
            max_runs=max_runs,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "artifacts_dir": report.artifacts_dir,
                        "generated_at": report.generated_at,
                        "runs_scanned": report.runs_scanned,
                        "runs_requiring_attention": report.runs_requiring_attention,
                        "failed_event_count": report.failed_event_count,
                        "category_counts": report.category_counts,
                        "report_path": str(Path(args.output)),
                        "json_path": str(json_output_path) if json_output_path else None,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Failure report: {Path(args.output)}")
            if json_output_path:
                print(f"JSON: {json_output_path}")
            print(
                f"Runs scanned: {report.runs_scanned} "
                f"Runs requiring attention: {report.runs_requiring_attention} "
                f"Failed events: {report.failed_event_count}"
            )
        return 0

    if args.command == "demo-readiness":
        json_output_path = Path(args.json_output) if args.json_output else None
        max_failure_runs = None if args.max_failure_runs == 0 else args.max_failure_runs
        report = write_demo_readiness_report(
            artifacts_dir=Path(args.artifacts_dir),
            output_path=Path(args.output),
            json_output_path=json_output_path,
            max_failure_runs=max_failure_runs,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "artifacts_dir": report.artifacts_dir,
                        "generated_at": report.generated_at,
                        "readiness_status": report.readiness_status,
                        "experiment_count": report.experiment_count,
                        "run_count": report.run_count,
                        "metric_count": report.metric_count,
                        "runs_requiring_attention": report.runs_requiring_attention,
                        "failure_categories": report.failure_categories,
                        "model_providers": report.model_providers,
                        "report_path": str(Path(args.output)),
                        "json_path": str(json_output_path) if json_output_path else None,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Demo readiness report: {Path(args.output)}")
            if json_output_path:
                print(f"JSON: {json_output_path}")
            print(
                f"Status: {report.readiness_status} "
                f"Experiments: {report.experiment_count} "
                f"Runs: {report.run_count} "
                f"Metrics: {report.metric_count}"
            )
        return 0

    if args.command == "demo-script":
        json_output_path = Path(args.json_output) if args.json_output else None
        max_failure_runs = None if args.max_failure_runs == 0 else args.max_failure_runs
        report = write_demo_script_report(
            artifacts_dir=Path(args.artifacts_dir),
            output_path=Path(args.output),
            json_output_path=json_output_path,
            max_failure_runs=max_failure_runs,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "artifacts_dir": report.artifacts_dir,
                        "generated_at": report.generated_at,
                        "target_duration_seconds": report.target_duration_seconds,
                        "readiness_status": report.readiness_status,
                        "section_count": len(report.sections),
                        "report_path": str(Path(args.output)),
                        "json_path": str(json_output_path) if json_output_path else None,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Demo script: {Path(args.output)}")
            if json_output_path:
                print(f"JSON: {json_output_path}")
            print(
                f"Status: {report.readiness_status} "
                f"Sections: {len(report.sections)} "
                f"Target: {report.target_duration_seconds}s"
            )
        return 0

    if args.command == "demo-media":
        json_output_path = Path(args.json_output) if args.json_output else None
        max_failure_runs = None if args.max_failure_runs == 0 else args.max_failure_runs
        report = write_demo_media_assets(
            artifacts_dir=Path(args.artifacts_dir),
            output_path=Path(args.output),
            svg_output_path=Path(args.svg_output),
            png_output_path=Path(args.png_output),
            json_output_path=json_output_path,
            max_failure_runs=max_failure_runs,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "artifacts_dir": report.artifacts_dir,
                        "generated_at": report.generated_at,
                        "readiness_status": report.readiness_status,
                        "markdown_path": report.markdown_path,
                        "svg_path": report.svg_path,
                        "png_path": report.png_path,
                        "width": report.width,
                        "height": report.height,
                        "json_path": str(json_output_path) if json_output_path else None,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Demo media report: {Path(args.output)}")
            print(f"SVG: {Path(args.svg_output)}")
            print(f"PNG: {Path(args.png_output)}")
            if json_output_path:
                print(f"JSON: {json_output_path}")
        return 0

    if args.command == "final-evaluation":
        json_output_path = Path(args.json_output) if args.json_output else None
        max_failure_runs = None if args.max_failure_runs == 0 else args.max_failure_runs
        report = write_final_evaluation_report(
            artifacts_dir=Path(args.artifacts_dir),
            output_path=Path(args.output),
            json_output_path=json_output_path,
            max_failure_runs=max_failure_runs,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "artifacts_dir": report.artifacts_dir,
                        "generated_at": report.generated_at,
                        "readiness_status": report.readiness_status,
                        "experiment_count": report.experiment_count,
                        "run_count": report.run_count,
                        "metric_count": report.metric_count,
                        "runs_requiring_attention": report.runs_requiring_attention,
                        "decision_count": len(report.decisions),
                        "limitation_count": len(report.limitations),
                        "report_path": str(Path(args.output)),
                        "json_path": str(json_output_path) if json_output_path else None,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Final evaluation report: {Path(args.output)}")
            if json_output_path:
                print(f"JSON: {json_output_path}")
            print(
                f"Status: {report.readiness_status} "
                f"Experiments: {report.experiment_count} "
                f"Metrics: {report.metric_count}"
            )
        return 0

    if args.command == "release-hygiene":
        json_output_path = Path(args.json_output) if args.json_output else None
        max_failure_runs = None if args.max_failure_runs == 0 else args.max_failure_runs
        report = write_release_hygiene_report(
            project_root=Path(args.project_root),
            artifacts_dir=Path(args.artifacts_dir),
            output_path=Path(args.output),
            json_output_path=json_output_path,
            max_failure_runs=max_failure_runs,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "project_root": report.project_root,
                        "artifacts_dir": report.artifacts_dir,
                        "generated_at": report.generated_at,
                        "release_status": report.release_status,
                        "passed_count": report.passed_count,
                        "warning_count": report.warning_count,
                        "blocked_count": report.blocked_count,
                        "report_path": str(Path(args.output)),
                        "json_path": str(json_output_path) if json_output_path else None,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Release hygiene report: {Path(args.output)}")
            if json_output_path:
                print(f"JSON: {json_output_path}")
            print(
                f"Status: {report.release_status} "
                f"Passed: {report.passed_count} "
                f"Warnings: {report.warning_count} "
                f"Blocked: {report.blocked_count}"
            )
        return 0

    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="patchsmith")
    subparsers = parser.add_subparsers(dest="command")

    run = subparsers.add_parser("run", help="Run the MVP issue-to-report lifecycle.")
    _add_repo_args(run)
    _add_issue_args(run)
    run.add_argument("--test-command", help="Allowed test command to run in the sandbox.")
    run.add_argument(
        "--runtime",
        choices=["agentless", "heuristic", "langgraph", "deepagents"],
        default="agentless",
        help="Runtime label for the run report.",
    )
    run.add_argument(
        "--planner",
        choices=["heuristic", "fake_model", "openai"],
        default="heuristic",
        help="Repair planner used by model-capable runtimes.",
    )
    run.add_argument(
        "--max-retries",
        type=int,
        default=0,
        help="Maximum extra LangGraph planning/edit retries after the first attempt.",
    )
    run.add_argument(
        "--context-provider",
        choices=["native", "native_hybrid", "native_graph", "ctxhelm_cli", "auto"],
        default="native",
        help="Context broker to use before agent execution.",
    )
    run.add_argument("--top-k", type=int, default=5, help="Number of files to retrieve.")
    run.add_argument("--artifacts-dir", default="artifacts", help="Artifact output directory.")
    run.add_argument("--json", action="store_true", help="Print machine-readable run summary.")

    index = subparsers.add_parser("index", help="Clone/copy a repository and print file index JSON.")
    _add_repo_args(index)

    retrieve = subparsers.add_parser("retrieve", help="Run keyword retrieval and print JSON.")
    _add_repo_args(retrieve)
    _add_issue_args(retrieve)
    retrieve.add_argument(
        "--retrieval",
        choices=["keyword", "native_hybrid", "native_graph"],
        default="keyword",
        help="Retrieval strategy for this direct retrieval command.",
    )
    retrieve.add_argument("--top-k", type=int, default=5, help="Number of files to retrieve.")

    eval_retrieval = subparsers.add_parser(
        "eval-retrieval", help="Compare context providers on seeded retrieval tasks."
    )
    eval_retrieval.add_argument(
        "--dataset",
        default="evals/tasks/seeded_bugs_v1",
        help="Seeded task dataset directory.",
    )
    eval_retrieval.add_argument(
        "--context-provider",
        action="append",
        choices=["native", "native_hybrid", "native_graph", "ctxhelm_cli"],
        default=[],
        help="Provider lane to evaluate. Repeat for multiple lanes.",
    )
    eval_retrieval.add_argument(
        "--output",
        default="artifacts/experiments/retrieval_eval_v1",
        help="Experiment output directory.",
    )
    eval_retrieval.add_argument("--top-k", type=int, default=5, help="Recall cutoff.")
    eval_retrieval.add_argument("--json", action="store_true", help="Print JSON summary.")

    validate_dataset = subparsers.add_parser(
        "validate-dataset", help="Validate seeded task metadata and expected paths."
    )
    validate_dataset.add_argument(
        "--dataset",
        default="evals/tasks/seeded_bugs_v1",
        help="Seeded task dataset directory.",
    )
    validate_dataset.add_argument(
        "--output",
        default="artifacts/experiments/seeded_dataset_validation_v1",
        help="Dataset validation output directory.",
    )
    validate_dataset.add_argument("--json", action="store_true", help="Print JSON summary.")

    eval_repair = subparsers.add_parser(
        "eval-repair", help="Run seeded repair tasks and write aggregate reports."
    )
    eval_repair.add_argument(
        "--dataset",
        default="evals/tasks/seeded_bugs_v1",
        help="Seeded task dataset directory.",
    )
    eval_repair.add_argument(
        "--runtime",
        choices=["agentless", "heuristic", "langgraph", "deepagents"],
        default="heuristic",
        help="Runtime to evaluate.",
    )
    eval_repair.add_argument(
        "--planner",
        choices=["heuristic", "fake_model", "openai"],
        default="heuristic",
        help="Repair planner to evaluate. `openai` requires OPENAI_API_KEY.",
    )
    eval_repair.add_argument(
        "--max-retries",
        type=int,
        default=0,
        help="Maximum extra LangGraph planning/edit retries after the first attempt.",
    )
    eval_repair.add_argument(
        "--context-provider",
        choices=["native", "native_hybrid", "native_graph", "ctxhelm_cli", "auto"],
        default="native_hybrid",
        help="Context provider for repair runs.",
    )
    eval_repair.add_argument(
        "--output",
        default="artifacts/experiments/repair_eval_v1",
        help="Experiment output directory.",
    )
    eval_repair.add_argument("--json", action="store_true", help="Print JSON summary.")

    eval_scaffold = subparsers.add_parser(
        "eval-scaffold", help="Compare repair scaffolds on the same seeded dataset."
    )
    eval_scaffold.add_argument(
        "--dataset",
        default="evals/tasks/seeded_bugs_v1",
        help="Seeded task dataset directory.",
    )
    eval_scaffold.add_argument(
        "--variant",
        action="append",
        choices=["agentless", "heuristic", "langgraph", "langgraph_fake_model", "deepagents"],
        default=[],
        help="Scaffold variant to evaluate. Repeat for multiple variants.",
    )
    eval_scaffold.add_argument(
        "--context-provider",
        choices=["native", "native_hybrid", "native_graph", "ctxhelm_cli", "auto"],
        default="native_hybrid",
        help="Context provider shared by all compared scaffolds.",
    )
    eval_scaffold.add_argument(
        "--output",
        default="artifacts/experiments/scaffold_comparison_v1",
        help="Scaffold comparison output directory.",
    )
    eval_scaffold.add_argument("--json", action="store_true", help="Print JSON summary.")

    eval_patch_search = subparsers.add_parser(
        "eval-patch-search", help="Evaluate deterministic multi-candidate patch search."
    )
    eval_patch_search.add_argument(
        "--dataset",
        default="evals/tasks/seeded_bugs_v1",
        help="Seeded task dataset directory.",
    )
    eval_patch_search.add_argument(
        "--candidate-count",
        type=int,
        action="append",
        default=[],
        help="Candidate count variant to evaluate. Repeat for multiple variants.",
    )
    eval_patch_search.add_argument(
        "--context-provider",
        choices=["native", "native_hybrid", "native_graph"],
        default="native_hybrid",
        help="Context provider used to localize source files before candidate generation.",
    )
    eval_patch_search.add_argument(
        "--output",
        default="artifacts/experiments/patch_search_eval_v1",
        help="Patch-search experiment output directory.",
    )
    eval_patch_search.add_argument("--json", action="store_true", help="Print JSON summary.")

    index_artifacts = subparsers.add_parser(
        "index-artifacts", help="Generate a static index of saved run and experiment artifacts."
    )
    index_artifacts.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    index_artifacts.add_argument(
        "--output",
        default="artifacts/experiments/index.md",
        help="Markdown artifact-index output path.",
    )
    index_artifacts.add_argument(
        "--json-output",
        help="Optional JSON artifact-index output path.",
    )
    index_artifacts.add_argument(
        "--html-output",
        help="Optional static HTML artifact-dashboard output path.",
    )
    index_artifacts.add_argument(
        "--run-detail-output-dir",
        help="Optional directory for static run-detail HTML pages.",
    )
    index_artifacts.add_argument("--json", action="store_true", help="Print JSON summary.")

    inspect_failures = subparsers.add_parser(
        "inspect-failures",
        help="Summarize failure signals from saved run trace artifacts.",
    )
    inspect_failures.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    inspect_failures.add_argument(
        "--output",
        default="artifacts/experiments/failure_report.md",
        help="Markdown failure report output path.",
    )
    inspect_failures.add_argument(
        "--json-output",
        help="Optional JSON failure report output path.",
    )
    inspect_failures.add_argument(
        "--max-runs",
        type=int,
        default=100,
        help="Maximum recent runs to scan. Use 0 to scan all runs.",
    )
    inspect_failures.add_argument("--json", action="store_true", help="Print JSON summary.")

    demo_readiness = subparsers.add_parser(
        "demo-readiness",
        help="Generate a portfolio demo readiness report from saved artifacts.",
    )
    demo_readiness.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    demo_readiness.add_argument(
        "--output",
        default="artifacts/experiments/demo_readiness.md",
        help="Markdown demo readiness report output path.",
    )
    demo_readiness.add_argument(
        "--json-output",
        help="Optional JSON demo readiness report output path.",
    )
    demo_readiness.add_argument(
        "--max-failure-runs",
        type=int,
        default=0,
        help="Maximum recent runs to scan for failure visibility. Use 0 to scan all runs.",
    )
    demo_readiness.add_argument("--json", action="store_true", help="Print JSON summary.")

    demo_script = subparsers.add_parser(
        "demo-script",
        help="Generate a timed portfolio demo script from saved artifacts.",
    )
    demo_script.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    demo_script.add_argument(
        "--output",
        default="artifacts/experiments/demo_script.md",
        help="Markdown demo script output path.",
    )
    demo_script.add_argument(
        "--json-output",
        help="Optional JSON demo script output path.",
    )
    demo_script.add_argument(
        "--max-failure-runs",
        type=int,
        default=0,
        help="Maximum recent runs to scan for failure visibility. Use 0 to scan all runs.",
    )
    demo_script.add_argument("--json", action="store_true", help="Print JSON summary.")

    demo_media = subparsers.add_parser(
        "demo-media",
        help="Generate demo media assets from saved artifact evidence.",
    )
    demo_media.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    demo_media.add_argument(
        "--output",
        default="artifacts/experiments/demo_media.md",
        help="Markdown demo media report output path.",
    )
    demo_media.add_argument(
        "--svg-output",
        default="artifacts/experiments/demo_media.svg",
        help="SVG demo media asset output path.",
    )
    demo_media.add_argument(
        "--png-output",
        default="artifacts/experiments/demo_media.png",
        help="PNG demo media asset output path.",
    )
    demo_media.add_argument(
        "--json-output",
        help="Optional JSON demo media report output path.",
    )
    demo_media.add_argument(
        "--max-failure-runs",
        type=int,
        default=0,
        help="Maximum recent runs to scan for failure visibility. Use 0 to scan all runs.",
    )
    demo_media.add_argument("--json", action="store_true", help="Print JSON summary.")

    final_evaluation = subparsers.add_parser(
        "final-evaluation",
        help="Generate a final evaluation narrative from saved artifacts.",
    )
    final_evaluation.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    final_evaluation.add_argument(
        "--output",
        default="artifacts/experiments/final_evaluation.md",
        help="Markdown final evaluation report output path.",
    )
    final_evaluation.add_argument(
        "--json-output",
        help="Optional JSON final evaluation report output path.",
    )
    final_evaluation.add_argument(
        "--max-failure-runs",
        type=int,
        default=0,
        help="Maximum recent runs to scan for failure visibility. Use 0 to scan all runs.",
    )
    final_evaluation.add_argument("--json", action="store_true", help="Print JSON summary.")

    release_hygiene = subparsers.add_parser(
        "release-hygiene",
        help="Generate a release hygiene checklist from saved artifacts and project files.",
    )
    release_hygiene.add_argument(
        "--project-root",
        default=".",
        help="Project root to inspect for docs, Git metadata, CI, and public assets.",
    )
    release_hygiene.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    release_hygiene.add_argument(
        "--output",
        default="artifacts/experiments/release_hygiene.md",
        help="Markdown release hygiene report output path.",
    )
    release_hygiene.add_argument(
        "--json-output",
        help="Optional JSON release hygiene report output path.",
    )
    release_hygiene.add_argument(
        "--max-failure-runs",
        type=int,
        default=0,
        help="Maximum recent runs to scan for failure visibility. Use 0 to scan all runs.",
    )
    release_hygiene.add_argument("--json", action="store_true", help="Print JSON summary.")

    return parser


def _add_repo_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", required=True, help="Local path or public Git repository URL.")
    parser.add_argument("--commit", help="Optional commit hash to check out.")
    parser.add_argument("--branch", help="Optional branch to check out.")


def _add_issue_args(parser: argparse.ArgumentParser) -> None:
    issue_group = parser.add_mutually_exclusive_group(required=True)
    issue_group.add_argument("--issue", help="Raw issue text.")
    issue_group.add_argument("--issue-file", help="Path to a file containing issue text.")
    parser.add_argument("--issue-url", help="Optional source issue URL for the run report.")


def _load_issue_text(args: argparse.Namespace) -> str:
    if args.issue_file:
        return Path(args.issue_file).read_text(encoding="utf-8")
    return args.issue


def _retriever_for(name: str) -> object:
    if name == "native_hybrid":
        return HybridRetriever()
    if name == "native_graph":
        return GraphRetriever()
    return KeywordRetriever()


if __name__ == "__main__":
    raise SystemExit(main())
