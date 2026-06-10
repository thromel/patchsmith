# Sprint Plans

## Status

Draft v0.2

## Purpose

This document decomposes the PatchSmith Research PRD, roadmap, evaluation plan, safety plan, and ctxhelm integration plan into executable sprint plans.

The project should run like a small applied research engineering program: each sprint produces a product artifact, an engineering artifact, an evaluation artifact, and a documented decision.

Latest evidence-backed MVP progress is `96.7%` with status `ready_with_caveats`: 28 checklist items pass, two are warnings, and no item is blocked or missing. The remaining warnings are live LLM calibration and Docker daemon/image smoke.

## Sprint operating model

### Cadence

- Sprint length: one to two weeks.
- Planning input: PRD, roadmap milestone, risk register, experiment plan, and previous sprint evidence.
- Sprint output: implemented code, tests, run artifacts, updated docs, and a decision.
- Review format: demo from a clean command, inspect generated artifacts, review metrics, then update backlog.

### Required sprint artifacts

Each sprint should produce:

- sprint goal,
- in-scope requirements,
- out-of-scope guardrails,
- acceptance criteria,
- verification commands,
- evidence locations,
- open risks or follow-up decisions.

### Definition of ready

A sprint item is ready when:

- the user-visible outcome is clear,
- the responsible subsystem is known,
- the safety impact is identified,
- the test or evaluation signal is defined,
- success can be proven from a command output or saved artifact.

### Definition of done

A sprint is done when:

- code is implemented for the sprint scope,
- unit or integration tests cover the changed behavior,
- generated artifacts prove the main workflow,
- docs and runbook references are current,
- risks introduced by the sprint are recorded,
- the next sprint can start without reverse-engineering the previous one.

## Requirement decomposition

| Requirement area | Source | Sprint lane | Proof artifact |
|---|---|---|---|
| Issue intake and repo snapshot | PRD F1, F2 | Sprint 1 | CLI run summary, snapshot metadata |
| File indexing and retrieval | PRD F3, F4, RQ1 | Sprints 1, 3, 4 | retrieval report, top-k recall table |
| Context broker integration | ADR 0006, docs/16 | Sprint 2 | ctxhelm/native comparison report |
| Agent runtime loop | PRD F5, RQ2 | Sprint 3 | trace with runtime nodes and patch attempt |
| Controlled edits and diffs | PRD F6 | Sprint 3 | patch candidate artifact, final diff |
| Test execution and sandbox policy | PRD F7, safety doc | Sprints 1, 3, 5 | command logs, policy rejection tests |
| Final reports and traces | PRD F8, observability plan | Every sprint | run report and trace JSONL |
| Seeded bug evaluation | Evaluation Gate 1, Gate 2 | Sprint 2 | seeded evaluation CSV and Markdown summary |
| Hybrid and graph retrieval | Roadmap M3, M4 | Sprints 5, 6 | retrieval ablation report |
| Runtime adapter comparison | Roadmap M5 | Sprint 7 | scaffold comparison report |
| Patch search | Roadmap M6, RQ3 | Sprint 8 | success@k report |
| Demo and portfolio launch | Roadmap M7, M9 | Sprints 9, 10 | demo script, screenshots, final README |

## Sprint backlog

### Sprint 0: Project Operating System

Goal:

Create the foundation for repeatable engineering and research work.

Scope:

- project charter,
- PRD,
- research plan,
- architecture and technical design,
- safety and data model docs,
- ADRs,
- experiment templates,
- sprint plan.

Acceptance criteria:

- docs describe the system scope and non-goals,
- roadmap has milestone gates,
- ADRs define adapter boundaries,
- next implementation sprint has executable tasks.

Current status:

Mostly complete. This sprint plan closes the missing sprint decomposition artifact.

### Sprint 1: Walking Skeleton

Goal:

Run a seeded issue through issue intake, repo copy or clone, indexing, native retrieval, command policy, test execution, traces, and final report.

In scope:

- CLI `run`, `index`, and `retrieve`,
- per-run artifact directory,
- repository snapshot metadata,
- basic file index,
- keyword retrieval,
- command allowlist,
- development sandbox runner,
- final Markdown report,
- one seeded bug fixture.

Out of scope:

- model-backed patch generation,
- Docker hardening,
- broad language support,
- hosted UI.

Acceptance criteria:

- `python3 -m pytest` passes,
- seeded smoke run writes `report.md`, `traces.jsonl`, `final.diff`, stdout, and stderr,
- failing seeded test output appears in the run report,
- no external write action is performed.

Current status:

