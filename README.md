# PatchSmith Research Documentation

PatchSmith Research is a production-grade AI software-maintenance agent and research platform. It converts GitHub issues into tested patch diffs while measuring the effect of agent scaffold design, code retrieval, sandbox feedback, test-time patch search, and self-improving skills.

This documentation package is designed to be used as the project foundation. It is intentionally lean: each document has an explicit purpose, and every major engineering decision should map to one of these files.

## Document map

| Area | File | Purpose |
|---|---|---|
| Direction | `docs/00_project_charter.md` | Defines vision, scope, success criteria, and non-goals |
| Product | `docs/01_product_requirements.md` | Defines user flows, MVP, and product requirements |
| Research | `docs/02_research_plan.md` | Defines research thesis, questions, experiments, and metrics |
| Architecture | `docs/03_architecture.md` | Defines system components and major data flows |
| Technical design | `docs/04_technical_design.md` | Defines subsystem-level implementation approach |
| Evaluation | `docs/05_evaluation_plan.md` | Defines benchmarks, metrics, ablations, and reporting |
| Safety | `docs/06_safety_and_sandboxing.md` | Defines sandboxing, threat model, and human approval gates |
| Data | `docs/07_data_model.md` | Defines core entities and database schema direction |
| Execution | `docs/08_engineering_playbook.md` | Defines lean workflow, branching, reviews, and done criteria |
| Roadmap | `docs/09_roadmap.md` | Defines implementation milestones |
| Quality | `docs/10_testing_strategy.md` | Defines test layers and quality gates |
| Observability | `docs/11_observability_plan.md` | Defines tracing, metrics, logs, and run reporting |
| Portfolio | `docs/12_release_and_portfolio_plan.md` | Defines demo, README, blog posts, and recruiter-facing assets |
| Shared language | `docs/13_glossary.md` | Defines project terminology |
| Risk | `docs/14_risk_register.md` | Tracks technical, safety, cost, and scope risks |
| Operations | `docs/15_runbook.md` | Defines local operations and troubleshooting |
| Integration | `docs/16_ctxhelm_integration_plan.md` | Defines ctxhelm context-broker integration, adapter boundaries, eval lanes, and safety controls |
| Sprint planning | `docs/17_sprint_plans.md` | Decomposes requirements and roadmap milestones into sprint plans |
| Delivery process | `docs/18_delivery_process.md` | Defines execution gates, review process, and evidence standards |

## Architecture Decision Records

Architecture decisions live in `adr/`:

- `adr/0001-use-langgraph-as-primary-runtime.md`
- `adr/0002-use-docker-sandbox-for-execution.md`
- `adr/0003-frameworks-behind-runtime-adapters.md`
- `adr/0004-use-code-context-graph-for-retrieval.md`
- `adr/0005-use-multi-candidate-patch-search-as-research-mode.md`
- `adr/0006-use-ctxhelm-as-context-broker-adapter.md`

## Experiment documents

Research experiment plans live in `experiments/`:

- `experiments/0001_retrieval_ablation.md`
- `experiments/0002_scaffold_comparison.md`
- `experiments/0003_patch_search_ablation.md`
- `experiments/0004_memory_ablation.md`
- `experiments/0005_dspy_prompt_optimization.md`
- `experiments/0006_ctxhelm_context_broker_ablation.md`

## Templates

Reusable templates live in `templates/`:

- `templates/adr_template.md`
- `templates/experiment_template.md`
- `templates/run_report_template.md`
- `templates/failure_analysis_template.md`
- `templates/eval_table_schema.csv`

## Recommended workflow

Use this loop:

```text
Document a decision -> build one vertical slice -> evaluate -> record result -> adjust roadmap
```

The project should not add a framework, model, benchmark, or architectural component unless it supports one of these outcomes:

1. improves the user-facing issue-to-patch flow,
2. improves measurable evaluation quality,
3. improves safety or debuggability,
4. improves portfolio clarity.

## First implementation target

The first target is not the full research system. The first target is a narrow but complete vertical slice:

```text
GitHub issue input -> repo clone -> ctxhelm CLI context plan or native fallback -> LangGraph repair loop -> Docker test run -> patch diff report
```

After that baseline works, add research features one at a time.

## ctxhelm integration stance

