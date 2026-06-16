# Runbook

## Status

Draft v0.1

## Purpose

This runbook defines common local operations and troubleshooting flows for PatchSmith Research.

## Local development startup

Expected future command:

```bash
make dev
```

Equivalent steps:

```bash
docker compose up -d postgres redis
uvicorn apps.api.main:app --reload
cd apps/web && npm run dev
python -m patchsmith.worker
```

## Run one repair task

Current seeded smoke command:

```bash
PYTHONPATH=src python3 -m patchsmith.cli run \
  --repo evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo \
  --issue-file evals/tasks/seeded_bugs_v1/task_001_logic_bug/issue.md \
  --test-command "python3 -m pytest" \
  --runtime heuristic \
  --context-provider native_hybrid \
  --artifacts-dir artifacts \
  --json
```

Expected future DeepAgents command:

```bash
patchsmith run \
  --repo https://github.com/example/repo \
  --issue-file examples/issues/issue_001.md \
  --runtime deepagents \
  --retrieval hybrid_v0 \
  --test-command "python -m pytest"
```

## Run seeded evaluation

Dataset validation:

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-dataset \
  --dataset evals/tasks/seeded_bugs_v1 \
  --output artifacts/experiments/seeded_dataset_validation_v1 \
  --json
```

Retrieval evaluation:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-retrieval \
  --dataset evals/tasks/seeded_bugs_v1 \
  --context-provider native \
  --context-provider native_hybrid \
  --context-provider native_graph \
  --context-provider ctxhelm_cli \
  --output artifacts/experiments/retrieval_eval_v1 \
  --json
```

Graph-specific retrieval stress evaluation:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-retrieval \
  --dataset evals/tasks/graph_retrieval_v1 \
  --context-provider native \
  --context-provider native_hybrid \
  --context-provider native_graph \
  --output artifacts/experiments/graph_retrieval_eval_v1 \
  --json
```

Use `native_hybrid` when issue text contains source symbols, repo-relative paths, or Python traceback frames. It keeps retrieval local while boosting likely source files over related tests.
Use `native_graph` when you want deterministic graph expansion through Python file, symbol, import, and test/source edges.

The retrieval report includes approximate context packing metadata: context count, source/test context counts, packed excerpt characters, and approximate tokens.

Repair evaluation:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-repair \
  --dataset evals/tasks/seeded_bugs_v1 \
  --runtime heuristic \
  --context-provider native_hybrid \
  --output artifacts/experiments/repair_eval_v1 \
  --json
```

DeepAgents orchestration evaluation with the current deterministic planner:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-repair \
  --dataset evals/tasks/seeded_bugs_v1 \
  --runtime deepagents \
  --context-provider native_hybrid \
  --output artifacts/experiments/deepagents_repair_eval_v1 \
  --json
```

DeepAgents evaluation through the offline model-planner contract:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-repair \
  --dataset evals/tasks/seeded_bugs_v1 \
  --runtime deepagents \
  --planner fake_model \
  --context-provider native_hybrid \
  --output artifacts/experiments/deepagents_model_repair_eval_v1 \
  --json
```

`fake_model` is an offline JSON model double. It exercises prompt construction, model-output parsing, retrieved-path validation, DeepAgents patch application, reports, and eval metrics without live credentials.

Public issue corpus validation:

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-issue-corpus \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The public issue corpus records real GitHub issue candidates for future external runs. Treat a valid corpus as task-breadth evidence only; it is not solved-run evidence.

Public issue repository preflight:

```bash
PYTHONPATH=src python3 -m patchsmith.cli preflight-issue-corpus \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The preflight checks repository reachability and records current branch/HEAD metadata before any source clone or repair attempt.

Public issue context preview:

```bash
PYTHONPATH=src python3 -m patchsmith.cli preview-issue-corpus-context \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --context-provider native_hybrid \
  --top-k 5 \
  --json
```

The preview clones and indexes reachable corpus repositories, then records source-free retrieved-file summaries. Treat it as context plumbing evidence only; issue reproduction, patch generation, and test success require normal run artifacts.

Public issue task materialization:

```bash
PYTHONPATH=src python3 -m patchsmith.cli materialize-issue-corpus-tasks \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The materializer writes per-issue task manifests, issue files, and runbooks from the context preview. Treat these as setup artifacts for an external evaluation lane, not solved-run artifacts.

Public issue task validation:

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-materialized-issue-tasks \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The validator checks manifest shape, source-free context summaries, task files, local repository snapshots, and suggested run commands before those manifests are used in external evaluation.

Public issue run readiness:

```bash
PYTHONPATH=src python3 -m patchsmith.cli check-materialized-run-readiness \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The readiness report checks command-policy allowlist status and execution risk without running public-repo tests. Treat warning-classified tasks as runnable only after choosing a scoped test command or accepting full-suite cost.

Public issue focused test plan:

```bash
PYTHONPATH=src python3 -m patchsmith.cli plan-materialized-focused-tests \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --max-paths 2 \
  --json