Implemented as the first development slice. The default runner remains the local command-policy sandbox for fast deterministic development. An opt-in Docker runner now exists for `run`, `eval-repair`, `eval-scaffold`, and `eval-patch-search`; it disables implicit image pulls and container networking, drops capabilities, applies resource limits, mounts the task workspace at `/workspace`, and records the selected sandbox mode in traces. The `docker-smoke` command now records daemon, image, seeded-run evidence, Docker-related environment/socket diagnostics, and remediation commands. A passing live Docker daemon/image smoke is still separate evidence because Docker mode requires a reachable daemon and an image with task dependencies installed.

### Sprint 2: Context Broker and Retrieval Evaluation

Goal:

Compare native keyword retrieval and ctxhelm CLI context brokering on seeded tasks.

In scope:

- `ContextBroker` interface,
- native keyword broker,
- ctxhelm CLI broker,
- path and command normalization,
- fallback behavior,
- seeded task metadata,
- retrieval evaluation CLI,
- top-k target recall,
- related-test recall,
- source-free contract check,
- Markdown and CSV eval reports.

Out of scope:

- ctxhelm MCP adapter,
- graph retrieval,
- model patch generation.

Acceptance criteria:

- `native` and `ctxhelm_cli` lanes run on the same seeded task set,
- each task records expected touched files and expected related tests,
- each lane reports top-1, top-3, top-5 target recall,
- ctxhelm failures are counted separately from retrieval misses,
- reports include cost placeholder, latency, fallback count, and source-free violation count.

Current status:

Substantially complete for the seeded retrieval lane. The context broker boundary, ctxhelm CLI broker, seeded task metadata, retrieval metrics, and `eval-retrieval` CLI exist for 10 seeded tasks. Later sprint work added the current four retrieval lanes: `native`, `native_hybrid`, `native_graph`, and `ctxhelm_cli`. Continue to add harder tasks, but the next main sprint can move toward Sprint 3 patch-attempt runtime.

Verification commands:

```bash
python3 -m pytest
PYTHONPATH=src python3 -m patchsmith.cli eval-retrieval \
  --dataset evals/tasks/seeded_bugs_v1 \
  --context-provider native \
  --context-provider ctxhelm_cli \
  --output artifacts/experiments/retrieval_eval_v1
```

### Sprint 3: Minimal Patch Attempt Runtime

Goal:

Replace the no-op runtime with a bounded repair attempt that can produce and test a patch on simple Python seeded bugs.

In scope:

- framework-neutral patch tool interface,
- file read/search tools,
- structured edit or unified diff application,
- deterministic fake runtime for tests,
- minimal model-backed LangGraph runtime behind `AgentRuntime`,
- patch candidate artifact,
- retry limit,
- final review node.

Out of scope:

- multi-candidate patch search,
- complex dependency installation,
- private repos.

Acceptance criteria:

- one seeded bug produces a patch attempt,
- patch is applied only inside the run workspace,
- final diff is exported,
- test command is re-run after patching,
- trace includes planning, edit, test, analyze, and report events.

Current status:

Started. A deterministic `heuristic` runtime and a LangGraph orchestration runtime now run behind the `AgentRuntime` boundary, apply safe text replacements inside the run workspace, emit patch candidate metadata, export unified diffs, and pass the 10-task seeded smoke suite through `eval-repair`. LangGraph now has planner selection with `heuristic`, `fake_model`, and `openai`; `fake_model` exercises the prompt/JSON model-backed planner seam offline, validates retrieved repo-relative paths, and produces a 10-task seeded evaluation artifact. `openai` is credential-gated through the OpenAI Responses API and records token/cost metadata when available. The LangGraph trace now includes `triage`, `plan`, `edit`, `analyze`, `retry`, and `review`; sandbox `test`, post-test `analyze`, and `report` events remain in the workflow layer. Run reports now include a `Repair Analysis` section and a dynamic final verdict such as `patch_validated`. Richer model-driven test-failure analysis is still pending.

Latest verification command:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-repair \
  --dataset evals/tasks/seeded_bugs_v1 \
  --runtime langgraph \
  --planner fake_model \
  --context-provider native_hybrid \
  --output artifacts/experiments/langgraph_model_repair_eval_v1 \
  --json
```

Latest evidence:

- `artifacts/experiments/langgraph_model_repair_eval_v1/repair_report.md`,
- attempted tasks: 10,
- completed tasks: 10,
- patch generated rate: 1.00,
- targeted test pass rate: 1.00,
- average latency: 463ms,
- model provider: offline_fake_model,
- model cost: $0.00 because the planner is an offline model double.

### Sprint 4: Seeded Bug Suite v1

Goal:

Make the MVP repeatable across a controlled Python seeded bug suite.

In scope:

- 10 seeded bug tasks,
- task schema and validation,
- evaluation runner,
- metrics logger,
- baseline run report,
- failure categories.

Out of scope:

- real GitHub issue set,
- SWE-bench subset.

Acceptance criteria:

- all seeded tasks run through the same pipeline,
- task-level JSON and aggregate CSV are saved,
- infrastructure failures are distinguishable from model or retrieval failures,
- Gate 1 MVP readiness can be assessed from artifacts.

Current status:

Started. The seeded suite currently has 10 Python tasks with expected touched files and related tests. Dataset validation is now a first-class CLI gate through `validate-dataset`; it writes task-level JSON, aggregate CSV, summary JSON, and a Markdown validation report. Retrieval and repair eval runners already save per-task and aggregate artifacts, and repair reports now classify post-test outcomes with failure categories or `patch_validated`. A public issue corpus validation lane now tracks real GitHub issue candidates separately from solved seeded runs.

Latest validation command:

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-dataset \
  --dataset evals/tasks/seeded_bugs_v1 \
  --output artifacts/experiments/seeded_dataset_validation_v1 \
  --json
```