PatchSmith should use `ctxhelm` as a pluggable context broker, not as a replacement for the core agent system. The MVP can lean on `ctxhelm` for task-conditioned target files, related tests, validation hints, and context packs while PatchSmith owns orchestration, editing, sandboxed execution, patch search, evaluation, and reporting.

Default path:

```text
ctxhelm CLI adapter first -> MCP adapter second -> ctxhelm/native/graph retrieval ablations third
```

## Current implementation status

The repository now includes a runnable Python scaffold for the first half of the Milestone 1 loop:

```text
issue input -> repo copy/clone -> context broker -> file index -> retrieval metrics -> command policy -> test run -> trace/report artifacts
```

Deterministic patch generation is wired for seeded smoke tasks. The current runtimes are `agentless`, `heuristic`, `langgraph`, `deepagents`, and `openai_agents`; LangGraph supports planner selection with `heuristic`, `fake_model`, and `openai`, while the DeepAgents and OpenAI Agents SDK adapters run in offline compatibility mode unless their optional extras are installed. The `fake_model` planner exercises the prompt/JSON model-backed planning seam offline, validates that model output targets retrieved repo-relative paths, and keeps local evals credential-free. The `openai` planner uses the OpenAI Responses API only when credentials are configured. The context layer supports native keyword retrieval, native hybrid retrieval, native graph retrieval, and a ctxhelm CLI broker. Test execution defaults to the local command-policy sandbox for developer speed, and `--sandbox-mode docker` selects the Docker runner for stronger process and environment isolation. Saved experiment and run artifacts can be summarized with a static artifact index for demo and review.

## Quickstart

Run the test suite:

```bash
python3 -m pytest
```

Run the seeded smoke task:

```bash
PYTHONPATH=src python3 -m patchsmith.cli run \
  --repo tests/fixtures/simple_calc_bug/repo \
  --issue-file tests/fixtures/simple_calc_bug/issue.md \
  --test-command "python3 -m pytest" \
  --artifacts-dir artifacts \
  --json
```

Expected result:

- retrieved source file: `src/simple_calc.py`,
- sandbox command: `python3 -m pytest`,
- test result: one failing seeded bug test,
- artifacts: `artifacts/runs/{run_id}/report.md`, `traces.jsonl`, and `final.diff`.

Use Docker isolation when the daemon and task image are available:

```bash
docker build -f docker/seeded-smoke.Dockerfile -t patchsmith-seeded-smoke:py312 .

PYTHONPATH=src python3 -m patchsmith.cli run \
  --repo evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo \
  --issue-file evals/tasks/seeded_bugs_v1/task_001_logic_bug/issue.md \
  --test-command "python3 -m pytest" \
  --runtime heuristic \
  --context-provider native_hybrid \
  --sandbox-mode docker \
  --sandbox-image patchsmith-seeded-smoke:py312 \
  --artifacts-dir artifacts \
  --json
```

Docker mode runs the policy-checked command inside a per-run container with implicit image pulls disabled, network disabled, dropped capabilities, resource limits, a mounted `/workspace`, and a sanitized host environment. The selected sandbox mode is recorded in each run trace. Use an image that already contains task dependencies. The provided `patchsmith-seeded-smoke:py312` image includes current `pip`, `pytest`, and `git` so seeded Docker smoke and focused setup installs can run dependency-group setup without falling back to an unbuilt base image.

Generate the Docker smoke/preflight report:

```bash
PYTHONPATH=src python3 -m patchsmith.cli docker-smoke \
  --project-root . \
  --artifacts-dir artifacts \
  --image patchsmith-seeded-smoke:py312 \
  --output artifacts/experiments/docker_smoke.md \
  --json-output artifacts/experiments/docker_smoke.json \
  --json
```

The report records Docker daemon availability, local smoke-image availability, the seeded Docker test run when available, Docker-related environment/socket diagnostics, host-side Docker Desktop/Colima hints, and remediation commands. If the daemon is unavailable, it records `not_available` evidence instead of silently skipping the gate.

Run a deterministic patch smoke task:

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

Expected result:

- patch generation: `patch_generated`,
- final diff changes `return left - right` to `return left + right`,
- test exit code: `0`.

