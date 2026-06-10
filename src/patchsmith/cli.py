from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from patchsmith.evaluation import (
    check_materialized_issue_run_readiness,
    check_focused_test_setup_readiness,
    diagnose_focused_test_runs,
    execute_focused_test_setups,
    materialize_issue_corpus_tasks,
    plan_focused_test_setups,
    plan_materialized_issue_focused_tests,
    preflight_issue_corpus_repositories,
    preview_issue_corpus_context,
    run_materialized_issue_focused_tests,
    run_patch_search_evaluation,
    run_repair_evaluation,
    run_scaffold_comparison,
    run_retrieval_evaluation,
    validate_focused_test_setups,
    validate_issue_corpus,
    validate_materialized_issue_tasks,
    validate_seeded_dataset,
)
from patchsmith.ingest import clone_or_copy_repository, index_repository
from patchsmith.models import RunRequest
from patchsmith.observability import write_artifact_index, write_failure_report
from patchsmith.portfolio import (
    write_demo_readiness_report,
    write_demo_media_assets,
    write_demo_script_report,
    write_delivery_audit_report,
    write_docker_smoke_report,
    write_evidence_refresh_report,
    write_final_evaluation_report,
    write_launch_blocker_report,
    write_live_calibration_plan_report,
    write_live_calibration_report,
    write_mvp_progress_report,
    write_project_status_report,
    write_quality_gate_report,
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
            sandbox_mode=args.sandbox_mode,
            sandbox_image=args.sandbox_image,
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

    if args.command == "validate-issue-corpus":
        results, summary = validate_issue_corpus(
            corpus_path=Path(args.corpus),
            output_dir=Path(args.output),
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "result_count": len(results),
                        "report_path": str(Path(args.output) / "corpus_report.md"),
                        "summary": summary.to_dict(),
                    },
                    indent=2,
                )
            )
        else:
            print(f"Report: {Path(args.output) / 'corpus_report.md'}")
            print(
                f"valid={summary.valid_entries}/{summary.entry_count} "
                f"errors={summary.error_count} warnings={summary.warning_count}"
            )
        return 0

    if args.command == "preflight-issue-corpus":
        results, summary = preflight_issue_corpus_repositories(
            corpus_path=Path(args.corpus),
            output_dir=Path(args.output),
            timeout_seconds=args.timeout_seconds,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "result_count": len(results),
                        "report_path": str(Path(args.output) / "repo_preflight_report.md"),
                        "summary": summary.to_dict(),
                    },
                    indent=2,
                )
            )
        else:
            print(f"Report: {Path(args.output) / 'repo_preflight_report.md'}")
            print(
                f"reachable={summary.reachable_repositories}/{summary.repository_count} "
                f"issues={summary.issue_count}"
            )
        return 0

    if args.command == "preview-issue-corpus-context":
        max_issues = None if args.max_issues == 0 else args.max_issues
        results, summary = preview_issue_corpus_context(
            corpus_path=Path(args.corpus),
            output_dir=Path(args.output),
            context_provider=args.context_provider,
            top_k=args.top_k,
            max_issues=max_issues,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "result_count": len(results),
                        "report_path": str(Path(args.output) / "context_preview_report.md"),
                        "summary": summary.to_dict(),
                    },
                    indent=2,
                )
            )
        else:
            print(f"Report: {Path(args.output) / 'context_preview_report.md'}")
            print(
                f"completed={summary.completed_issues}/{summary.attempted_issues} "
                f"context_provider={summary.context_provider}"
            )
        return 0

    if args.command == "materialize-issue-corpus-tasks":
        max_issues = None if args.max_issues == 0 else args.max_issues
        context_preview = (
            Path(args.context_preview)
            if args.context_preview
            else Path(args.output) / "context_preview_results.json"
        )
        results, summary = materialize_issue_corpus_tasks(
            corpus_path=Path(args.corpus),
            output_dir=Path(args.output),
            context_preview_path=context_preview,
            max_issues=max_issues,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "result_count": len(results),
                        "report_path": str(Path(args.output) / "materialized_task_report.md"),
                        "summary": summary.to_dict(),
                    },
                    indent=2,
                )
            )
        else:
            print(f"Report: {Path(args.output) / 'materialized_task_report.md'}")
            print(
                f"materialized={summary.materialized_tasks}/{summary.attempted_issues} "
                f"source_free={str(summary.source_free).lower()}"
            )
        return 0

    if args.command == "validate-materialized-issue-tasks":
        results, summary = validate_materialized_issue_tasks(
            tasks_dir=Path(args.tasks_dir),
            output_dir=Path(args.output),
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "result_count": len(results),
                        "report_path": str(
                            Path(args.output) / "materialized_task_validation_report.md"
                        ),
                        "summary": summary.to_dict(),
                    },
                    indent=2,
                )
            )
        else:
            print(
                f"Report: {Path(args.output) / 'materialized_task_validation_report.md'}"
            )
            print(
                f"valid={summary.valid_tasks}/{summary.task_count} "
                f"errors={summary.error_count} warnings={summary.warning_count}"
            )
        return 0

    if args.command == "check-materialized-run-readiness":
        results, summary = check_materialized_issue_run_readiness(
            tasks_dir=Path(args.tasks_dir),
            output_dir=Path(args.output),
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "result_count": len(results),
                        "report_path": str(
                            Path(args.output) / "materialized_run_readiness_report.md"
                        ),
                        "summary": summary.to_dict(),
                    },
                    indent=2,
                )
            )
        else:
            print(
                f"Report: {Path(args.output) / 'materialized_run_readiness_report.md'}"
            )
            print(
                f"ready={summary.ready_tasks} warning={summary.warning_tasks} "
                f"blocked={summary.blocked_tasks}"
            )
        return 0

    if args.command == "plan-materialized-focused-tests":
        results, summary = plan_materialized_issue_focused_tests(
            tasks_dir=Path(args.tasks_dir),
            output_dir=Path(args.output),
            max_paths=args.max_paths,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "result_count": len(results),
                        "report_path": str(Path(args.output) / "focused_test_plan_report.md"),
                        "summary": summary.to_dict(),
                    },
                    indent=2,
                )
            )
        else:
            print(f"Report: {Path(args.output) / 'focused_test_plan_report.md'}")
            print(
                f"planned={summary.planned_tasks} fallback={summary.fallback_tasks} "
                f"blocked={summary.blocked_tasks}"
            )
        return 0

    if args.command == "run-materialized-focused-tests":
        results, summary = run_materialized_issue_focused_tests(
            plan_path=Path(args.plan),
            output_dir=Path(args.output),
            sandbox_mode=args.sandbox_mode,
            sandbox_image=args.sandbox_image,
            timeout_seconds=args.timeout_seconds,
            max_tasks=args.max_tasks,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "result_count": len(results),
                        "report_path": str(Path(args.output) / "focused_test_run_report.md"),
                        "summary": summary.to_dict(),
                    },
                    indent=2,
                )
            )
        else:
            print(f"Report: {Path(args.output) / 'focused_test_run_report.md'}")
            print(
                f"passed={summary.passed_tasks} failed={summary.failed_tasks} "
                f"timed_out={summary.timed_out_tasks} blocked={summary.blocked_tasks}"
            )
        return 0

    if args.command == "diagnose-focused-test-runs":
        results, summary = diagnose_focused_test_runs(
            results_path=Path(args.results),
            output_dir=Path(args.output),
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "result_count": len(results),
                        "report_path": str(
                            Path(args.output) / "focused_test_diagnosis_report.md"
                        ),
                        "summary": summary.to_dict(),
                    },
                    indent=2,
                )
            )
        else:
            print(f"Report: {Path(args.output) / 'focused_test_diagnosis_report.md'}")
            print(
                f"environment={summary.environment_issue_tasks} "
                f"dependency={summary.dependency_issue_tasks} "
                f"unknown={summary.unknown_failure_tasks}"
            )
        return 0

    if args.command == "plan-focused-test-setups":
        results, summary = plan_focused_test_setups(
            diagnosis_path=Path(args.diagnosis),
            output_dir=Path(args.output),
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "result_count": len(results),
                        "report_path": str(
                            Path(args.output) / "focused_test_setup_plan_report.md"
                        ),
                        "summary": summary.to_dict(),
                    },
                    indent=2,
                )
            )
        else:
            print(f"Report: {Path(args.output) / 'focused_test_setup_plan_report.md'}")
            print(
                f"planned={summary.planned_tasks} ready={summary.ready_tasks} "
                f"manual_review={summary.manual_review_tasks}"
            )
        return 0

    if args.command == "check-focused-test-setup-readiness":
        results, summary = check_focused_test_setup_readiness(
            setup_plan_path=Path(args.setup_plan),
            docker_smoke_path=Path(args.docker_smoke),
            output_dir=Path(args.output),
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "result_count": len(results),
                        "report_path": str(
                            Path(args.output) / "focused_test_setup_readiness_report.md"
                        ),
                        "summary": summary.to_dict(),
                    },
                    indent=2,
                )
            )
        else:
            print(f"Report: {Path(args.output) / 'focused_test_setup_readiness_report.md'}")
            print(
                f"ready={summary.ready_tasks} warning={summary.warning_tasks} "
                f"blocked={summary.blocked_tasks}"
            )
        return 0

    if args.command == "execute-focused-test-setups":
        max_tasks = None if args.max_tasks == 0 else args.max_tasks
        results, summary = execute_focused_test_setups(
            readiness_path=Path(args.readiness),
            output_dir=Path(args.output),
            sandbox_mode=args.sandbox_mode,
            sandbox_image=args.sandbox_image,
            sandbox_network=args.sandbox_network,
            timeout_seconds=args.timeout_seconds,
            max_tasks=max_tasks,
            dry_run=not args.execute,
            allow_warnings=args.allow_warnings,
            allow_dependency_installs=args.allow_dependency_installs,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "result_count": len(results),
                        "report_path": str(
                            Path(args.output) / "focused_test_setup_execution_report.md"
                        ),
                        "summary": summary.to_dict(),
                    },
                    indent=2,
                )
            )
        else:
            print(f"Report: {Path(args.output) / 'focused_test_setup_execution_report.md'}")
            print(
                f"dry_run={summary.dry_run_tasks} attempted={summary.attempted_tasks} "
                f"passed={summary.completed_tasks} blocked={summary.blocked_tasks}"
            )
        return 0

    if args.command == "validate-focused-test-setups":
        max_tasks = None if args.max_tasks == 0 else args.max_tasks
        results, summary = validate_focused_test_setups(
            setup_execution_path=Path(args.setup_execution),
            output_dir=Path(args.output),
            sandbox_mode=args.sandbox_mode,
            sandbox_image=args.sandbox_image,
            sandbox_network=args.sandbox_network,
            timeout_seconds=args.timeout_seconds,
            max_tasks=max_tasks,
            dry_run=not args.execute,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "result_count": len(results),
                        "report_path": str(
                            Path(args.output) / "focused_test_setup_validation_report.md"
                        ),
                        "summary": summary.to_dict(),
                    },
                    indent=2,
                )
            )
        else:
            print(f"Report: {Path(args.output) / 'focused_test_setup_validation_report.md'}")
            print(
                f"dry_run={summary.dry_run_tasks} attempted={summary.attempted_tasks} "
                f"passed={summary.passed_tasks} blocked={summary.blocked_tasks}"
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
            sandbox_mode=args.sandbox_mode,
            sandbox_image=args.sandbox_image,
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
            or [
                "agentless",
                "heuristic",
                "langgraph",
                "langgraph_fake_model",
                "deepagents",
                "openai_agents",
            ],
            context_provider=args.context_provider,
            output_dir=Path(args.output),
            sandbox_mode=args.sandbox_mode,
            sandbox_image=args.sandbox_image,
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
            sandbox_mode=args.sandbox_mode,
            sandbox_image=args.sandbox_image,
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
                        "deepagents_package_run_count": report.deepagents_package_run_count,
                        "deepagents_compatibility_run_count": (
                            report.deepagents_compatibility_run_count
                        ),
                        "openai_agents_package_run_count": (
                            report.openai_agents_package_run_count
                        ),
                        "openai_agents_compatibility_run_count": (
                            report.openai_agents_compatibility_run_count
                        ),
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

    if args.command == "live-calibration":
        json_output_path = Path(args.json_output) if args.json_output else None
        report = write_live_calibration_report(
            artifacts_dir=Path(args.artifacts_dir),
            output_path=Path(args.output),
            json_output_path=json_output_path,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "artifacts_dir": report.artifacts_dir,
                        "generated_at": report.generated_at,
                        "calibration_status": report.calibration_status,
                        "saved_live_provider_count": report.saved_live_provider_count,
                        "deepagents_package_run_count": report.deepagents_package_run_count,
                        "deepagents_compatibility_run_count": (
                            report.deepagents_compatibility_run_count
                        ),
                        "openai_agents_package_run_count": (
                            report.openai_agents_package_run_count
                        ),
                        "openai_agents_compatibility_run_count": (
                            report.openai_agents_compatibility_run_count
                        ),
                        "model_providers": report.model_providers,
                        "report_path": str(Path(args.output)),
                        "json_path": str(json_output_path) if json_output_path else None,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Live calibration report: {Path(args.output)}")
            if json_output_path:
                print(f"JSON: {json_output_path}")
            print(
                f"Status: {report.calibration_status} "
                f"Saved live-provider runs: {report.saved_live_provider_count} "
                f"DeepAgents package runs: {report.deepagents_package_run_count} "
                f"OpenAI Agents package runs: {report.openai_agents_package_run_count}"
            )
        return 0

    if args.command == "live-calibration-plan":
        json_output_path = Path(args.json_output) if args.json_output else None
        report = write_live_calibration_plan_report(
            artifacts_dir=Path(args.artifacts_dir),
            output_path=Path(args.output),
            json_output_path=json_output_path,
        )
        ready_runs = sum(1 for run in report.runs if run.status == "ready")
        blocked_runs = sum(1 for run in report.runs if run.status == "blocked")
        if args.json:
            print(
                json.dumps(
                    {
                        "artifacts_dir": report.artifacts_dir,
                        "generated_at": report.generated_at,
                        "plan_status": report.plan_status,
                        "calibration_status": report.calibration_status,
                        "saved_live_provider_count": report.saved_live_provider_count,
                        "run_count": len(report.runs),
                        "ready_runs": ready_runs,
                        "blocked_runs": blocked_runs,
                        "report_path": str(Path(args.output)),
                        "json_path": str(json_output_path) if json_output_path else None,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Live calibration plan: {Path(args.output)}")
            if json_output_path:
                print(f"JSON: {json_output_path}")
            print(
                f"Status: {report.plan_status} "
                f"Runs: {len(report.runs)} "
                f"Ready: {ready_runs} "
                f"Blocked: {blocked_runs}"
            )
        return 0

    if args.command == "docker-smoke":
        json_output_path = Path(args.json_output) if args.json_output else None
        report = write_docker_smoke_report(
            project_root=Path(args.project_root),
            artifacts_dir=Path(args.artifacts_dir),
            output_path=Path(args.output),
            json_output_path=json_output_path,
            image=args.image,
            task_dir=Path(args.task_dir),
            test_command=args.test_command,
            runtime=args.runtime,
            context_provider=args.context_provider,
            docker_binary=args.docker_binary,
            run_seeded=not args.skip_run,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "project_root": report.project_root,
                        "artifacts_dir": report.artifacts_dir,
                        "generated_at": report.generated_at,
                        "smoke_status": report.smoke_status,
                        "image": report.image,
                        "task_dir": report.task_dir,
                        "run_id": report.run_id,
                        "test_exit_code": report.test_exit_code,
                        "environment": report.environment,
                        "remediation_commands": report.remediation_commands,
                        "report_path": str(Path(args.output)),
                        "json_path": str(json_output_path) if json_output_path else None,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Docker smoke report: {Path(args.output)}")
            if json_output_path:
                print(f"JSON: {json_output_path}")
            print(
                f"Status: {report.smoke_status} "
                f"Image: {report.image} "
                f"Run: {report.run_id or 'n/a'} "
                f"Test exit: {report.test_exit_code if report.test_exit_code is not None else 'n/a'}"
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

    if args.command == "launch-blockers":
        json_output_path = Path(args.json_output) if args.json_output else None
        report = write_launch_blocker_report(
            artifacts_dir=Path(args.artifacts_dir),
            output_path=Path(args.output),
            json_output_path=json_output_path,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "artifacts_dir": report.artifacts_dir,
                        "generated_at": report.generated_at,
                        "launch_status": report.launch_status,
                        "item_count": report.item_count,
                        "blocked_count": report.blocked_count,
                        "warning_count": report.warning_count,
                        "ready_count": report.ready_count,
                        "report_path": str(Path(args.output)),
                        "json_path": str(json_output_path) if json_output_path else None,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Launch blocker report: {Path(args.output)}")
            if json_output_path:
                print(f"JSON: {json_output_path}")
            print(
                f"Status: {report.launch_status} "
                f"Items: {report.item_count} "
                f"Blocked: {report.blocked_count} "
                f"Warnings: {report.warning_count}"
            )
        return 0

    if args.command == "mvp-progress":
        json_output_path = Path(args.json_output) if args.json_output else None
        max_failure_runs = None if args.max_failure_runs == 0 else args.max_failure_runs
        report = write_mvp_progress_report(
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
                        "status": report.status,
                        "completion_percent": report.completion_percent,
                        "item_count": report.item_count,
                        "passed_count": report.passed_count,
                        "warning_count": report.warning_count,
                        "blocked_count": report.blocked_count,
                        "missing_count": report.missing_count,
                        "report_path": str(Path(args.output)),
                        "json_path": str(json_output_path) if json_output_path else None,
                    },
                    indent=2,
                )
            )
        else:
            print(f"MVP progress report: {Path(args.output)}")
            if json_output_path:
                print(f"JSON: {json_output_path}")
            print(
                f"Status: {report.status} "
                f"Completion: {report.completion_percent:.1f}% "
                f"Passed: {report.passed_count} "
                f"Warnings: {report.warning_count} "
                f"Missing: {report.missing_count} "
                f"Blocked: {report.blocked_count}"
            )
        return 0

    if args.command == "delivery-audit":
        json_output_path = Path(args.json_output) if args.json_output else None
        report = write_delivery_audit_report(
            project_root=Path(args.project_root),
            artifacts_dir=Path(args.artifacts_dir),
            output_path=Path(args.output),
            json_output_path=json_output_path,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "project_root": report.project_root,
                        "artifacts_dir": report.artifacts_dir,
                        "generated_at": report.generated_at,
                        "delivery_status": report.delivery_status,
                        "completion_percent": report.completion_percent,
                        "item_count": report.item_count,
                        "passed_count": report.passed_count,
                        "warning_count": report.warning_count,
                        "blocked_count": report.blocked_count,
                        "missing_count": report.missing_count,
                        "report_path": str(Path(args.output)),
                        "json_path": str(json_output_path) if json_output_path else None,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Delivery audit report: {Path(args.output)}")
            if json_output_path:
                print(f"JSON: {json_output_path}")
            print(
                f"Status: {report.delivery_status} "
                f"Completion: {report.completion_percent:.1f}% "
                f"Passed: {report.passed_count} "
                f"Warnings: {report.warning_count} "
                f"Missing: {report.missing_count} "
                f"Blocked: {report.blocked_count}"
            )
        return 0

    if args.command == "quality-gate":
        json_output_path = Path(args.json_output) if args.json_output else None
        logs_dir = Path(args.logs_dir) if args.logs_dir else None
        report = write_quality_gate_report(
            project_root=Path(args.project_root),
            artifacts_dir=Path(args.artifacts_dir),
            output_path=Path(args.output),
            json_output_path=json_output_path,
            logs_dir=logs_dir,
            timeout_seconds=args.timeout_seconds,
            include_tests=not args.skip_tests,
            include_build=not args.skip_build,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "project_root": report.project_root,
                        "artifacts_dir": report.artifacts_dir,
                        "generated_at": report.generated_at,
                        "quality_status": report.quality_status,
                        "passed_count": report.passed_count,
                        "failed_count": report.failed_count,
                        "skipped_count": report.skipped_count,
                        "report_path": str(Path(args.output)),
                        "json_path": str(json_output_path) if json_output_path else None,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Quality gate report: {Path(args.output)}")
            if json_output_path:
                print(f"JSON: {json_output_path}")
            print(
                f"Status: {report.quality_status} "
                f"Passed: {report.passed_count} "
                f"Failed: {report.failed_count} "
                f"Skipped: {report.skipped_count}"
            )
        return 0

    if args.command == "project-status":
        json_output_path = Path(args.json_output) if args.json_output else None
        report = write_project_status_report(
            project_root=Path(args.project_root),
            artifacts_dir=Path(args.artifacts_dir),
            output_path=Path(args.output),
            json_output_path=json_output_path,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "project_root": report.project_root,
                        "artifacts_dir": report.artifacts_dir,
                        "generated_at": report.generated_at,
                        "overall_status": report.overall_status,
                        "mvp_status": report.mvp_status,
                        "mvp_completion_percent": report.mvp_completion_percent,
                        "delivery_status": report.delivery_status,
                        "delivery_completion_percent": report.delivery_completion_percent,
                        "quality_status": report.quality_status,
                        "launch_status": report.launch_status,
                        "release_status": report.release_status,
                        "docker_smoke_status": report.docker_smoke_status,
                        "live_calibration_status": report.live_calibration_status,
                        "saved_live_provider_count": report.saved_live_provider_count,
                        "blocker_count": report.blocker_count,
                        "warning_count": report.warning_count,
                        "evidence_freshness_status": report.evidence_freshness_status,
                        "stale_source_count": report.stale_source_count,
                        "undated_source_count": report.undated_source_count,
                        "missing_source_count": len(report.missing_sources),
                        "report_path": str(Path(args.output)),
                        "json_path": str(json_output_path) if json_output_path else None,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Project status report: {Path(args.output)}")
            if json_output_path:
                print(f"JSON: {json_output_path}")
            print(
                f"Status: {report.overall_status} "
                f"MVP: {report.mvp_completion_percent:.1f}% "
                f"Delivery: {report.delivery_completion_percent:.1f}% "
                f"Launch: {report.launch_status} "
                f"Quality: {report.quality_status} "
                f"Freshness: {report.evidence_freshness_status}"
            )
        return 0

    if args.command == "refresh-evidence":
        json_output_path = Path(args.json_output) if args.json_output else None
        max_failure_runs = None if args.max_failure_runs == 0 else args.max_failure_runs
        report = write_evidence_refresh_report(
            project_root=Path(args.project_root),
            artifacts_dir=Path(args.artifacts_dir),
            output_path=Path(args.output),
            json_output_path=json_output_path,
            max_failure_runs=max_failure_runs,
            include_quality_gate=args.include_quality_gate,
            quality_timeout_seconds=args.quality_timeout_seconds,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "project_root": report.project_root,
                        "artifacts_dir": report.artifacts_dir,
                        "generated_at": report.generated_at,
                        "refresh_status": report.refresh_status,
                        "step_count": report.step_count,
                        "passed_count": report.passed_count,
                        "failed_count": report.failed_count,
                        "skipped_count": report.skipped_count,
                        "quality_gate_refreshed": report.quality_gate_refreshed,
                        "report_path": str(Path(args.output)),
                        "json_path": str(json_output_path) if json_output_path else None,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Evidence refresh report: {Path(args.output)}")
            if json_output_path:
                print(f"JSON: {json_output_path}")
            print(
                f"Status: {report.refresh_status} "
                f"Steps: {report.step_count} "
                f"Passed: {report.passed_count} "
                f"Failed: {report.failed_count} "
                f"Skipped: {report.skipped_count}"
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
        choices=["agentless", "heuristic", "langgraph", "deepagents", "openai_agents"],
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
    _add_sandbox_args(run)
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

    validate_issue_corpus_parser = subparsers.add_parser(
        "validate-issue-corpus",
        help="Validate public issue-corpus metadata for real-world eval planning.",
    )
    validate_issue_corpus_parser.add_argument(
        "--corpus",
        default="evals/issue_corpora/public_issue_smoke_v1/issues.json",
        help="Issue corpus JSON manifest.",
    )
    validate_issue_corpus_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Issue corpus validation output directory.",
    )
    validate_issue_corpus_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    preflight_issue_corpus_parser = subparsers.add_parser(
        "preflight-issue-corpus",
        help="Check repository reachability for public issue-corpus entries.",
    )
    preflight_issue_corpus_parser.add_argument(
        "--corpus",
        default="evals/issue_corpora/public_issue_smoke_v1/issues.json",
        help="Issue corpus JSON manifest.",
    )
    preflight_issue_corpus_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Issue corpus preflight output directory.",
    )
    preflight_issue_corpus_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=20,
        help="Per-repository git ls-remote timeout.",
    )
    preflight_issue_corpus_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    preview_issue_corpus_parser = subparsers.add_parser(
        "preview-issue-corpus-context",
        help="Clone/index public issue-corpus repos and write retrieval preview artifacts.",
    )
    preview_issue_corpus_parser.add_argument(
        "--corpus",
        default="evals/issue_corpora/public_issue_smoke_v1/issues.json",
        help="Issue corpus JSON manifest.",
    )
    preview_issue_corpus_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Issue corpus context preview output directory.",
    )
    preview_issue_corpus_parser.add_argument(
        "--context-provider",
        choices=["native", "native_hybrid", "native_graph"],
        default="native_hybrid",
        help="Retriever to use for source-free public issue context previews.",
    )
    preview_issue_corpus_parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of retrieved files to record per issue.",
    )
    preview_issue_corpus_parser.add_argument(
        "--max-issues",
        type=int,
        default=0,
        help="Maximum issue entries to preview. Use 0 for all entries.",
    )
    preview_issue_corpus_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    materialize_issue_corpus_parser = subparsers.add_parser(
        "materialize-issue-corpus-tasks",
        help="Write source-free task manifests from public issue context-preview results.",
    )
    materialize_issue_corpus_parser.add_argument(
        "--corpus",
        default="evals/issue_corpora/public_issue_smoke_v1/issues.json",
        help="Issue corpus JSON manifest.",
    )
    materialize_issue_corpus_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Issue corpus materialization output directory.",
    )
    materialize_issue_corpus_parser.add_argument(
        "--context-preview",
        default=None,
        help="Context preview results JSON. Defaults to <output>/context_preview_results.json.",
    )
    materialize_issue_corpus_parser.add_argument(
        "--max-issues",
        type=int,
        default=0,
        help="Maximum issue entries to materialize. Use 0 for all entries.",
    )
    materialize_issue_corpus_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    validate_materialized_issue_tasks_parser = subparsers.add_parser(
        "validate-materialized-issue-tasks",
        help="Validate source-free public issue task manifests and runbooks.",
    )
    validate_materialized_issue_tasks_parser.add_argument(
        "--tasks-dir",
        default="artifacts/experiments/public_issue_corpus_v1/materialized_tasks",
        help="Directory containing materialized task subdirectories.",
    )
    validate_materialized_issue_tasks_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Materialized task validation output directory.",
    )
    validate_materialized_issue_tasks_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    materialized_run_readiness_parser = subparsers.add_parser(
        "check-materialized-run-readiness",
        help="Check policy and risk readiness before running materialized public issue tasks.",
    )
    materialized_run_readiness_parser.add_argument(
        "--tasks-dir",
        default="artifacts/experiments/public_issue_corpus_v1/materialized_tasks",
        help="Directory containing materialized task subdirectories.",
    )
    materialized_run_readiness_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Materialized run readiness output directory.",
    )
    materialized_run_readiness_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    focused_test_plan_parser = subparsers.add_parser(
        "plan-materialized-focused-tests",
        help="Plan focused pytest commands from materialized public issue retrieval hints.",
    )
    focused_test_plan_parser.add_argument(
        "--tasks-dir",
        default="artifacts/experiments/public_issue_corpus_v1/materialized_tasks",
        help="Directory containing materialized task subdirectories.",
    )
    focused_test_plan_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Focused test plan output directory.",
    )
    focused_test_plan_parser.add_argument(
        "--max-paths",
        type=int,
        default=2,
        help="Maximum retrieved test-like paths to include in each focused command.",
    )
    focused_test_plan_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    focused_test_run_parser = subparsers.add_parser(
        "run-materialized-focused-tests",
        help="Execute focused pytest commands planned for materialized public issue tasks.",
    )
    focused_test_run_parser.add_argument(
        "--plan",
        default="artifacts/experiments/public_issue_corpus_v1/focused_test_plan_results.json",
        help="Focused test plan results JSON.",
    )
    focused_test_run_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Focused test run output directory.",
    )
    focused_test_run_parser.add_argument(
        "--sandbox-mode",
        choices=["local", "docker"],
        default="local",
        help="Sandbox runner to use for focused test commands.",
    )
    focused_test_run_parser.add_argument(
        "--sandbox-image",
        default="python:3.12-slim",
        help="Docker image used when --sandbox-mode docker is selected.",
    )
    focused_test_run_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=60,
        help="Per-task focused test timeout.",
    )
    focused_test_run_parser.add_argument(
        "--max-tasks",
        type=int,
        default=0,
        help="Maximum planned tasks to execute. Use 0 for all planned tasks.",
    )
    focused_test_run_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    focused_test_diagnosis_parser = subparsers.add_parser(
        "diagnose-focused-test-runs",
        help="Classify focused public issue test failures from saved stdout/stderr logs.",
    )
    focused_test_diagnosis_parser.add_argument(
        "--results",
        default="artifacts/experiments/public_issue_corpus_v1/focused_test_run_results.json",
        help="Focused test run results JSON.",
    )
    focused_test_diagnosis_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Focused test diagnosis output directory.",
    )
    focused_test_diagnosis_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    focused_test_setup_parser = subparsers.add_parser(
        "plan-focused-test-setups",
        help="Plan sandbox setup steps from focused public issue test diagnoses.",
    )
    focused_test_setup_parser.add_argument(
        "--diagnosis",
        default="artifacts/experiments/public_issue_corpus_v1/focused_test_diagnosis_results.json",
        help="Focused test diagnosis results JSON.",
    )
    focused_test_setup_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Focused test setup-plan output directory.",
    )
    focused_test_setup_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    focused_test_setup_readiness_parser = subparsers.add_parser(
        "check-focused-test-setup-readiness",
        help="Check sandbox and repository readiness before executing focused test setup plans.",
    )
    focused_test_setup_readiness_parser.add_argument(
        "--setup-plan",
        default="artifacts/experiments/public_issue_corpus_v1/focused_test_setup_plan_results.json",
        help="Focused test setup-plan results JSON.",
    )
    focused_test_setup_readiness_parser.add_argument(
        "--docker-smoke",
        default="artifacts/experiments/docker_smoke.json",
        help="Docker smoke JSON report to use as sandbox readiness evidence.",
    )
    focused_test_setup_readiness_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Focused test setup-readiness output directory.",
    )
    focused_test_setup_readiness_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    focused_test_setup_execution_parser = subparsers.add_parser(
        "execute-focused-test-setups",
        help="Dry-run or execute focused public issue setup commands after readiness checks.",
    )
    focused_test_setup_execution_parser.add_argument(
        "--readiness",
        default=(
            "artifacts/experiments/public_issue_corpus_v1/"
            "focused_test_setup_readiness_results.json"
        ),
        help="Focused test setup-readiness results JSON.",
    )
    focused_test_setup_execution_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Focused test setup-execution output directory.",
    )
    focused_test_setup_execution_parser.add_argument(
        "--sandbox-mode",
        choices=["local", "docker"],
        default="docker",
        help="Sandbox runner to use when --execute is set.",
    )
    focused_test_setup_execution_parser.add_argument(
        "--sandbox-image",
        default="python:3.12-slim",
        help="Docker image used when --sandbox-mode docker is selected.",
    )
    focused_test_setup_execution_parser.add_argument(
        "--sandbox-network",
        choices=["none", "bridge"],
        default="none",
        help="Docker network mode used when --execute and --sandbox-mode docker are selected.",
    )
    focused_test_setup_execution_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
        help="Per-setup-command timeout when --execute is set.",
    )
    focused_test_setup_execution_parser.add_argument(
        "--max-tasks",
        type=int,
        default=0,
        help="Maximum readiness records to process. Use 0 for all records.",
    )
    focused_test_setup_execution_parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute commands instead of writing dry-run evidence.",
    )
    focused_test_setup_execution_parser.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Permit readiness-warning tasks to proceed after review.",
    )
    focused_test_setup_execution_parser.add_argument(
        "--allow-dependency-installs",
        action="store_true",
        help="Permit the narrow editable-install setup policy; requires --sandbox-mode docker.",
    )
    focused_test_setup_execution_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    focused_test_setup_validation_parser = subparsers.add_parser(
        "validate-focused-test-setups",
        help="Dry-run or run validation commands after focused public issue setup execution.",
    )
    focused_test_setup_validation_parser.add_argument(
        "--setup-execution",
        default=(
            "artifacts/experiments/public_issue_corpus_v1/"
            "focused_test_setup_execution_results.json"
        ),
        help="Focused test setup-execution results JSON.",
    )
    focused_test_setup_validation_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Focused test setup-validation output directory.",
    )
    focused_test_setup_validation_parser.add_argument(
        "--sandbox-mode",
        choices=["local", "docker"],
        default="docker",
        help="Sandbox runner to use when --execute is set.",
    )
    focused_test_setup_validation_parser.add_argument(
        "--sandbox-image",
        default="python:3.12-slim",
        help="Docker image used when --sandbox-mode docker is selected.",
    )
    focused_test_setup_validation_parser.add_argument(
        "--sandbox-network",
        choices=["none", "bridge"],
        default="none",
        help="Docker network mode used when --execute and --sandbox-mode docker are selected.",
    )
    focused_test_setup_validation_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
        help="Per-validation-command timeout when --execute is set.",
    )
    focused_test_setup_validation_parser.add_argument(
        "--max-tasks",
        type=int,
        default=0,
        help="Maximum setup-execution records to process. Use 0 for all records.",
    )
    focused_test_setup_validation_parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute validation commands instead of writing dry-run evidence.",
    )
    focused_test_setup_validation_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

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
        choices=["agentless", "heuristic", "langgraph", "deepagents", "openai_agents"],
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
    _add_sandbox_args(eval_repair)
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
        choices=[
            "agentless",
            "heuristic",
            "langgraph",
            "langgraph_fake_model",
            "deepagents",
            "openai_agents",
        ],
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
    _add_sandbox_args(eval_scaffold)
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
    _add_sandbox_args(eval_patch_search)
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

    live_calibration = subparsers.add_parser(
        "live-calibration",
        help="Generate a live-provider calibration readiness report.",
    )
    live_calibration.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan for saved provider evidence.",
    )
    live_calibration.add_argument(
        "--output",
        default="artifacts/experiments/calibration_readiness.md",
        help="Markdown live calibration readiness report output path.",
    )
    live_calibration.add_argument(
        "--json-output",
        help="Optional JSON live calibration readiness report output path.",
    )
    live_calibration.add_argument("--json", action="store_true", help="Print JSON summary.")

    live_calibration_plan = subparsers.add_parser(
        "live-calibration-plan",
        help="Generate an executable live-provider calibration plan.",
    )
    live_calibration_plan.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan for saved provider evidence.",
    )
    live_calibration_plan.add_argument(
        "--output",
        default="artifacts/experiments/live_calibration_plan.md",
        help="Markdown live calibration plan output path.",
    )
    live_calibration_plan.add_argument(
        "--json-output",
        default="artifacts/experiments/live_calibration_plan.json",
        help="Optional JSON live calibration plan output path.",
    )
    live_calibration_plan.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    docker_smoke = subparsers.add_parser(
        "docker-smoke",
        help="Generate Docker sandbox preflight and seeded-smoke evidence.",
    )
    docker_smoke.add_argument(
        "--project-root",
        default=".",
        help="Project root containing the seeded task and Dockerfile.",
    )
    docker_smoke.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to write smoke evidence.",
    )
    docker_smoke.add_argument(
        "--output",
        default="artifacts/experiments/docker_smoke.md",
        help="Markdown Docker smoke report output path.",
    )
    docker_smoke.add_argument(
        "--json-output",
        default="artifacts/experiments/docker_smoke.json",
        help="Optional JSON Docker smoke report output path.",
    )
    docker_smoke.add_argument(
        "--image",
        default="patchsmith-seeded-smoke:py312",
        help="Local Docker image containing Python and seeded-suite test dependencies.",
    )
    docker_smoke.add_argument(
        "--task-dir",
        default="evals/tasks/seeded_bugs_v1/task_001_logic_bug",
        help="Seeded task directory to run inside Docker.",
    )
    docker_smoke.add_argument(
        "--test-command",
        default="python3 -m pytest",
        help="Policy-allowed test command to run inside Docker.",
    )
    docker_smoke.add_argument(
        "--runtime",
        choices=["heuristic", "langgraph", "deepagents", "openai_agents"],
        default="heuristic",
        help="Runtime to use for the smoke repair.",
    )
    docker_smoke.add_argument(
        "--context-provider",
        choices=["native", "native_hybrid", "native_graph", "ctxhelm_cli", "auto"],
        default="native_hybrid",
        help="Context provider to use for the smoke repair.",
    )
    docker_smoke.add_argument(
        "--docker-binary",
        default="docker",
        help="Docker CLI binary to use for preflight checks.",
    )
    docker_smoke.add_argument(
        "--skip-run",
        action="store_true",
        help="Only run Docker daemon and image preflight checks.",
    )
    docker_smoke.add_argument("--json", action="store_true", help="Print JSON summary.")

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

    launch_blockers = subparsers.add_parser(
        "launch-blockers",
        help="Generate a prioritized launch-blocker backlog from readiness artifacts.",
    )
    launch_blockers.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    launch_blockers.add_argument(
        "--output",
        default="artifacts/experiments/launch_blockers.md",
        help="Markdown launch-blocker backlog output path.",
    )
    launch_blockers.add_argument(
        "--json-output",
        default="artifacts/experiments/launch_blockers.json",
        help="Optional JSON launch-blocker backlog output path.",
    )
    launch_blockers.add_argument("--json", action="store_true", help="Print JSON summary.")

    mvp_progress = subparsers.add_parser(
        "mvp-progress",
        help="Generate an evidence-weighted MVP checklist progress report.",
    )
    mvp_progress.add_argument(
        "--project-root",
        default=".",
        help="Project root to inspect for source, docs, tests, and checklist evidence.",
    )
    mvp_progress.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    mvp_progress.add_argument(
        "--output",
        default="artifacts/experiments/mvp_progress.md",
        help="Markdown MVP progress report output path.",
    )
    mvp_progress.add_argument(
        "--json-output",
        help="Optional JSON MVP progress report output path.",
    )
    mvp_progress.add_argument(
        "--max-failure-runs",
        type=int,
        default=0,
        help="Maximum recent runs to scan for failure visibility. Use 0 to scan all runs.",
    )
    mvp_progress.add_argument("--json", action="store_true", help="Print JSON summary.")

    delivery_audit = subparsers.add_parser(
        "delivery-audit",
        help="Generate an objective-to-evidence delivery audit report.",
    )
    delivery_audit.add_argument(
        "--project-root",
        default=".",
        help="Project root to inspect for docs, tests, and Git metadata.",
    )
    delivery_audit.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    delivery_audit.add_argument(
        "--output",
        default="artifacts/experiments/delivery_audit.md",
        help="Markdown delivery audit output path.",
    )
    delivery_audit.add_argument(
        "--json-output",
        default="artifacts/experiments/delivery_audit.json",
        help="Optional JSON delivery audit output path.",
    )
    delivery_audit.add_argument("--json", action="store_true", help="Print JSON summary.")

    quality_gate = subparsers.add_parser(
        "quality-gate",
        help="Run local verification commands and save a quality-gate report.",
    )
    quality_gate.add_argument(
        "--project-root",
        default=".",
        help="Project root where verification commands run.",
    )
    quality_gate.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to write logs under.",
    )
    quality_gate.add_argument(
        "--output",
        default="artifacts/experiments/quality_gate.md",
        help="Markdown quality-gate report output path.",
    )
    quality_gate.add_argument(
        "--json-output",
        default="artifacts/experiments/quality_gate.json",
        help="Optional JSON quality-gate output path.",
    )
    quality_gate.add_argument(
        "--logs-dir",
        help="Directory for per-command stdout/stderr logs.",
    )
    quality_gate.add_argument(
        "--timeout-seconds",
        type=int,
        default=180,
        help="Per-command timeout in seconds.",
    )
    quality_gate.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip the full pytest gate.",
    )
    quality_gate.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip the package build gate.",
    )
    quality_gate.add_argument("--json", action="store_true", help="Print JSON summary.")

    project_status = subparsers.add_parser(
        "project-status",
        help="Generate a consolidated status report from saved evidence artifacts.",
    )
    project_status.add_argument(
        "--project-root",
        default=".",
        help="Project root to include in the status report.",
    )
    project_status.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    project_status.add_argument(
        "--output",
        default="artifacts/experiments/project_status.md",
        help="Markdown project status report output path.",
    )
    project_status.add_argument(
        "--json-output",
        default="artifacts/experiments/project_status.json",
        help="Optional JSON project status output path.",
    )
    project_status.add_argument("--json", action="store_true", help="Print JSON summary.")

    refresh_evidence = subparsers.add_parser(
        "refresh-evidence",
        help="Regenerate saved review/status evidence artifacts in dependency order.",
    )
    refresh_evidence.add_argument(
        "--project-root",
        default=".",
        help="Project root to inspect for docs, Git metadata, and quality-gate context.",
    )
    refresh_evidence.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to refresh.",
    )
    refresh_evidence.add_argument(
        "--output",
        default="artifacts/experiments/evidence_refresh.md",
        help="Markdown evidence-refresh report output path.",
    )
    refresh_evidence.add_argument(
        "--json-output",
        default="artifacts/experiments/evidence_refresh.json",
        help="Optional JSON evidence-refresh output path.",
    )
    refresh_evidence.add_argument(
        "--max-failure-runs",
        type=int,
        default=0,
        help="Maximum recent runs to scan for failure visibility. Use 0 to scan all runs.",
    )
    refresh_evidence.add_argument(
        "--include-quality-gate",
        action="store_true",
        help="Also run the full quality gate during refresh.",
    )
    refresh_evidence.add_argument(
        "--quality-timeout-seconds",
        type=int,
        default=180,
        help="Per-command timeout for quality-gate steps when included.",
    )
    refresh_evidence.add_argument("--json", action="store_true", help="Print JSON summary.")

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


def _add_sandbox_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--sandbox-mode",
        choices=["local", "docker"],
        default="local",
        help="Sandbox runner for executing task test commands.",
    )
    parser.add_argument(
        "--sandbox-image",
        default="python:3.12-slim",
        help="Docker image used when --sandbox-mode=docker.",
    )


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