Latest evidence:

- `artifacts/experiments/seeded_dataset_validation_v1/validation_report.md`,
- task count: 10,
- valid tasks: 10,
- invalid tasks: 0,
- errors: 0,
- warnings: 0.

Public issue corpus evidence:

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-issue-corpus \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

```bash
PYTHONPATH=src python3 -m patchsmith.cli preflight-issue-corpus \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

```bash
PYTHONPATH=src python3 -m patchsmith.cli preview-issue-corpus-context \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --context-provider native_hybrid \
  --top-k 5 \
  --json
```

```bash
PYTHONPATH=src python3 -m patchsmith.cli materialize-issue-corpus-tasks \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-materialized-issue-tasks \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

```bash
PYTHONPATH=src python3 -m patchsmith.cli check-materialized-run-readiness \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

```bash
PYTHONPATH=src python3 -m patchsmith.cli plan-materialized-focused-tests \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --max-paths 2 \
  --json
```

```bash
PYTHONPATH=src python3 -m patchsmith.cli run-materialized-focused-tests \
  --plan artifacts/experiments/public_issue_corpus_v1/focused_test_plan_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --timeout-seconds 60 \
  --json
```

```bash
PYTHONPATH=src python3 -m patchsmith.cli diagnose-focused-test-runs \
  --results artifacts/experiments/public_issue_corpus_v1/focused_test_run_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

```bash
PYTHONPATH=src python3 -m patchsmith.cli plan-focused-test-setups \
  --diagnosis artifacts/experiments/public_issue_corpus_v1/focused_test_diagnosis_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

```bash
PYTHONPATH=src python3 -m patchsmith.cli check-focused-test-setup-readiness \
  --setup-plan artifacts/experiments/public_issue_corpus_v1/focused_test_setup_plan_results.json \
  --docker-smoke artifacts/experiments/docker_smoke.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

```bash
PYTHONPATH=src python3 -m patchsmith.cli execute-focused-test-setups \
  --readiness artifacts/experiments/public_issue_corpus_v1/focused_test_setup_readiness_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-focused-test-setups \
  --setup-execution artifacts/experiments/public_issue_corpus_v1/focused_test_setup_execution_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Latest expected evidence:

- `artifacts/experiments/public_issue_corpus_v1/corpus_report.md`,
- `artifacts/experiments/public_issue_corpus_v1/repo_preflight_report.md`,
- `artifacts/experiments/public_issue_corpus_v1/context_preview_report.md`,
- `artifacts/experiments/public_issue_corpus_v1/materialized_task_report.md`,
- `artifacts/experiments/public_issue_corpus_v1/materialized_task_validation_report.md`,
- `artifacts/experiments/public_issue_corpus_v1/materialized_run_readiness_report.md`,
- `artifacts/experiments/public_issue_corpus_v1/focused_test_plan_report.md`,
- `artifacts/experiments/public_issue_corpus_v1/focused_test_run_report.md`,
- `artifacts/experiments/public_issue_corpus_v1/focused_test_diagnosis_report.md`,
- `artifacts/experiments/public_issue_corpus_v1/focused_test_setup_plan_report.md`,
- `artifacts/experiments/public_issue_corpus_v1/focused_test_setup_readiness_report.md`,
- `artifacts/experiments/public_issue_corpus_v1/focused_test_setup_execution_report.md`,
- `artifacts/experiments/public_issue_corpus_v1/focused_test_setup_validation_report.md`,
- valid public issue candidates: 3,
- reachable public repositories: 2,
- context preview completed issues: 3,
- context preview source-free summaries: true,
- materialized public issue tasks: 3,
- valid materialized issue tasks: 3,
- invalid materialized issue tasks: 0,
- materialized task manifests source-free: true,
- run-readiness blocked tasks: 0,
- run-readiness warning tasks: 3,
- policy-allowed materialized test commands: 3,
- focused public issue test plans: 3,
- focused test fallbacks: 0,
- policy-allowed focused test commands: 3,
- focused public issue test runs attempted: 3,
- focused public issue test runs passed: 0,
- focused public issue test runs failed: 3,
- focused public issue diagnosis dependency issues: 1,
- focused public issue diagnosis environment issues: 2,
- focused public issue diagnosis unknown failures: 0,
- focused public issue setup plans: 3,
- focused public issue setup dependency plans: 1,
- focused public issue setup environment plans: 2,
- focused public issue setup network-required plans: 3,
- focused public issue setup-readiness ready tasks: 0,
- focused public issue setup-readiness blocked tasks: 3,
- focused public issue setup-execution blocked tasks: 3,
- focused public issue setup dependency installs: blocked by default policy unless explicitly enabled with Docker mode,
- focused public issue setup-validation blocked tasks: 3,
- invalid entries: 0,
- repositories: `psf/requests`, `pytest-dev/pytest`.

### Sprint 5: Hybrid Retrieval v0

Goal:

Improve localization beyond keyword and ctxhelm-only retrieval.

In scope:

- symbol extraction for Python,
- stack-trace and path heuristics,
- context packing metadata,
- hybrid retrieval lane,
- retrieval ablation update.

Out of scope:

- full Code Context Graph,
- embeddings as a hard dependency.

Acceptance criteria:

- `native`, `native_hybrid`, `native_graph`, and `ctxhelm_cli` are comparable on seeded tasks,
- retrieval output includes method labels and scores,
- experiment report explains wins, misses, cost, and latency.

Current status:

Mostly complete for the seeded v1 lane. `native_hybrid` now combines lexical matching, Python symbol extraction, source-over-test ranking, direct repo-relative path hints, and Python traceback frame path/symbol hints. Retrieval contexts continue to expose method labels, scores, matched terms, excerpts, and aggregate context packing metadata through the same `RetrievedContext`-based contract. The shared seeded retrieval ablation now compares `native`, `native_hybrid`, `native_graph`, and `ctxhelm_cli` on the 10-task suite.

Latest verification command:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-retrieval \
  --dataset evals/tasks/seeded_bugs_v1 \
  --context-provider native \
  --context-provider native_hybrid \
  --context-provider ctxhelm_cli \
  --output artifacts/experiments/retrieval_eval_v1 \
  --json
```

