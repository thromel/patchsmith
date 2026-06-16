"""CLI evals commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from patchsmith.artifacts import write_json
from patchsmith.cli._args import _add_sandbox_args
from patchsmith.cli._types import CommandHandler
from patchsmith.evaluation import (
    ComplexBenchmarkSuitePreflight,
    load_complex_benchmark_suite_spec,
    resolve_complex_benchmark_suite_config,
    run_patch_search_evaluation,
    run_repair_evaluation,
    run_retrieval_evaluation,
    run_scaffold_comparison,
    summarize_complex_benchmark,
    summarize_complex_benchmark_suite,
    validate_complex_benchmark_suite_inputs,
    validate_seeded_dataset,
)
from patchsmith.evaluation.complex.thresholds import (
    COMPLEX_BENCHMARK_SUITE_THRESHOLDS,
)


def register(subparsers: argparse._SubParsersAction) -> dict[str, CommandHandler]:
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
        choices=["agentless", "heuristic", "deepagents"],
        default="heuristic",
        help="Runtime to evaluate.",
    )
    eval_repair.add_argument(
        "--planner",
        choices=["heuristic", "fake_model", "openai", "deepagents"],
        default="heuristic",
        help="Repair planner to evaluate. `openai` requires OPENAI_API_KEY.",
    )
    eval_repair.add_argument(
        "--max-retries",
        type=int,
        default=0,
        help="Maximum extra DeepAgents feedback retries after the first attempt.",
    )
    eval_repair.add_argument(
        "--max-tasks",
        type=int,
        default=0,
        help="Maximum seeded tasks to run; 0 runs the full dataset.",
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
            "deepagents",
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
        "--max-tasks",
        type=int,
        default=0,
        help="Maximum seeded tasks to run per scaffold; 0 runs the full dataset.",
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

    eval_complex = subparsers.add_parser(
        "eval-complex",
        help="Summarize public issue repair-attempt artifacts as a complex benchmark.",
    )
    eval_complex.add_argument(
        "--attempt-dir",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Directory containing public_issue_repair_attempt_results.json.",
    )
    eval_complex.add_argument(
        "--benchmark",
        default="public_issue_repair_attempts",
        help="Benchmark label to write into the report.",
    )
    eval_complex.add_argument(
        "--output",
        default="artifacts/experiments/complex_deepagents_benchmark_v1",
        help="Complex benchmark summary output directory.",
    )
    eval_complex.add_argument("--json", action="store_true", help="Print JSON summary.")

    eval_complex_suite = subparsers.add_parser(
        "eval-complex-suite",
        help="Aggregate multiple public issue repair-attempt directories.",
    )
    eval_complex_suite.add_argument(
        "--suite-spec",
        help=(
            "JSON suite spec containing benchmark, attempt_dirs, optional output_dir, "
            "and gate thresholds."
        ),
    )
    eval_complex_suite.add_argument(
        "--attempt-dir",
        action="append",
        default=[],
        help="Directory containing public_issue_repair_attempt_results.json. Repeat for multiple runs.",
    )
    eval_complex_suite.add_argument(
        "--benchmark",
        default=None,
        help="Benchmark label to write into the report.",
    )
    eval_complex_suite.add_argument(
        "--output",
        default=None,
        help="Complex benchmark suite output directory.",
    )
    _add_complex_suite_threshold_args(eval_complex_suite)
    eval_complex_suite.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate suite inputs and gate configuration without writing benchmark artifacts.",
    )
    eval_complex_suite.add_argument("--json", action="store_true", help="Print JSON summary.")

    return {
        "eval-retrieval": _eval_retrieval_command,
        "validate-dataset": _validate_dataset_command,
        "eval-repair": _eval_repair_command,
        "eval-scaffold": _eval_scaffold_command,
        "eval-patch-search": _eval_patch_search_command,
        "eval-complex": _eval_complex_command,
        "eval-complex-suite": _eval_complex_suite_command,
    }


def _add_complex_suite_threshold_args(parser: argparse.ArgumentParser) -> None:
    for threshold in COMPLEX_BENCHMARK_SUITE_THRESHOLDS:
        parser.add_argument(
            threshold.cli_flag,
            type=int if threshold.value_kind == "nonnegative_int" else float,
            help=threshold.cli_help,
        )


def _eval_retrieval_command(args: argparse.Namespace) -> int:
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


def _validate_dataset_command(args: argparse.Namespace) -> int:
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


def _eval_repair_command(args: argparse.Namespace) -> int:
    results, summary = run_repair_evaluation(
        dataset_dir=Path(args.dataset),
        runtime=args.runtime,
        planner=args.planner,
        max_retries=args.max_retries,
        max_tasks=None if args.max_tasks == 0 else args.max_tasks,
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


def _eval_scaffold_command(args: argparse.Namespace) -> int:
    results = run_scaffold_comparison(
        dataset_dir=Path(args.dataset),
        variants=args.variant
        or [
            "agentless",
            "heuristic",
            "deepagents",
        ],
        context_provider=args.context_provider,
        output_dir=Path(args.output),
        max_tasks=None if args.max_tasks == 0 else args.max_tasks,
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


def _eval_patch_search_command(args: argparse.Namespace) -> int:
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


def _eval_complex_command(args: argparse.Namespace) -> int:
    results, summary = summarize_complex_benchmark(
        attempt_dir=Path(args.attempt_dir),
        output_dir=Path(args.output),
        benchmark=args.benchmark,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "result_count": len(results),
                    "report_path": str(Path(args.output) / "complex_benchmark_report.md"),
                    "summary": summary.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(f"Report: {Path(args.output) / 'complex_benchmark_report.md'}")
        print(
            f"{summary.benchmark}: validation_rate={summary.validation_rate:.2f} "
            f"pass_at_n={summary.validated_task_pass_at_n_rate:.2f} "
            f"patch_generated={summary.patch_generated_rate:.2f} "
            f"completed={summary.validated_tasks}/{summary.attempted_tasks}"
        )
    return 0


def _eval_complex_suite_command(args: argparse.Namespace) -> int:
    suite_spec = (
        load_complex_benchmark_suite_spec(Path(args.suite_spec)) if args.suite_spec else None
    )
    threshold_kwargs = {
        threshold.name: getattr(args, threshold.name)
        for threshold in COMPLEX_BENCHMARK_SUITE_THRESHOLDS
    }
    config = resolve_complex_benchmark_suite_config(
        suite_spec=suite_spec,
        attempt_dirs=[Path(path) for path in args.attempt_dir],
        output_dir=Path(args.output) if args.output else None,
        benchmark=args.benchmark,
        **threshold_kwargs,
    )
    if not config.attempt_dirs:
        raise ValueError(
            "eval-complex-suite requires --attempt-dir or --suite-spec with attempt_dirs"
        )
    preflight = validate_complex_benchmark_suite_inputs(
        attempt_dirs=list(config.attempt_dirs),
        output_dir=config.output_dir,
        benchmark=config.benchmark,
        gate_threshold_count=config.thresholds.count,
    )
    if args.validate_only or preflight.status == "failed":
        _print_complex_suite_preflight(
            preflight,
            json_output=args.json,
        )
        return 0 if preflight.status == "passed" else 1
    results, summary, attempt_summaries, followup_candidates = summarize_complex_benchmark_suite(
        attempt_dirs=list(config.attempt_dirs),
        output_dir=config.output_dir,
        benchmark=config.benchmark,
        thresholds=config.thresholds,
    )
    gate = config.thresholds.gate(summary)
    if config.gate_requested:
        write_json(
            config.output_dir / "complex_benchmark_suite_gate.json",
            gate.to_dict(),
            trailing_newline=True,
        )
    if args.json:
        print(
            json.dumps(
                {
                    "result_count": len(results),
                    "report_path": str(config.output_dir / "complex_benchmark_suite_report.md"),
                    "summary": summary.to_dict(),
                    "attempt_summaries": [
                        attempt_summary.to_dict() for attempt_summary in attempt_summaries
                    ],
                    "followup_candidates": [
                        candidate.to_dict() for candidate in followup_candidates
                    ],
                    "gate": gate.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(f"Report: {config.output_dir / 'complex_benchmark_suite_report.md'}")
        print(
            f"{summary.benchmark}: validation_rate={summary.validation_rate:.2f} "
            f"pass_at_n={summary.validated_task_pass_at_n_rate:.2f} "
            f"cost={summary.estimated_cost_usd or 0.0:.6f} "
            f"completed={summary.validated_tasks}/{summary.attempted_tasks}"
        )
        if config.gate_requested:
            print(f"gate={gate.status}")
            for failure in gate.failures:
                print(f"- {failure}")
    return 1 if gate.status == "failed" else 0


def _print_complex_suite_preflight(
    preflight: ComplexBenchmarkSuitePreflight,
    *,
    json_output: bool,
) -> None:
    if json_output:
        print(json.dumps({"preflight": preflight.to_dict()}, indent=2))
        return
    print(f"preflight={preflight.status}")
    print(f"benchmark={preflight.benchmark}")
    print(f"attempt_dirs={preflight.attempt_dir_count}")
    print(f"result_files={preflight.result_file_count}")
    print(f"gate_thresholds={preflight.gate_threshold_count}")
    for error in preflight.errors:
        print(f"- error: {error}")
    for warning in preflight.warnings:
        print(f"- warning: {warning}")