```

The focused test plan derives scoped pytest commands from retrieved test-like files and validates them through the command policy without executing them.

Public issue focused test run:

```bash
PYTHONPATH=src python3 -m patchsmith.cli run-materialized-focused-tests \
  --plan artifacts/experiments/public_issue_corpus_v1/focused_test_plan_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --sandbox-mode docker \
  --sandbox-image patchsmith-seeded-smoke:py312 \
  --sandbox-network bridge \
  --timeout-seconds 300 \
  --json
```

The focused test run executes the planned scoped commands and writes `focused_test_run_report.md`, `focused_test_run_summary.json`, result CSV/JSON, and per-task stdout/stderr files. Use explicit Docker bridge networking only after reviewing that the upstream suite requires local service fixtures or network timeout behavior. Treat focused-command results as environment or upstream-suite readiness evidence unless the run also captures issue reproduction and a PatchSmith-generated repair.

Public issue focused test diagnosis:

```bash
PYTHONPATH=src python3 -m patchsmith.cli diagnose-focused-test-runs \
  --results artifacts/experiments/public_issue_corpus_v1/focused_test_run_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The diagnosis report classifies saved focused-run logs and suggests setup-oriented next actions. Do not execute dependency setup suggestions outside the approved sandbox model, and do not treat diagnosis categories as repair success or failure.

Public issue focused test setup plan:

```bash
PYTHONPATH=src python3 -m patchsmith.cli plan-focused-test-setups \
  --diagnosis artifacts/experiments/public_issue_corpus_v1/focused_test_diagnosis_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The setup plan converts diagnosis categories into explicit setup profiles, setup commands, validation commands, network flags, and sandbox-required flags. Execute those steps only in disposable sandboxes; the plan itself is not validation evidence.

Public issue focused test setup readiness:

```bash
PYTHONPATH=src python3 -m patchsmith.cli check-focused-test-setup-readiness \
  --setup-plan artifacts/experiments/public_issue_corpus_v1/focused_test_setup_plan_results.json \
  --docker-smoke artifacts/experiments/docker_smoke.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The setup-readiness report checks local repository snapshots, validation commands, network flags, and Docker smoke evidence before setup execution. `blocked` means setup must not run yet.

Public issue focused test setup execution:

```bash
PYTHONPATH=src python3 -m patchsmith.cli execute-focused-test-setups \
  --readiness artifacts/experiments/public_issue_corpus_v1/focused_test_setup_readiness_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The setup-execution report defaults to dry-run and records readiness, command-policy, sandbox, and next-action evidence. Add `--execute` only after setup-readiness is not blocked and the selected sandbox/network policy is approved. Blocked execution rows are stop conditions, not reproduction or repair-quality evidence.

Dependency installs are not part of the default command policy. The setup executor can dry-run the narrow editable-install policy with `--allow-dependency-installs --sandbox-mode docker --sandbox-network bridge`; focused setup execution and validation default to `patchsmith-seeded-smoke:py312`. The focused setup policy allows editable project installs and the project `test` dependency group only inside this explicit setup path. Combine that with `--execute` only after Docker smoke passes and the network-enabled sandbox decision is approved.

Public issue focused test setup validation:

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-focused-test-setups \
  --setup-execution artifacts/experiments/public_issue_corpus_v1/focused_test_setup_execution_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The setup-validation report defaults to dry-run and records whether validation commands can run after setup execution. Blocked rows mean setup did not complete and must not be counted as issue reproduction or repair evidence.

Public issue reproduction plan:

```bash
PYTHONPATH=src python3 -m patchsmith.cli plan-public-issue-reproductions \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --focused-plan artifacts/experiments/public_issue_corpus_v1/focused_test_plan_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The reproduction-plan report records candidate commands and expected-failure signal gaps before public issue repairs. It also emits `public_issue_reproduction_specs_template.json` with task-specific candidate commands for review. Add `--reproduction-specs <reviewed-specs.json>` when reviewed criteria are available; the specs file accepts `task_id`, optional `command`, optional `fixture_files`, optional `source_hints`, and `expected_failure_signals`, and `evals/issue_corpora/public_issue_smoke_v1/reproduction_specs.template.json` is the authoring template. Reviewed criteria that should survive refreshes live in `evals/issue_corpora/public_issue_smoke_v1/reproduction_specs.reviewed.json`; `refresh-evidence` uses that file when present. Fixture files must use repository-relative paths and are written only to disposable execution workspaces. Source hints must be repository-relative file paths, optionally with a reviewed identifier focus such as `src/pkg/module.py#function_name`, and are copied into the repair prompt to improve targeting. Treat `warning` rows as planning work, not reproduction evidence; encode the failing assertion, traceback, or behavior mismatch before running repair attempts.

Public issue failure-signal discovery:

```bash
PYTHONPATH=src python3 -m patchsmith.cli discover-public-issue-failure-signals \
  --plan artifacts/experiments/public_issue_corpus_v1/public_issue_reproduction_plan_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The failure-signal discovery report writes `public_issue_failure_signal_discovery_*` artifacts and is dry-run by default. It can be executed to save candidate command logs and extract review hints, but those hints do not count as reproduction evidence until copied into reviewed specs and matched by reproduction execution. When reviewed specs include `fixture_files`, discovery writes them into a disposable copy before running the command and leaves the repository snapshot unchanged.

Public issue reproduction spec validation:

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-public-issue-reproduction-specs \
  --specs artifacts/experiments/public_issue_corpus_v1/public_issue_reproduction_specs_template.json \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --focused-plan artifacts/experiments/public_issue_corpus_v1/focused_test_plan_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The spec-validation report writes `public_issue_reproduction_spec_validation_*` artifacts and blocks missing specs, empty `expected_failure_signals`, unsafe `fixture_files`, extra task IDs, and policy-rejected commands before reproduction execution.

Public issue reproduction execution:

```bash
PYTHONPATH=src python3 -m patchsmith.cli execute-public-issue-reproductions \
  --plan artifacts/experiments/public_issue_corpus_v1/public_issue_reproduction_plan_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The reproduction-execution command writes `public_issue_reproduction_execution_*` artifacts and is dry-run by default. It blocks rows without explicit expected-failure signals. Use `--execute` only after review; `reproduced` means the command failed nonzero and every configured expected-failure signal appeared in saved stdout/stderr logs.

Public issue repair readiness:

```bash
PYTHONPATH=src python3 -m patchsmith.cli check-public-issue-repair-readiness \
  --focused-run artifacts/experiments/public_issue_corpus_v1/focused_test_run_results.json \
  --diagnosis artifacts/experiments/public_issue_corpus_v1/focused_test_diagnosis_results.json \
  --setup-validation artifacts/experiments/public_issue_corpus_v1/focused_test_setup_validation_results.json \
  --reproduction-execution artifacts/experiments/public_issue_corpus_v1/public_issue_reproduction_execution_results.json \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The repair-readiness report joins focused-run, diagnosis, setup-validation, reproduction-execution, and materialized-task command evidence before a public issue repair attempt. Treat `warning` rows as runnable only with explicit caveats; a pre-repair passing focused command means validation is runnable, not that the issue has been reproduced as a failing test.

Public issue repair attempts:

```bash
PYTHONPATH=src python3 -m patchsmith.cli execute-public-issue-repairs \
  --readiness artifacts/experiments/public_issue_corpus_v1/public_issue_repair_readiness_results.json \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --max-retries 1 \
  --json
```

The repair-attempt command writes `public_issue_repair_attempt_*` artifacts and is dry-run by default. It blocks rows without reproduced failing evidence and only executes PatchSmith repairs when readiness is clean, or when warning rows are explicitly accepted with `--allow-warnings`. `--max-retries` enables extra DeepAgents feedback turns after failed validation or a rejected bounded edit.

Scaffold comparison:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-scaffold \
  --dataset evals/tasks/seeded_bugs_v1 \
  --variant agentless \
  --variant heuristic \
  --variant deepagents \
  --context-provider native_hybrid \
  --output artifacts/experiments/scaffold_comparison_v1 \
  --json
```

The scaffold report includes patch/test rates, latency, trace event counts, runtime node counts, failed trace events, retry events, and a 0-5 debug score.
The `deepagents` variant uses PatchSmith's dependency-gated DeepAgents adapter unless the native live planner is selected separately.

Complex public-issue benchmark summary:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-complex \
  --attempt-dir artifacts/experiments/public_issue_corpus_v1 \
  --benchmark public_issue_smoke_v1_latest_all \
  --output artifacts/experiments/complex_deepagents_public_issue_smoke_v1_latest_all \
  --json
```

This reads completed public-issue repair-attempt artifacts and summarizes validation rate, patch-generation rate, trace complexity, retry-feedback artifact coverage, DeepAgents trajectory score, model provider, tokens, and estimated cost. It does not execute tests or call a model.

DeepAgents adapter smoke:

```bash
python -m pip install -e ".[dev,deepagents]"

PYTHONPATH=src python3 -m patchsmith.cli eval-repair \
  --dataset evals/tasks/seeded_bugs_v1 \
  --runtime deepagents \
  --planner heuristic \
  --context-provider native_hybrid \
  --output artifacts/experiments/deepagents_adapter_smoke_v1 \
  --json
```

This proves the `deepagents` import boundary and PatchSmith adapter contract when the extra is installed. It does not prove live DeepAgents model quality unless credentials, model config, and non-offline provider metadata are present.

Patch-search evaluation:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-patch-search \
  --dataset evals/tasks/seeded_bugs_v1 \
  --candidate-count 1 \
  --candidate-count 3 \
  --context-provider native_hybrid \
  --output artifacts/experiments/patch_search_eval_v1 \
  --json
```

The patch-search report compares success@k, selected-candidate success, latency, test-run count, and deterministic candidate artifacts.

Sandbox mode:

```bash
docker build -f docker/seeded-smoke.Dockerfile -t patchsmith-seeded-smoke:py312 .

PYTHONPATH=src python3 -m patchsmith.cli eval-repair \
  --dataset evals/tasks/seeded_bugs_v1 \
  --runtime heuristic \
  --context-provider native_hybrid \
  --sandbox-mode docker \
  --sandbox-image patchsmith-seeded-smoke:py312 \
  --output artifacts/experiments/repair_eval_docker_smoke_v1 \
  --json
```