Latest evidence:

- `artifacts/experiments/retrieval_eval_v1/report.md`,
- `native`: top-1 0.80, top-3 1.00, top-5 1.00, average packed context 37 approximate tokens, average latency 4ms,
- `native_hybrid`: top-1 1.00, top-3 1.00, top-5 1.00, average packed context 35 approximate tokens, average latency 3ms,
- `native_graph`: top-1 1.00, top-3 1.00, top-5 1.00, average packed context 35 approximate tokens, average latency 4ms,
- `ctxhelm_cli`: top-1 1.00, top-3 1.00, top-5 1.00, average packed context 54 approximate tokens, average latency 141ms,
- model cost: $0.00 because this is retrieval-only evaluation.

### Sprint 6: Code Context Graph Research Lane

Goal:

Add graph-augmented repository understanding as a research lane.

In scope:

- graph schema,
- file, symbol, import, and test nodes,
- graph expansion retrieval,
- reranking hook,
- ctxhelm-seeded graph lane.

Out of scope:

- full multi-language parser support,
- hosted graph dashboard.

Acceptance criteria:

- graph lane runs on seeded suite,
- graph mode is compared against keyword, hybrid, and ctxhelm lanes,
- graph quality limitations are documented.

Current status:

Substantially complete for the first graph research lane. Code Context Graph v0 now builds Python file, symbol, import, and test/source relationship nodes from the repository snapshot. `native_graph` runs as a retriever, CLI context provider, repair context provider, and retrieval evaluation lane. On the 10-task seeded bug suite, `native_graph` matches `native_hybrid`: top-1 1.00, top-3 1.00, top-5 1.00, related-test recall 1.00, average packed context 35 approximate tokens, and average latency 4ms. A separate `graph_retrieval_v1` retrieval-only dataset now tests path-only failing-test reports where graph expansion should matter.

Latest verification command:

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

Latest evidence:

- `artifacts/experiments/retrieval_eval_v1/report.md`,
- lane count: 4,
- `native_graph`: top-1 1.00, top-3 1.00, top-5 1.00, related-test recall 1.00,
- `artifacts/experiments/graph_dataset_validation_v1/validation_report.md`,
- `artifacts/experiments/graph_retrieval_eval_v1/report.md`,
- graph-specific dataset: 3 valid tasks, `native_graph` top-1/top-3/top-5 1.00, `native_hybrid` top-1/top-3/top-5 0.00,
- current limitation: graph-specific evidence is retrieval-only and does not yet prove patch-success improvement.

### Sprint 7: Runtime Adapter Comparison

Goal:

Compare at least two agent scaffolds under the same task and model conditions.

In scope:

- Agentless baseline,
- LangGraph runtime,
- runtime config,
- comparable traces,
- scaffold comparison report.

Out of scope:

- Tree-search runtime unless the adapter baseline comparison is stable.

Acceptance criteria:

- same seeded task can run under two runtimes,
- resolved rate, cost, latency, iterations, and failure categories are reported,
- framework-specific objects do not leak into storage or reports.

Current status:

Started. `eval-scaffold` now compares multiple repair scaffolds under the same dataset, context provider, sandbox, and repair-evaluation metrics. The comparison includes `agentless`, `heuristic`, `langgraph`, `langgraph_fake_model`, the dependency-gated `deepagents` adapter, and the dependency-gated `openai_agents` adapter in offline compatibility mode; each scaffold also keeps its own nested repair report and run artifacts.

Latest verification command:

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

Latest evidence:

- `artifacts/experiments/scaffold_comparison_v1/scaffold_report.md`,
- `agentless`: patch generated 0.00, targeted tests passed 0.00, average latency 496ms, average trace events 9.0, runtime nodes 0.0, debug score 4.0,
- `heuristic`: patch generated 1.00, targeted tests passed 1.00, average latency 469ms, average trace events 12.0, runtime nodes 3.0, debug score 5.0,
- `langgraph`: patch generated 1.00, targeted tests passed 1.00, average latency 512ms, average trace events 15.0, runtime nodes 6.0, retries 1.0, debug score 5.0,
- `langgraph_fake_model`: patch generated 1.00, targeted tests passed 1.00, average latency 482ms, average trace events 15.0, runtime nodes 6.0, retries 1.0, debug score 5.0, model provider `offline_fake_model`, cost $0.00,
- `deepagents`: patch generated 1.00, targeted tests passed 1.00, average latency 465ms, average trace events 15.0, runtime nodes 6.0, retries 0.0, debug score 5.0; current evidence uses offline adapter compatibility mode, not live DeepAgents package/model execution.
- `openai_agents`: patch generated 1.00, targeted tests passed 1.00, average latency 466ms, average trace events 16.0, runtime nodes 7.0, retries 0.0, debug score 5.0; current evidence uses offline adapter compatibility mode, not live OpenAI Agents package/model execution.

### Sprint 8: Multi-Candidate Patch Search

Goal:

Evaluate whether test-time patch search improves success.

In scope:

- candidate generator,
- per-candidate sandbox execution,
- patch selector,
- success@k metrics,
- candidate comparison report.

Out of scope:

- large-scale parallel execution,
- learned selector.

Acceptance criteria:

- one-candidate and three-candidate modes are compared,
- selected candidate is justified in the final report,
- cost per successful patch is reported next to success.

Current status:

Started. `eval-patch-search` now runs deterministic patch-search variants over the seeded suite. Each candidate is applied and tested in an isolated repository copy. The first evaluator compares one-candidate and three-candidate modes with heuristic candidate generation, selects the first passing candidate, and writes task-level candidate artifacts plus aggregate CSV, JSON, and Markdown reports.

Latest verification command:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-patch-search \
  --dataset evals/tasks/seeded_bugs_v1 \
  --candidate-count 1 \
  --candidate-count 3 \
  --context-provider native_hybrid \
  --output artifacts/experiments/patch_search_eval_v1 \
  --json
```

Latest evidence:

- `artifacts/experiments/patch_search_eval_v1/patch_search_report.md`,
- `candidates_1`: success@1 1.00, success@k 1.00, selected success 1.00, average latency 442ms, average test runs 1.0,
- `candidates_3`: success@1 1.00, success@k 1.00, selected success 1.00, average latency 1371ms, average test runs 3.0,
- current decision: current seeded tasks are too easy for deterministic patch search; three-candidate mode increases validation cost without improving success.

### Sprint 9: Observability and Demo UI

Goal:

Make PatchSmith inspectable for demos and engineering review.

In scope:

- run history,
- trace timeline view,
- retrieved context view,
- diff view,
- failure summary,
- evaluation dashboard stub.

Out of scope:

- arbitrary hosted execution against untrusted repos.

Acceptance criteria:

- demo issue can be shown from saved artifacts,
- trace and report views are understandable without reading code,
- screenshots can support portfolio documentation.

Current status:

Substantially complete for the static review lane. The first Sprint 9 slice adds `index-artifacts`, a static observability command that scans saved experiment folders, classifies known report types, counts result rows, counts nested run artifacts, normalizes summary metrics, and writes Markdown, JSON, HTML dashboard, and run-detail HTML outputs. The generated dashboard provides research metrics, search, kind filtering, result/run load bars, links into saved reports/results, and recent-run drill-down links for generated detail pages plus report, trace, diff, stdout, and stderr artifacts. Run-detail pages render trace timeline, retrieved context paths, context broker targets, diff preview, and log previews. The second slice adds `inspect-failures`, a failure review report that scans saved run traces, groups repair-outcome categories, counts failed trace events, and links back to report, trace, and diff artifacts. This gives demos and engineering reviews one entry point for aggregate metrics and one explicit failure-analysis surface before a hosted UI exists.

Latest verification command:

```bash
PYTHONPATH=src python3 -m patchsmith.cli index-artifacts \
  --artifacts-dir artifacts \
  --output artifacts/experiments/index.md \
  --json-output artifacts/experiments/index.json \
  --html-output artifacts/experiments/index.html \
  --run-detail-output-dir artifacts/experiments/run-details \
  --json