The default context provider is native keyword retrieval. `native_hybrid` adds Python symbol matching, source-over-test ranking, direct path hints, and Python traceback path/symbol hints. `native_graph` adds a Python Code Context Graph v0 with file, symbol, import, and test/source edges. To use the ctxhelm adapter on a Git-backed repository:

```bash
PYTHONPATH=src python3 -m patchsmith.cli run \
  --repo /path/to/git/repo \
  --issue-file /path/to/issue.md \
  --test-command "python3 -m pytest" \
  --context-provider ctxhelm_cli \
  --artifacts-dir artifacts \
  --json
```

`ctxhelm_cli` records `ctxhelm doctor` and `ctxhelm inspector export` artifacts under `artifacts/runs/{run_id}/context/`. If ctxhelm is unavailable or cannot produce usable source targets, `auto` mode falls back to native keyword retrieval and records the fallback in the trace.

Validate the seeded dataset:

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-dataset \
  --dataset evals/tasks/seeded_bugs_v1 \
  --output artifacts/experiments/seeded_dataset_validation_v1 \
  --json
```

Expected artifacts:

- `artifacts/experiments/seeded_dataset_validation_v1/validation_report.md`,
- `artifacts/experiments/seeded_dataset_validation_v1/validation_results.csv`,
- `artifacts/experiments/seeded_dataset_validation_v1/validation_results.json`,
- `artifacts/experiments/seeded_dataset_validation_v1/validation_summary.json`.

Run the seeded retrieval evaluation:

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

Expected artifacts:

- `artifacts/experiments/retrieval_eval_v1/report.md`,
- `artifacts/experiments/retrieval_eval_v1/results.csv`,
- `artifacts/experiments/retrieval_eval_v1/results.json`,
- `artifacts/experiments/retrieval_eval_v1/summary.json`.

Run the graph-specific retrieval stress evaluation:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-retrieval \
  --dataset evals/tasks/graph_retrieval_v1 \
  --context-provider native \
  --context-provider native_hybrid \
  --context-provider native_graph \
  --output artifacts/experiments/graph_retrieval_eval_v1 \
  --json
```

This retrieval-only dataset checks whether `native_graph` can expand from failing test paths to imported source files. The latest run has `native_graph` at 1.00 top-1/top-3/top-5 and `native_hybrid` at 0.00 on the three graph-specific tasks.

Validate the public issue corpus:

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-issue-corpus \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The corpus report validates curated public GitHub issue candidates for the next external evaluation lane. It proves task-breadth planning evidence, not solved real-world repair quality.

Preflight the public issue repositories:

```bash
PYTHONPATH=src python3 -m patchsmith.cli preflight-issue-corpus \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The preflight report checks repository reachability and records current default branch and HEAD metadata with `git ls-remote`. It does not clone source or run repairs.

Preview public issue context retrieval:

```bash
PYTHONPATH=src python3 -m patchsmith.cli preview-issue-corpus-context \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --context-provider native_hybrid \
  --top-k 5 \
  --json
```

The context preview clones/indexes the reachable public repositories and records source-free retrieved-file summaries. It proves clone/index/retrieval plumbing for external issue candidates, not reproduction, patch generation, or test success.

Materialize public issue task manifests:

```bash
PYTHONPATH=src python3 -m patchsmith.cli materialize-issue-corpus-tasks \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The materialization step writes per-issue task manifests, issue files, and runbooks from the context-preview evidence. The manifests are source-free setup artifacts for external evaluation; they are not solved-run evidence.

Validate materialized public issue tasks:

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-materialized-issue-tasks \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The validation gate checks manifest shape, source-free context summaries, task files, local repository snapshots, and suggested run commands before the manifests are used as external-evaluation setup evidence.

Check materialized task run readiness:

```bash
PYTHONPATH=src python3 -m patchsmith.cli check-materialized-run-readiness \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The readiness report checks policy allowlist status and public-repo execution risk without running tests. Current public issue tasks are policy-runnable but warning-classified because they use full pytest suites on medium or large repositories.

Plan focused public issue tests:

```bash
PYTHONPATH=src python3 -m patchsmith.cli plan-materialized-focused-tests \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --max-paths 2 \
  --json