`run`, `eval-repair`, `eval-scaffold`, and `eval-patch-search` all accept `--sandbox-mode local|docker` plus `--sandbox-image`. Local mode remains the default for fast deterministic development runs. Docker mode wraps the same command-policy decision in `docker run` with implicit image pulls disabled, network disabled, dropped capabilities, a `/workspace` bind mount, resource limits, and sanitized host environment. Use a prebuilt image containing the test runner and task dependencies; otherwise the Docker run can fail even when the patch is correct. The provided `patchsmith-seeded-smoke:py312` image includes current `pip`, `pytest`, and `git`.

Docker smoke report:

```bash
PYTHONPATH=src python3 -m patchsmith.cli docker-smoke \
  --project-root . \
  --artifacts-dir artifacts \
  --image patchsmith-seeded-smoke:py312 \
  --output artifacts/experiments/docker_smoke.md \
  --json-output artifacts/experiments/docker_smoke.json \
  --json
```

The Docker smoke report preserves daemon, image, seeded-run evidence, Docker-related environment/socket diagnostics, host-side Docker Desktop/Colima hints, and remediation commands. `not_available` means Docker was not reachable in the current shell; it does not satisfy the MVP Docker checkbox.

Artifact index:

```bash
PYTHONPATH=src python3 -m patchsmith.cli index-artifacts \
  --artifacts-dir artifacts \
  --output artifacts/experiments/index.md \
  --json-output artifacts/experiments/index.json \
  --html-output artifacts/experiments/index.html \
  --run-detail-output-dir artifacts/experiments/run-details \
  --json
```

The artifact index scans saved experiment folders, classifies report types, counts task results, counts nested run artifacts, normalizes experiment summary metrics, and writes a Markdown review surface plus optional JSON, static HTML dashboard, and generated run-detail pages. Markdown and HTML include research metrics plus the latest 25 runs with links to reports, traces, diffs, stdout, stderr, and generated details. JSON includes the full discovered run list and normalized metric rows.

Failure inspection:

```bash
PYTHONPATH=src python3 -m patchsmith.cli inspect-failures \
  --artifacts-dir artifacts \
  --output artifacts/experiments/failure_report.md \
  --json-output artifacts/experiments/failure_report.json \
  --max-runs 0 \
  --json
```

The failure report scans saved run traces, groups repair-outcome categories, counts failed trace events, and links back to report, trace, and diff artifacts. Use it before a demo review to make failure cases visible instead of relying on only aggregate success metrics.

Demo readiness:

```bash
PYTHONPATH=src python3 -m patchsmith.cli demo-readiness \
  --artifacts-dir artifacts \
  --output artifacts/experiments/demo_readiness.md \
  --json-output artifacts/experiments/demo_readiness.json \
  --json
```

The demo readiness report checks whether the saved artifact set contains experiment evidence, saved runs, normalized metrics, retrieval evidence, repair or scaffold evidence, patch-search evidence, visible failures, and live-provider metadata. `ready_with_caveats` means the offline portfolio demo is coherent but one or more warnings, such as missing live LLM calibration, must be stated publicly.

MVP progress:

```bash
PYTHONPATH=src python3 -m patchsmith.cli mvp-progress \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/mvp_progress.md \
  --json-output artifacts/experiments/mvp_progress.json \
  --json
```

The MVP progress report turns the implementation, docs, test, and artifact checklist into an evidence-weighted percentage. `ready_with_caveats` means the core MVP evidence is present, but warning items must still be named in status updates.

Delivery audit:

```bash
PYTHONPATH=src python3 -m patchsmith.cli delivery-audit \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/delivery_audit.md \
  --json-output artifacts/experiments/delivery_audit.json \
  --json
```

The delivery audit maps the original planning/development objective to concrete evidence across docs, sprint plans, Git, tests, saved artifacts, release hygiene, Docker, public issue setup validation, and live calibration. `in_progress_with_blockers` means delivery has evidence-backed progress but still has blocker-class gaps.

Project status:

```bash
PYTHONPATH=src python3 -m patchsmith.cli project-status \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/project_status.md \
  --json-output artifacts/experiments/project_status.json \
  --json
```

The project-status report is the concise briefing surface for progress percentage, delivery percentage, quality gate, launch blockers, Docker smoke, live calibration, adapter evidence, release hygiene, and saved-evidence counts. It summarizes saved artifacts and includes a 24-hour evidence-freshness table for each upstream JSON source; rerun the underlying gates when evidence is stale, undated, or missing.

Environment readiness:

```bash
PYTHONPATH=src python3 -m patchsmith.cli environment-readiness \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/environment_readiness.md \
  --json-output artifacts/experiments/environment_readiness.json \
  --json
```

The environment-readiness report consolidates saved Docker smoke evidence with host Docker hints, current OpenAI credential/package readiness, optional DeepAgents package importability, saved adapter evidence, and remediation commands. It does not execute Docker smoke or call live model providers.

Evidence refresh:

```bash
PYTHONPATH=src python3 -m patchsmith.cli refresh-evidence \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/evidence_refresh.md \
  --json-output artifacts/experiments/evidence_refresh.json \
  --json
```

The evidence refresh command regenerates the lightweight review/status reports in dependency order: artifact index, failure report, demo readiness, live-calibration readiness and plan, environment readiness, demo script/media, final evaluation, launch blockers, MVP progress, delivery audit, project status, and release hygiene. It skips the full quality gate, Docker smoke, and complex suite aggregation by default; pass `--include-quality-gate` only when the refresh should also run compile, pytest, and package build, pass `--include-docker-smoke` when the Docker sandbox evidence should be refreshed before launch/status reports, and pass `--complex-suite-spec evals/issue_corpora/public_issue_smoke_v1/complex_suite.template.json` when the live-agent suite gate should be regenerated from existing artifacts without new model calls. Add `min_target_alignment_rate` to the suite gate when the report should enforce that final patches stayed inside paths localized by explicit target candidates or by DeepAgents' structured failure-localization rationale for the selected patch plan. Use `max_selected_*_per_validated_task` cost/token/response caps to bound aggregate retained-attempt spend, `max_attempted_*_per_validated_task` caps to catch expensive exploratory attempts, and `max_*_task_*` caps to catch single-task cost, token, or response-count outliers even when the suite average passes. The complex summary also includes context-efficiency proxies for selected attempts: virtual files, virtual files per validated task, tokens per virtual file, responses per virtual file, and selected context-target recall/precision when saved traces include both localized targets and mounted source paths. It reports repo-instructions manifest tasks and read-first rate when DeepAgents mounted scoped AGENTS.md-style repository guidance for selected paths. Use `min_repo_instructions_manifest_rate` and `min_repo_instructions_read_first_rate` when a context-policy lane must prove those scoped instructions were mounted and read before source edits. Use `max_selected_virtual_files_per_validated_task`, `max_selected_tokens_per_virtual_file`, and `max_selected_responses_per_virtual_file` to cap context-efficiency proxies. Use `min_selected_context_target_recall` to catch missing localized target context and `min_selected_context_target_precision` to catch over-broad mounted source context. Use `min_acceptance_rubric_manifest_rate` and `min_acceptance_rubric_read_first_rate` when a verifier lane must prove the task-local acceptance rubric was mounted and read before final output. Use `min_acceptance_rubric_alignment_rate` when the lane must also prove deterministic rubric alignment: read-first verifier coverage, mounted patch target, target-aligned localization, generated patch, and no patch-quality warning.
Use `min_selected_progress_score` when a suite must prove selected attempts reached a minimum partial-progress stage even if a task is not cleanly validated; the score separates reproduced input, patch generation, target-aligned patches, quality-warning test passes, and clean validation.
Complex summaries also include `failure_class_counts` and `selected_failure_class_counts`. These deterministic artifact labels separate clean validation from quality-risk passes, preflight blocks, missing reproduction, no-patch attempts, target-misaligned patches, runtime/tool failures, retry exhaustion, and validation failures; they are triage labels, not human root-cause annotations.
They also include `harness_layer_counts` and
`selected_harness_layer_counts`, which collapse the same evidence into the
implicated harness layer: budget, model, sandbox, preflight, reproduction,
planning, context, patch quality, retry, runtime, validation, or orchestration.
Use those counts when deciding whether a failed live lane needs a context-policy
edit, retry-policy edit, sandbox/readiness fix, or validation-harness repair.
The equivalent `refresh-evidence` flags are `--complex-suite-min-acceptance-rubric-manifest-rate`, `--complex-suite-min-acceptance-rubric-read-first-rate`, and `--complex-suite-min-acceptance-rubric-alignment-rate`.
Trajectory summaries keep the legacy agent trajectory score stable and report contextual-verifier coverage as a separate rate, so older score thresholds do not move when verifier instrumentation is added. Use `min_contextual_verifier_rate`, `--min-contextual-verifier-rate`, or `--complex-suite-min-contextual-verifier-rate` when a suite must prove verifier coverage from saved traces. Use `evals/issue_corpora/public_issue_smoke_v1/complex_suite_verifier.template.json` for the next rubric-enabled live lane; keep `complex_suite.template.json` as the historical pre-rubric baseline.

Before citing a complex suite, run the spec preflight:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-complex-suite \
  --suite-spec evals/issue_corpora/public_issue_smoke_v1/complex_suite.template.json \
  --validate-only \
  --json
```

This follows the same engineering lesson behind current coding-agent systems: [SWE-agent](https://arxiv.org/abs/2405.15793) treats the agent-computer interface as a first-class design object, [Agentless](https://arxiv.org/abs/2407.01489) separates localization/repair/validation so claims stay auditable, and [OpenHands](https://arxiv.org/abs/2407.16741) emphasizes sandboxed execution plus benchmark integration. PatchSmith's suite spec preflight applies that pattern to benchmark evidence by checking the declared interface before aggregating saved traces.

Live calibration readiness:

```bash
PYTHONPATH=src python3 -m patchsmith.cli live-calibration \
  --artifacts-dir artifacts \
  --output artifacts/experiments/calibration_readiness.md \
  --json-output artifacts/experiments/calibration_readiness.json \
  --json