PYTHONPATH=src python3 -m patchsmith.cli inspect-failures \
  --artifacts-dir artifacts \
  --output artifacts/experiments/failure_report.md \
  --json-output artifacts/experiments/failure_report.json \
  --max-runs 0 \
  --json
```

Latest evidence:

- `artifacts/experiments/index.md`,
- `artifacts/experiments/index.json`,
- `artifacts/experiments/index.html`,
- `artifacts/experiments/failure_report.md`,
- `artifacts/experiments/failure_report.json`,
- `artifacts/experiments/run-details/`,
- indexed experiments: 13,
- indexed saved runs: 363,
- normalized metric rows: 26,
- recent run links shown in Markdown/HTML: latest 25,
- generated run-detail pages: 25,
- full run list stored in JSON: 363,
- failure report scans saved traces and preserves failure cases for demo review,
- failure report run scan: 363,
- runs requiring attention: 62,
- failure categories: `no_patch_generated` 60, `sandbox_test_failed` 2.

### Sprint 10: Portfolio Launch

Goal:

Publish a credible, honest project artifact.

In scope:

- polished README,
- architecture diagram,
- demo script and video,
- final evaluation report,
- failure analysis report,
- tagged release.

Out of scope:

- unsupported public SaaS execution,
- inflated benchmark claims.

Acceptance criteria:

- README summarizes metrics and limitations,
- at least three experiment reports exist,
- public demo is safe and reproducible,
- failure cases are visible.

Current status:

Started. The README now surfaces current seeded-suite metrics, limitations, scaffold comparison, artifact dashboard generation, failure report generation, demo readiness generation, live calibration readiness generation, demo script generation, demo media generation, final evaluation generation, executable quality-gate generation, consolidated project-status generation, evidence-refresh orchestration, launch-blocker remediation commands, and release hygiene generation. The failure-analysis surface is generated from saved traces through `inspect-failures`, the launch review surface is generated through `demo-readiness`, the live-provider readiness surface is generated through `live-calibration`, the timed recording script is generated through `demo-script`, demo media is generated through `demo-media`, the portfolio-facing evaluation narrative is generated through `final-evaluation`, the executable verification surface is generated through `quality-gate`, the status briefing surface is generated through `project-status`, the review refresh surface is generated through `refresh-evidence`, the blocker backlog is generated through `launch-blockers`, and release checks are generated through `release-hygiene`. Current readiness is `ready_with_caveats`: offline seeded-suite evidence is coherent, but live LLM calibration is not present beyond `offline_fake_model` metadata. Current live calibration readiness is `not_configured`: no `OPENAI_API_KEY`, 10 saved DeepAgents package-backed adapter runs, 30 compatibility-mode runs, OpenAI Agents adapter smoke evidence in offline compatibility mode, and no saved non-offline provider rows. Current release hygiene is `ready_with_warnings` after restoring local Git metadata. CI workflow coverage, a Mermaid architecture diagram, SVG/PNG demo media, an executable quality-gate report, consolidated project-status report, evidence-refresh orchestration, and dependency-chain launch remediation now exist. The remaining Sprint 10 work is running live-provider calibration when credentials and budget are available.

Latest verification command:

```bash
PYTHONPATH=src python3 -m patchsmith.cli demo-readiness \
  --artifacts-dir artifacts \
  --output artifacts/experiments/demo_readiness.md \
  --json-output artifacts/experiments/demo_readiness.json \
  --json

PYTHONPATH=src python3 -m patchsmith.cli live-calibration \
  --artifacts-dir artifacts \
  --output artifacts/experiments/calibration_readiness.md \
  --json-output artifacts/experiments/calibration_readiness.json \
  --json

PYTHONPATH=src python3 -m patchsmith.cli live-calibration-plan \
  --artifacts-dir artifacts \
  --output artifacts/experiments/live_calibration_plan.md \
  --json-output artifacts/experiments/live_calibration_plan.json \
  --json

PYTHONPATH=src python3 -m patchsmith.cli demo-script \
  --artifacts-dir artifacts \
  --output artifacts/experiments/demo_script.md \
  --json-output artifacts/experiments/demo_script.json \
  --json