```

The focused test plan derives narrower pytest commands from retrieved test-like files and checks them against the command policy. Current public issue tasks have three planned focused commands, zero fallbacks, and zero blocked commands.

Run focused public issue tests:

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

The focused test run executes only the planned scoped pytest commands and saves per-task stdout/stderr logs. Current public issue evidence uses the Docker setup image with explicit bridge networking because the requests upstream suite exercises local service fixtures and network timeout behavior. Treat passing focused commands as runnable-validation evidence, not PatchSmith repair quality.

Diagnose focused public issue test failures:

```bash
PYTHONPATH=src python3 -m patchsmith.cli diagnose-focused-test-runs \
  --results artifacts/experiments/public_issue_corpus_v1/focused_test_run_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The diagnosis report classifies saved focused-run logs without executing repository code. Current post-setup diagnosis reports three `focused_test_passed` tasks and no dependency, environment, timeout, blocked, or unknown failures.

Plan focused public issue test setup:

```bash
PYTHONPATH=src python3 -m patchsmith.cli plan-focused-test-setups \
  --diagnosis artifacts/experiments/public_issue_corpus_v1/focused_test_diagnosis_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The setup plan converts diagnosis categories into sandbox-only setup profiles and validation commands. Saved setup evidence preserves the remediation recipe used to prepare the current public issue snapshots: one dependency setup, two environment fixture setups, and disposable Docker execution before public issue repair attempts.

Check focused public issue setup readiness:

```bash
PYTHONPATH=src python3 -m patchsmith.cli check-focused-test-setup-readiness \
  --setup-plan artifacts/experiments/public_issue_corpus_v1/focused_test_setup_plan_results.json \
  --docker-smoke artifacts/experiments/docker_smoke.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The setup-readiness report gates setup execution on repository snapshots and Docker smoke evidence. Current readiness has zero blocked tasks and three warning-class tasks because each public issue setup requires reviewed networked Docker execution.

Dry-run focused public issue setup execution:

```bash
PYTHONPATH=src python3 -m patchsmith.cli execute-focused-test-setups \
  --readiness artifacts/experiments/public_issue_corpus_v1/focused_test_setup_readiness_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The setup-execution report records readiness-gated dry-run or explicit execution evidence for setup commands. It defaults to dry-run; use `--execute` only after setup-readiness is no longer blocked and the selected sandbox is approved. Current setup execution has completed all three setup tasks in Docker with explicit warning, dependency-install, and bridge-network approval.

Dependency installation remains blocked by the default command policy. To dry-run or execute the narrow editable-install setup policy, use Docker mode with explicit opt-in flags such as `--allow-dependency-installs --sandbox-network bridge`; focused setup execution and validation default to `patchsmith-seeded-smoke:py312`. Use `--execute` only after reviewing the dry-run report.

Dry-run focused public issue setup validation:

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-focused-test-setups \
  --setup-execution artifacts/experiments/public_issue_corpus_v1/focused_test_setup_execution_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The setup-validation report gates validation commands on completed setup execution. Current setup validation executes all three validation commands successfully after the focused setup recipes run in Docker. This proves the post-setup validation commands can run; it is still setup/reproduction plumbing evidence, not repair-quality evidence.

Plan public issue reproduction checks:

```bash
PYTHONPATH=src python3 -m patchsmith.cli plan-public-issue-reproductions \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --focused-plan artifacts/experiments/public_issue_corpus_v1/focused_test_plan_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The reproduction-plan report records candidate commands before public issue repair attempts and marks tasks that still need explicit expected-failure signals. Add `--reproduction-specs <reviewed-specs.json>` when reviewed criteria are available; the specs file accepts `task_id`, optional `command`, and `expected_failure_signals`, and the corpus includes `evals/issue_corpora/public_issue_smoke_v1/reproduction_specs.template.json` as the source-controlled authoring template. Current public issue reproduction planning is warning-class: all three tasks have candidate commands, but all three still need manual failing-signal specs before reproduction can be claimed.

Dry-run or execute public issue reproduction checks:

```bash
PYTHONPATH=src python3 -m patchsmith.cli execute-public-issue-reproductions \
  --plan artifacts/experiments/public_issue_corpus_v1/public_issue_reproduction_plan_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The reproduction-execution report is dry-run by default. It blocks rows without explicit expected-failure signals, and only `--execute` can save stdout/stderr evidence. A task counts as `reproduced` only when the command exits nonzero and all configured expected-failure signals appear in the saved logs.

Check public issue repair-attempt readiness:

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

The repair-readiness report joins focused-run, diagnosis, setup-validation, reproduction-execution, and materialized-task command evidence before any public issue repair attempt. Current public issue repair readiness is warning-class: all three tasks have runnable validation and saved PatchSmith repair commands, but all three lack saved failing reproduction evidence, so repair-quality claims remain unproven.

Dry-run or execute public issue repair attempts:

```bash
PYTHONPATH=src python3 -m patchsmith.cli execute-public-issue-repairs \
  --readiness artifacts/experiments/public_issue_corpus_v1/public_issue_repair_readiness_results.json \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The repair-attempt report is dry-run by default and blocks rows without reproduced failing evidence. Use `--execute` only after reproduction is proven and readiness warnings are explicitly accepted.

Run the seeded repair evaluation:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-repair \
  --dataset evals/tasks/seeded_bugs_v1 \
  --runtime heuristic \
  --context-provider native_hybrid \
  --output artifacts/experiments/repair_eval_v1 \
  --json
```

Expected artifacts:

- `artifacts/experiments/repair_eval_v1/repair_report.md`,
- `artifacts/experiments/repair_eval_v1/repair_results.csv`,
- `artifacts/experiments/repair_eval_v1/repair_results.json`,
- `artifacts/experiments/repair_eval_v1/repair_summary.json`.

Run the LangGraph offline model-planner contract evaluation:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-repair \
  --dataset evals/tasks/seeded_bugs_v1 \
  --runtime langgraph \
  --planner fake_model \
  --context-provider native_hybrid \
  --output artifacts/experiments/langgraph_model_repair_eval_v1 \
  --json
```

Expected result on the current seeded suite:

- planner: `fake_model`,
- model provider: `offline_fake_model`,
- patch generated rate: `1.00`,
- targeted test pass rate: `1.00`,
- model cost: `$0.00` because this is an offline model double, not a live provider.

Run the scaffold comparison:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-scaffold \
  --dataset evals/tasks/seeded_bugs_v1 \
  --variant agentless \
  --variant heuristic \
  --variant langgraph \
  --variant langgraph_fake_model \
  --variant deepagents \
  --variant openai_agents \
  --context-provider native_hybrid \
  --output artifacts/experiments/scaffold_comparison_v1 \
  --json
```

Latest comparison evidence is saved in `artifacts/experiments/scaffold_comparison_v1/scaffold_report.md`.

Run the OpenAI Agents SDK adapter smoke:

```bash
python -m pip install -e ".[dev,openai-agents]"

PYTHONPATH=src python3 -m patchsmith.cli eval-repair \
  --dataset evals/tasks/seeded_bugs_v1 \
  --runtime openai_agents \
  --planner heuristic \
  --context-provider native_hybrid \
  --output artifacts/experiments/openai_agents_adapter_smoke_v1 \
  --json
```

The adapter imports the optional `openai-agents` package as `agents` when installed, but the saved local smoke is adapter-contract evidence, not live OpenAI Agents model quality.

Run the patch-search ablation:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-patch-search \
  --dataset evals/tasks/seeded_bugs_v1 \
  --candidate-count 1 \
  --candidate-count 3 \
  --context-provider native_hybrid \
  --output artifacts/experiments/patch_search_eval_v1 \
  --json
```

Latest patch-search evidence is saved in `artifacts/experiments/patch_search_eval_v1/patch_search_report.md`.

Generate the local artifact index:

```bash
PYTHONPATH=src python3 -m patchsmith.cli index-artifacts \
  --artifacts-dir artifacts \
  --output artifacts/experiments/index.md \
  --json-output artifacts/experiments/index.json \
  --html-output artifacts/experiments/index.html \
  --run-detail-output-dir artifacts/experiments/run-details \
  --json
```

Latest observability evidence is saved in `artifacts/experiments/index.md`, `artifacts/experiments/index.json`, the static dashboard `artifacts/experiments/index.html`, and per-run detail pages under `artifacts/experiments/run-details/`. The Markdown and HTML outputs show normalized research metrics, the latest 25 saved runs, and links to reports, traces, diffs, stdout, stderr, and generated detail pages. The JSON output includes the full discovered run list and normalized metric rows for downstream UI adapters.

Generate the failure review report:

```bash
PYTHONPATH=src python3 -m patchsmith.cli inspect-failures \
  --artifacts-dir artifacts \
  --output artifacts/experiments/failure_report.md \
  --json-output artifacts/experiments/failure_report.json \
  --max-runs 0 \
  --json
```

The failure report scans saved run traces, groups repair-outcome categories such as `no_patch_generated`, counts failed sandbox/runtime events, and links back to report, trace, and diff artifacts. It is meant for demo review and failure analysis, not as a substitute for rerunning tests.

Generate the demo readiness report:

```bash
PYTHONPATH=src python3 -m patchsmith.cli demo-readiness \
  --artifacts-dir artifacts \
  --output artifacts/experiments/demo_readiness.md \
  --json-output artifacts/experiments/demo_readiness.json \
  --json
```

Latest readiness evidence is saved in `artifacts/experiments/demo_readiness.md` and `artifacts/experiments/demo_readiness.json`. Current status is `ready_with_caveats`: saved offline evaluation and failure-analysis evidence is demo-ready, but live LLM calibration is not present unless a non-offline model provider appears in saved artifacts.

Generate the MVP progress report:

```bash
PYTHONPATH=src python3 -m patchsmith.cli mvp-progress \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/mvp_progress.md \
  --json-output artifacts/experiments/mvp_progress.json \
  --json
```

Latest MVP progress evidence is saved in `artifacts/experiments/mvp_progress.md` and `artifacts/experiments/mvp_progress.json`. Current status is `ready_with_caveats` at `96.7%`: 28 checklist items pass, two remain warnings, and no item is blocked or missing. The remaining warnings are intentionally evidence-based: live LLM calibration and Docker daemon/image smoke are still not proven.

Generate the consolidated project status report:

```bash
PYTHONPATH=src python3 -m patchsmith.cli project-status \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/project_status.md \
  --json-output artifacts/experiments/project_status.json \
  --json
```

Latest project-status evidence is saved in `artifacts/experiments/project_status.md` and `artifacts/experiments/project_status.json`. It summarizes MVP progress, delivery audit, quality gate, launch blockers, Docker smoke, live calibration, adapter evidence, release hygiene, and saved experiment counts from existing artifacts without rerunning those checks. It also records per-source evidence freshness against a 24-hour threshold so stale or undated status inputs remain visible before sprint review.

Generate the environment readiness report:

```bash
PYTHONPATH=src python3 -m patchsmith.cli environment-readiness \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/environment_readiness.md \
  --json-output artifacts/experiments/environment_readiness.json \
  --json
```

Latest environment readiness evidence is saved in `artifacts/experiments/environment_readiness.md` and `artifacts/experiments/environment_readiness.json`. It consolidates saved Docker smoke evidence with host Docker hints, current OpenAI credential/package readiness, optional DeepAgents/OpenAI Agents package importability, and saved adapter/live-provider evidence without executing Docker smoke or calling live model providers.

Refresh the lightweight review evidence bundle:

```bash
PYTHONPATH=src python3 -m patchsmith.cli refresh-evidence \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/evidence_refresh.md \
  --json-output artifacts/experiments/evidence_refresh.json \
  --json
```

Latest evidence-refresh output is saved in `artifacts/experiments/evidence_refresh.md` and `artifacts/experiments/evidence_refresh.json`. It regenerates the lightweight review/status artifacts in dependency order and records each step, duration, and output path, including the environment readiness report. It skips the full quality gate and Docker smoke by default; pass `--include-quality-gate` when you want the refresh to run compile, tests, and package build, and pass `--include-docker-smoke` when Docker sandbox evidence should be refreshed before launch/status reports.

Run the executable quality gate:

```bash
PYTHONPATH=src python3 -m patchsmith.cli quality-gate \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/quality_gate.md \
  --json-output artifacts/experiments/quality_gate.json \
  --logs-dir artifacts/experiments/quality_gate_logs \
  --json
```

Latest quality-gate evidence is saved in `artifacts/experiments/quality_gate.md`, `artifacts/experiments/quality_gate.json`, and per-command logs under `artifacts/experiments/quality_gate_logs/`. The gate executes compileall, whitespace diff checks, full pytest, and package build unless specific skip flags are used.

Generate the delivery audit:

```bash
PYTHONPATH=src python3 -m patchsmith.cli delivery-audit \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/delivery_audit.md \
  --json-output artifacts/experiments/delivery_audit.json \
  --json
```

Latest delivery-audit evidence is saved in `artifacts/experiments/delivery_audit.md` and `artifacts/experiments/delivery_audit.json`. It maps the original planning/development objective to concrete evidence. Docker smoke and public issue setup validation now pass, environment readiness is warning-class, and live LLM calibration remains the hard blocker until credentials and a bounded live-provider run exist. Quality-gate evidence is included as an executable verification item.

Generate the live calibration readiness report:

```bash
PYTHONPATH=src python3 -m patchsmith.cli live-calibration \
  --artifacts-dir artifacts \
  --output artifacts/experiments/calibration_readiness.md \
  --json-output artifacts/experiments/calibration_readiness.json \
  --json
```

Latest live calibration readiness evidence is saved in `artifacts/experiments/calibration_readiness.md` and `artifacts/experiments/calibration_readiness.json`. Current status is `not_configured`: the OpenAI SDK is importable, but `OPENAI_API_KEY` is not set and saved model-provider evidence is still offline-only. DeepAgents now has 10 saved package-backed adapter smoke runs, while the current shell still does not import `deepagents`. OpenAI Agents SDK now has 10 saved package-backed adapter smoke runs, while the current shell still does not import `agents`.

Generate the live calibration execution plan:

```bash
PYTHONPATH=src python3 -m patchsmith.cli live-calibration-plan \
  --artifacts-dir artifacts \
  --output artifacts/experiments/live_calibration_plan.md \
  --json-output artifacts/experiments/live_calibration_plan.json \
  --json
```

Latest calibration-plan evidence is saved in `artifacts/experiments/live_calibration_plan.md` and `artifacts/experiments/live_calibration_plan.json`. Current plan status is `blocked` until `OPENAI_API_KEY` is configured; the plan still records the exact single-task live smoke, follow-up seeded-suite eval, optional adapter refresh commands, and claim boundaries.

Run DeepAgents with the optional package installed:

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

Generate the timed demo script:

```bash
PYTHONPATH=src python3 -m patchsmith.cli demo-script \
  --artifacts-dir artifacts \
  --output artifacts/experiments/demo_script.md \
  --json-output artifacts/experiments/demo_script.json \
  --json
```

Latest script evidence is saved in `artifacts/experiments/demo_script.md` and `artifacts/experiments/demo_script.json`. The current generated script has six sections and targets a 3 minute 10 second walkthrough.

Generate demo media assets:

```bash
PYTHONPATH=src python3 -m patchsmith.cli demo-media \
  --artifacts-dir artifacts \
  --output artifacts/experiments/demo_media.md \
  --svg-output artifacts/experiments/demo_media.svg \
  --png-output artifacts/experiments/demo_media.png \
  --json-output artifacts/experiments/demo_media.json \
  --json
```

Latest demo media evidence is saved in `artifacts/experiments/demo_media.md`, `artifacts/experiments/demo_media.svg`, `artifacts/experiments/demo_media.png`, and `artifacts/experiments/demo_media.json`.

Generate the final evaluation narrative:

```bash
PYTHONPATH=src python3 -m patchsmith.cli final-evaluation \
  --artifacts-dir artifacts \
  --output artifacts/experiments/final_evaluation.md \
  --json-output artifacts/experiments/final_evaluation.json \
  --json
```

Latest final evaluation evidence is saved in `artifacts/experiments/final_evaluation.md` and `artifacts/experiments/final_evaluation.json`. It summarizes retrieval, repair/scaffold, patch-search, failure, provider, and limitation evidence into one reviewer-facing report.

Generate the launch blocker backlog:

```bash
PYTHONPATH=src python3 -m patchsmith.cli launch-blockers \
  --artifacts-dir artifacts \
  --output artifacts/experiments/launch_blockers.md \
  --json-output artifacts/experiments/launch_blockers.json \
  --json
```

Latest launch blocker evidence is saved in `artifacts/experiments/launch_blockers.md` and `artifacts/experiments/launch_blockers.json`. Current status is `ready_with_warnings`: Docker smoke is ready, focused public issue setup-readiness is warning-class rather than blocked, setup validation passes after the approved Docker setup recipe, public repair-readiness is warning-class because failing reproduction evidence is not saved, and live-provider calibration plus release hygiene remain caveats. Public issue setup validation and repair readiness remain prerequisites rather than public issue repair-quality evidence.