```

The live calibration readiness report checks whether the OpenAI SDK is importable, credentials are configured, cost-rate environment variables are present, the optional DeepAgents package is importable in the current shell, saved DeepAgents traces prove package-backed execution, and saved artifacts contain non-offline provider metadata. `calibrated` means saved live-provider rows exist; public claims must still name the tested model and scope results to the saved benchmark lane.

Live calibration execution plan:

```bash
PYTHONPATH=src python3 -m patchsmith.cli live-calibration-plan \
  --artifacts-dir artifacts \
  --output artifacts/experiments/live_calibration_plan.md \
  --json-output artifacts/experiments/live_calibration_plan.json \
  --json
```

The plan records the required single-task live OpenAI smoke, follow-up seeded-suite eval, optional package-adapter refreshes, success evidence, and claim boundaries. `blocked` means prerequisites are missing and the plan itself must not be cited as live LLM evidence.

DeepAgents package-backed adapter smoke:

```bash
python -m pip install -e ".[dev,deepagents]"

PYTHONPATH=src python3 -m patchsmith.cli eval-repair \
  --dataset evals/tasks/seeded_bugs_v1 \
  --runtime deepagents \
  --planner heuristic \
  --context-provider native_hybrid \
  --output artifacts/experiments/deepagents_package_smoke_v1 \
  --json
```

Native DeepAgents planning uses state-backed file reads, structured patch output, a patch-review subagent, and read-only DeepAgents filesystem permissions over the retrieved virtual files. The agent plans; PatchSmith applies the final bounded replacement through its own patch safety gate.

Demo script:

```bash
PYTHONPATH=src python3 -m patchsmith.cli demo-script \
  --artifacts-dir artifacts \
  --output artifacts/experiments/demo_script.md \
  --json-output artifacts/experiments/demo_script.json \
  --json
```

The demo script renders a timed run of show, narration, artifacts to open, rehearsal commands, and guardrails. Use it as the recording script for the portfolio walkthrough.

Demo media:

```bash
PYTHONPATH=src python3 -m patchsmith.cli demo-media \
  --artifacts-dir artifacts \
  --output artifacts/experiments/demo_media.md \
  --svg-output artifacts/experiments/demo_media.svg \
  --png-output artifacts/experiments/demo_media.png \
  --json-output artifacts/experiments/demo_media.json \
  --json
```

The demo media command writes a readable SVG summary, a compact PNG preview, a Markdown asset note, and JSON metadata from saved portfolio evidence.

Final evaluation:

```bash
PYTHONPATH=src python3 -m patchsmith.cli final-evaluation \
  --artifacts-dir artifacts \
  --output artifacts/experiments/final_evaluation.md \
  --json-output artifacts/experiments/final_evaluation.json \
  --json
```

The final evaluation report ties normalized metric rows, failure categories, provider metadata, launch decisions, limitations, and review artifact links into one portfolio-facing narrative. Use it as the source of truth for public claims.

Launch blockers:

```bash
PYTHONPATH=src python3 -m patchsmith.cli launch-blockers \
  --artifacts-dir artifacts \
  --output artifacts/experiments/launch_blockers.md \
  --json-output artifacts/experiments/launch_blockers.json \
  --json
```

The launch blocker backlog consolidates Docker smoke, focused public issue setup-readiness, public issue repair-readiness, live calibration, and release hygiene into a prioritized action list. It also renders each item's upstream dependencies and remediation commands so recovery steps are reviewable without reverse-engineering prior reports. Treat `blocked` as a hard stop for public release claims and `warning` as a caveat that must stay visible.

Quality gate:

```bash
PYTHONPATH=src python3 -m patchsmith.cli quality-gate \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/quality_gate.md \
  --json-output artifacts/experiments/quality_gate.json \
  --logs-dir artifacts/experiments/quality_gate_logs \
  --json
```

The quality gate runs local compile, whitespace, full pytest, and package-build checks, then writes a Markdown/JSON review artifact plus per-command stdout/stderr logs. Treat `failed` as a release stop and `passed_with_skips` as acceptable only for explicitly scoped local smoke checks, not final launch review.

Release gate:

```bash
PYTHONPATH=src python3 -m patchsmith.cli release-gate \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/release_gate.md \
  --json-output artifacts/experiments/release_gate.json \
  --logs-dir artifacts/experiments/release_gate_logs \
  --json
```

The release gate layers product-release checks on top of local verification:
full pytest, focused smoke tests, package build, top-level/agent/chat CLI help
snapshots, a sample transcript export, and saved complex benchmark result
validation when `complex_benchmark_results.json` is available. Treat skipped
benchmark validation as a visible caveat unless the release claim does not
depend on saved benchmark evidence.

Release hygiene:

```bash
PYTHONPATH=src python3 -m patchsmith.cli release-hygiene \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/release_hygiene.md \
  --json-output artifacts/experiments/release_hygiene.json \
  --json