PYTHONPATH=src python3 -m patchsmith.cli demo-media \
  --artifacts-dir artifacts \
  --output artifacts/experiments/demo_media.md \
  --svg-output artifacts/experiments/demo_media.svg \
  --png-output artifacts/experiments/demo_media.png \
  --json-output artifacts/experiments/demo_media.json \
  --json

PYTHONPATH=src python3 -m patchsmith.cli final-evaluation \
  --artifacts-dir artifacts \
  --output artifacts/experiments/final_evaluation.md \
  --json-output artifacts/experiments/final_evaluation.json \
  --json

PYTHONPATH=src python3 -m patchsmith.cli quality-gate \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/quality_gate.md \
  --json-output artifacts/experiments/quality_gate.json \
  --logs-dir artifacts/experiments/quality_gate_logs \
  --json

PYTHONPATH=src python3 -m patchsmith.cli project-status \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/project_status.md \
  --json-output artifacts/experiments/project_status.json \
  --json

PYTHONPATH=src python3 -m patchsmith.cli refresh-evidence \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/evidence_refresh.md \
  --json-output artifacts/experiments/evidence_refresh.json \
  --json

PYTHONPATH=src python3 -m patchsmith.cli delivery-audit \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/delivery_audit.md \
  --json-output artifacts/experiments/delivery_audit.json \
  --json

PYTHONPATH=src python3 -m patchsmith.cli release-hygiene \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/release_hygiene.md \
  --json-output artifacts/experiments/release_hygiene.json \
  --json