Generate the release hygiene report:

```bash
PYTHONPATH=src python3 -m patchsmith.cli release-hygiene \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/release_hygiene.md \
  --json-output artifacts/experiments/release_hygiene.json \
  --json
```

Latest release hygiene evidence is saved in `artifacts/experiments/release_hygiene.md` and `artifacts/experiments/release_hygiene.json`. Current status is `ready_with_warnings`: CI, packaging metadata, architecture-diagram, demo-media, quality-gate, project-status, project-status freshness, calibration-readiness, live-calibration plan, delivery audit, launch-blocker, public issue corpus/context-preview/materialized-task validation/readiness/focused-test plan/run/diagnosis/setup-plan/setup-readiness/setup-execution/setup-validation/reproduction-plan/reproduction-execution/repair-readiness/repair-attempt evidence, and local Git metadata checks pass, while unproven live LLM calibration and warning-class environment/setup/reproduction evidence must stay visible in release claims.

Build package artifacts:

```bash
python -m pip install -e ".[dev]"
python -m build --sdist --wheel --outdir dist
```

Run LangGraph with a live OpenAI planner:

```bash
export OPENAI_API_KEY=...
export PATCHSMITH_OPENAI_MODEL=<model>

PYTHONPATH=src python3 -m patchsmith.cli run \
  --repo evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo \
  --issue-file evals/tasks/seeded_bugs_v1/task_001_logic_bug/issue.md \
  --test-command "python3 -m pytest" \
  --runtime langgraph \
  --planner openai \
  --context-provider native_hybrid \
  --artifacts-dir artifacts \
  --json
```

Optional cost fields:

- `PATCHSMITH_OPENAI_INPUT_COST_PER_1M`,
- `PATCHSMITH_OPENAI_OUTPUT_COST_PER_1M`.

When those rates are set, reports estimate model cost from provider token usage. Without rates, reports still record provider, response ID, and token counts when the API returns usage.

## Next engineering wedges

The context broker boundary, retrieval eval runner, repair eval runner, scaffold comparison runner, patch-search evaluator, public issue corpus validation/preflight/context preview/task materialization, validation, run-readiness, focused-test planning, focused-test execution, focused-test diagnosis, focused-test setup planning, setup-readiness checks, setup-execution dry-run and executed Docker evidence, passing setup-validation execution evidence, public issue reproduction planning, public issue reproduction execution gating, public issue repair-readiness gating, public issue repair-attempt gating, static artifact index/dashboard with normalized metrics and generated run-detail trace pages, failure review report, demo readiness report, executable quality-gate report, consolidated project-status report with evidence freshness, environment readiness report, evidence-refresh orchestration report with opt-in Docker smoke refresh, live calibration readiness report and execution plan, delivery audit, launch blocker backlog with dependency-chain remediation commands, generated demo script, final evaluation report, release hygiene report, deterministic heuristic runtime, LangGraph orchestration runtime, DeepAgents adapter compatibility mode plus package-backed smoke evidence, OpenAI Agents SDK adapter compatibility mode, offline model-planner seam, credential-gated OpenAI Responses client, and Python Code Context Graph v0 now exist. The current seeded suite has 10 tasks and compares `native`, `native_hybrid`, `native_graph`, and `ctxhelm_cli` for retrieval, including aggregate context packing metadata. Scaffold comparison now includes trace complexity and debuggability metrics. The next useful development step is resolving the live-provider warning, harder patch-search tasks with model-diverse candidates, or public issue repair attempts once reproduction criteria are explicit.

The current LangGraph repair skeleton is:

```text
workflow retrieval -> triage -> plan -> edit -> analyze -> retry -> review -> workflow test -> report
```

`--max-retries` controls extra graph-level planning/edit retries after the first attempt. Keep the current report, trace, sandbox policy, and retrieval interfaces stable while deepening test-failure analysis.

## Planning docs

Start from:

- `docs/17_sprint_plans.md` for the sprint decomposition,
- `docs/18_delivery_process.md` for the delivery process,
- `docs/09_roadmap.md` for milestone gates.