```

The release hygiene report checks required docs, generated review artifacts, public issue reproduction-plan, failure-signal-discovery, reproduction-spec-validation, reproduction-execution, repair-readiness, and repair-attempt evidence, project-status freshness, environment readiness, demo readiness, failure visibility, live-provider caveats, Git metadata, packaging metadata, CI, demo media, architecture diagram evidence, and README caveat markers. Treat `blocked` as a hard stop for tagged/public release claims.

Package build:

```bash
python -m pip install -e ".[dev]"
python -m build --sdist --wheel --outdir dist
```

The wheel build uses `tool.hatch.build.targets.wheel.packages = ["src/patchsmith"]`. The `dev` extra includes `pytest` and `build`, matching the CI install command.

Live OpenAI planner smoke run:

```bash
export OPENAI_API_KEY=...
export PATCHSMITH_OPENAI_MODEL=<model>

PYTHONPATH=src python3 -m patchsmith.cli run \
  --repo evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo \
  --issue-file evals/tasks/seeded_bugs_v1/task_001_logic_bug/issue.md \
  --test-command "python3 -m pytest" \
  --runtime deepagents \
  --planner openai \
  --max-retries 1 \
  --context-provider native_hybrid \
  --artifacts-dir artifacts \
  --json
```

Optional cost estimation:

```bash
export PATCHSMITH_OPENAI_INPUT_COST_PER_1M=...
export PATCHSMITH_OPENAI_OUTPUT_COST_PER_1M=...
```

Without those rates, PatchSmith still records provider, response ID, and usage token counts when the provider returns them, but the estimated cost remains `n/a`.

`--max-retries` controls extra graph-level planning/edit retries after the first attempt. The runtime trace records retry decisions under `runtime.retry`; sandbox test execution still happens afterward in the workflow layer.

Optional DeepAgents context-budget experiments:

```bash
export PATCHSMITH_DEEPAGENTS_SUBAGENTS=auto
export PATCHSMITH_DEEPAGENTS_CONTEXT_MODE=span
export PATCHSMITH_DEEPAGENTS_CONTEXT_WINDOW_LINES=80
PYTHONPATH=src python -m patchsmith.cli execute-public-issue-repairs \
  --deepagents-max-context-files 2 ...