```

Latest evidence:

- `artifacts/experiments/demo_readiness.md`,
- `artifacts/experiments/demo_readiness.json`,
- `artifacts/experiments/calibration_readiness.md`,
- `artifacts/experiments/calibration_readiness.json`,
- `artifacts/experiments/live_calibration_plan.md`,
- `artifacts/experiments/live_calibration_plan.json`,
- `artifacts/experiments/demo_script.md`,
- `artifacts/experiments/demo_script.json`,
- `artifacts/experiments/demo_media.md`,
- `artifacts/experiments/demo_media.json`,
- `artifacts/experiments/demo_media.svg`,
- `artifacts/experiments/demo_media.png`,
- `artifacts/experiments/final_evaluation.md`,
- `artifacts/experiments/final_evaluation.json`,
- `artifacts/experiments/quality_gate.md`,
- `artifacts/experiments/quality_gate.json`,
- `artifacts/experiments/quality_gate_logs/`,
- `artifacts/experiments/project_status.md`,
- `artifacts/experiments/project_status.json`,
- `artifacts/experiments/evidence_refresh.md`,
- `artifacts/experiments/evidence_refresh.json`,
- `artifacts/experiments/delivery_audit.md`,
- `artifacts/experiments/delivery_audit.json`,
- `artifacts/experiments/launch_blockers.md`,
- `artifacts/experiments/launch_blockers.json`,
- `artifacts/experiments/public_issue_corpus_v1/focused_test_setup_execution_report.md`,
- `artifacts/experiments/public_issue_corpus_v1/focused_test_setup_execution_summary.json`,
- `artifacts/experiments/public_issue_corpus_v1/focused_test_setup_validation_report.md`,
- `artifacts/experiments/public_issue_corpus_v1/focused_test_setup_validation_summary.json`,
- `artifacts/experiments/release_hygiene.md`,
- `artifacts/experiments/release_hygiene.json`,
- readiness status: `ready_with_caveats`,
- live calibration readiness: `not_configured`,
- live calibration plan: `blocked`,
- delivery audit: `in_progress_with_blockers`,
- quality gate: `passed`,
- project status: `in_progress_with_blockers`,
- evidence refresh: `passed_with_skips`,
- launch blocker status: `blocked`,
- launch blockers: 2,
- launch warnings: 2,
- release hygiene status: `ready_with_warnings`,
- release hygiene checks: generated review artifacts include quality-gate, project-status, live-calibration planning, launch blockers, public issue context preview, task materialization validation/readiness, focused-test planning, focused-test run, focused-test diagnosis, focused-test setup-plan, setup-readiness, setup-execution, and setup-validation evidence; live LLM calibration remains the only warning,
- indexed experiments: 16,
- indexed saved runs: 443,
- normalized metric rows: 29,
- runs requiring attention: 72,
- model providers: `offline_fake_model` 23,
- saved live-provider runs: 0,
- DeepAgents package-backed runs: 10,
- DeepAgents compatibility-mode runs: 30,
- OpenAI Agents package-backed runs: 10,
- OpenAI Agents compatibility-mode runs: 20,
- demo script sections: 6,
- demo script target duration: 3m 10s,
- demo media: SVG and PNG generated from saved evidence,
- final evaluation decision bullets: 9,
- final evaluation limitations: 6,
- caveat: no non-offline live provider metadata was found.
- remaining release warning: live LLM calibration.
- local Git metadata: initialized on `main`.
- packaging metadata: Hatch wheel target ships `src/patchsmith`; `dev` extra includes `pytest` and `build`.
- added CI workflow: `.github/workflows/ci.yml`.
- added architecture diagram: Mermaid block in `docs/03_architecture.md`.

## Current sprint selection

The active sprint is Sprint 10: Portfolio Launch.

Reason:

- Sprints 1 through 9 now have working code paths and saved evidence artifacts.
- Static review surfaces now cover aggregate metrics, run details, and failure cases without adding a web stack.
- The remaining gap is launch execution: resolve Docker smoke availability, unblock focused public issue setup-readiness, and run live-provider calibration only when credentials and budget are available.

## Sprint 10 task breakdown

| Task | Type | Owner | Output |
|---|---|---|---|
| S10-T1 | Demo | PatchSmith | `demo-script` command plus timed recording script from saved evidence |
| S10-T6 | Media | PatchSmith | `demo-media` command plus SVG/PNG demo media assets |
| S10-T2 | Reports | PatchSmith | `final-evaluation` command plus narrative tying retrieval, repair, scaffold, patch-search, and failure evidence together |
| S10-T3 | Portfolio | PatchSmith | README/demo copy with honest metrics, limits, and non-live-provider caveats |
| S10-T4 | Release | PatchSmith | `release-hygiene` command plus release warning report |
| S10-T5 | Readiness | PatchSmith | `demo-readiness` command plus Markdown/JSON launch review report |
| S10-T7 | Blockers | PatchSmith | `launch-blockers` command plus prioritized Docker/setup/calibration/release action backlog with dependency-chain remediation commands |
| S10-T8 | Setup execution | PatchSmith | `execute-focused-test-setups` command plus readiness-gated dry-run/execution evidence |
| S10-T9 | Setup policy | PatchSmith | Docker-only editable-install policy behind explicit dependency-install and network flags |
| S10-T10 | Setup validation | PatchSmith | `validate-focused-test-setups` command plus post-setup validation dry-run/execution evidence |
| S10-T11 | Live calibration planning | PatchSmith | `live-calibration-plan` command plus credential-gated live-run matrix and claim boundaries |
| S10-T12 | Delivery audit | PatchSmith | `delivery-audit` command plus objective-to-evidence status report |
| S10-T13 | Quality gate | PatchSmith | `quality-gate` command plus compile, diff, pytest, package-build, and log evidence |
| S10-T14 | Status briefing | PatchSmith | `project-status` command plus consolidated progress, verification, launch, model, and adapter evidence |
| S10-T15 | Evidence refresh | PatchSmith | `refresh-evidence` command plus ordered review-artifact regeneration audit |
| S10-T16 | Evidence freshness | PatchSmith | `project-status` freshness table plus stale/undated source counters |

## Completed Sprint 9 task breakdown

| Task | Type | Owner | Output |
|---|---|---|---|
| S9-T1 | Observability | PatchSmith | static experiment/run artifact index |
| S9-T2 | CLI | PatchSmith | `index-artifacts` command with Markdown, JSON, HTML, and metric outputs |
| S9-T3 | Tests | PatchSmith | artifact scanning, rendering, and CLI smoke coverage |
| S9-T4 | Reports | PatchSmith | `artifacts/experiments/index.md`, `index.json`, `index.html`, and `run-details/` |
| S9-T5 | Demo | PatchSmith | trace, report, diff, logs, and experiment review flow from saved artifacts |
| S9-T6 | UI | PatchSmith | lightweight static metrics dashboard and run-detail pages |
| S9-T7 | Failure analysis | PatchSmith | `inspect-failures` command plus Markdown/JSON failure report |

## Risk controls

- Keep ctxhelm optional and fallback-capable.
- Count ctxhelm unavailable separately from retrieval failure.
- Do not treat source-bearing ctxhelm artifacts as public report content.
- Treat deterministic control candidates as infrastructure evidence, not proof of model-diverse patch search.
- Keep every candidate in an isolated repository copy.
- Report added test runs and latency next to success@k.
- Keep artifact indexes local and avoid copying source-bearing raw context into summary reports.
- Treat the artifact index as a navigation surface; reports remain the source of truth for metrics and decisions.
- Treat project-status freshness warnings as process evidence; rerun the underlying generator before sprint review when a source is stale, undated, or missing.
- Keep eval tasks small and deterministic.
- Record generated reports under `artifacts/`, not tracked docs.

## Review checklist

- [ ] Does the sprint produce a command a reviewer can run?
- [ ] Does the output include a saved report?
- [ ] Are safety-sensitive commands policy-checked?
- [ ] Are failures preserved rather than hidden?
- [ ] Are metrics defined before interpreting results?
- [ ] Does the sprint move the project closer to issue-to-tested-patch?