```

The default `0` preserves the full retrieved context. Positive values cap the
repository files mounted into the DeepAgents virtual filesystem while keeping
reviewed source hints, validation fixtures, and strong target-localization
signals such as symbol-qualified control points first. Treat this as an
experiment knob: validate token usage, validation status, target alignment, and
cost before adopting a capped configuration in a suite.
`PATCHSMITH_DEEPAGENTS_CONTEXT_MODE=span` is an additional opt-in compression
mode that keeps mounted repository paths stable while narrowing each source file
to a focused line window around matched symbols, runtime-cache cues, or reviewed
source hints. Use it only in saved calibration lanes until it proves lower
tokens without reducing validation or target alignment. Complex benchmark
reports expose DeepAgents virtual-file count, context-cap usage,
repair-interface manifest coverage, acceptance-rubric manifest coverage,
read-first rates, token, and cost metrics.
Public issue repair summaries expose actual model calls, tokens, and estimated
cost. Post-run live-cost, response-count, and token-count cap overages are
treated as failed claims rather than validated repairs.
Use `--max-actual-model-responses` and `--max-actual-model-tokens` when a live
benchmark lane needs hard claim limits for DeepAgents' internal call volume.
PatchSmith mounts those limits into `/.patchsmith/repair-interface.md` as a
resource budget. For native DeepAgents runs, the response cap also installs an
active model-callback tripwire that blocks the next model response once the cap
is exhausted; token caps are evaluated from recorded provider usage after each
response and remain strict post-run claim gates. `--deepagents-subagents auto`
makes budgeted first attempts prefer compact inline localization/review while
keeping feedback retries eligible for subagents. When the remaining response
budget is six or fewer, the repair interface enters budget-critical mode: it
stops requiring generic memory/skill reads, includes a compact Fast Patch Packet
for the first preferred source/symbol, and asks the model to return a structured
patch as soon as the controlling branch is identifiable.
Feedback retries write `feedback/retry_feedback_attempt_*_to_*.md` and emit
`retry_failure_class` in the `feedback_retry` trace payload. Use that field to
check whether the next attempt was guided by validation failure, safety-gate
rejection, patch-quality risk, repeated-target failure, or missing validation
instead of a blind retry. Complex benchmark summaries aggregate those payloads
as `retry_failure_class_counts` next to `retry_label_counts`.
Complex reports also include `process_quality_label_counts`,
`process_quality_flag_counts`, and `process_risky_validated_tasks`. Treat these
as trace-derived process diagnostics: a run can pass validation while still
being flagged for missing verification, blind retry behavior, repeated failed
event churn, or editing after successful verification. Use
`min_process_quality_score` and `max_process_risky_validated_tasks` in suite
specs, or the matching `--min-process-quality-score` /
`--max-process-risky-validated-tasks` CLI flags, when a benchmark lane should
fail on likely lucky-pass process risk.
`PATCHSMITH_DEEPAGENTS_SUBAGENTS=auto` is a separate efficiency experiment:
it keeps subagents for retries, reviewed source hints, validation fixtures, and
multi-context repairs, but disables them for simple single-control-point runs.
`inline` disables subagents globally and should be used only when reproducing
that ablation. Compare any non-default mode against `full` with the same task,
model, sandbox, and suite gates before using it in a benchmark claim.
Native DeepAgents runs also mount `/.patchsmith/repair-interface.md`, a compact
run interface that lists required reads, mounted source paths, subagent routing,
and the bounded output contract. They also mount
`/.patchsmith/acceptance-rubric.md`, a task-local verifier checklist generated
from issue evidence, mounted files, preferred target paths/symbols, validation
fixtures, and unsafe-patch exclusions. When the target repository has
AGENTS.md-style files at the root or ancestors of mounted context paths,
PatchSmith mounts a capped `/.patchsmith/repo-instructions.md` manifest. Treat
that file as scoped constraints for the current mounted paths, not as broad
repository context. Check
`repair_interface_manifest_path`, `repair_interface_manifest_read_first`,
`acceptance_rubric_manifest_path`, and
`acceptance_rubric_manifest_read_first`, plus
`repo_instructions_manifest_path` and
`repo_instructions_manifest_read_first`, in saved DeepAgents contract metadata
before comparing traces from different experiment slices.

## Common failures

### Clone failed

Check:

- repository URL is valid,
- repository is public,
- network is available,
- branch or commit exists.

### Dependency installation failed

Check:

- project uses supported package manager,
- dependency command is allowed,
- network policy allows install if needed,
- lockfile is compatible with environment.

### Sandbox command rejected

Check:

- command is in allowlist,
- command does not access host paths,
- command does not request network when disabled,
- command does not contain suspicious shell patterns.

### Tests timeout

Check:

- test command is too broad,
- test suite is hanging,
- timeout is too low,
- agent selected wrong command.

### Patch application failed

Check:

- patch uses correct file paths,
- file changed since context retrieval,
- patch is malformed,
- line numbers are stale.

### Retrieval misses relevant files

Check:

- issue text lacks terms from code,
- symbol index is missing,
- embeddings index was not built,
- graph expansion is disabled,
- context budget is too low.

### ctxhelm context broker unavailable

Check:

- `ctxhelm --version` works,
- the target repository has a `.git` directory or the eval runner initialized one in a temporary workspace,
- `ctxhelm doctor --repo <repo> --format json` passes,
- raw broker artifacts exist under `artifacts/runs/{run_id}/context/` or `artifacts/experiments/{experiment_id}/context_artifacts/`,
- the trace records `context_broker_call` with a fallback or error reason.

## Artifact locations

Expected local structure:

```text
artifacts/
  runs/{run_id}/
    report.md
    final.diff
    traces.jsonl
    logs/
    candidates/
  experiments/{experiment_id}/
    results.csv
    report.md
  experiments/index.md
  experiments/index.json
  experiments/index.html
  experiments/failure_report.md
  experiments/failure_report.json
  experiments/demo_readiness.md
  experiments/demo_readiness.json
  experiments/calibration_readiness.md
  experiments/calibration_readiness.json
  experiments/demo_script.md
  experiments/demo_script.json
  experiments/demo_media.md
  experiments/demo_media.json
  experiments/demo_media.svg
  experiments/demo_media.png
  experiments/quality_gate.md
  experiments/quality_gate.json
  experiments/quality_gate_logs/
  experiments/project_status.md
  experiments/project_status.json
  experiments/evidence_refresh.md
  experiments/evidence_refresh.json
  experiments/final_evaluation.md
  experiments/final_evaluation.json
  experiments/release_hygiene.md
  experiments/release_hygiene.json
  experiments/run-details/{run_id}.html
```

## Incident response for unsafe behavior

If the system attempts unsafe behavior:

1. stop the run,
2. preserve run artifacts,
3. inspect command request and trace,
4. update command policy or path validation,
5. add a regression safety test,
6. update `docs/06_safety_and_sandboxing.md`,
7. record risk update in `docs/14_risk_register.md`.

## Before public demo

Run:

- unit tests,
- sandbox safety tests,
- one seeded eval run,
- demo issue run,
- artifact index and failure report regeneration,
- demo readiness report regeneration,
- demo script regeneration,
- demo media regeneration,
- final evaluation report regeneration,
- quality-gate regeneration,
- project-status regeneration,
- evidence-refresh regeneration,
- delivery audit regeneration,
- launch blocker backlog regeneration,
- live calibration plan regeneration,
- focused public issue setup-execution regeneration,
- focused public issue setup-validation regeneration,
- public issue reproduction-plan regeneration,
- public issue failure-signal discovery regeneration,
- public issue reproduction-spec validation regeneration,
- public issue reproduction-execution regeneration,
- public issue repair-readiness regeneration,
- public issue repair-attempt regeneration,
- release hygiene report regeneration,
- README quickstart validation,
- final report review.

## Debugging principle

Every failure should become one of:

- a test,
- a metric,
- a trace event,
- a documented limitation,
- a cut feature.
