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

Docker mode runs the policy-checked command inside a per-run container with implicit image pulls disabled, network disabled, dropped capabilities, resource limits, a mounted `/workspace`, and a sanitized host environment. The selected sandbox mode is recorded in each run trace. Use an image that already contains task dependencies such as `pytest`.

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

The report records Docker daemon availability, local smoke-image availability, and the seeded Docker test run when available. If the daemon is unavailable, it records `not_available` evidence instead of silently skipping the gate.

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

Generate the live calibration readiness report:

```bash
PYTHONPATH=src python3 -m patchsmith.cli live-calibration \
  --artifacts-dir artifacts \
  --output artifacts/experiments/calibration_readiness.md \
  --json-output artifacts/experiments/calibration_readiness.json \
  --json
```

Latest live calibration readiness evidence is saved in `artifacts/experiments/calibration_readiness.md` and `artifacts/experiments/calibration_readiness.json`. Current status is `not_configured`: the OpenAI SDK is importable, but `OPENAI_API_KEY` is not set and saved model-provider evidence is still offline-only. DeepAgents now has 10 saved package-backed adapter smoke runs, while the current shell still does not import `deepagents`. OpenAI Agents SDK now has 10 saved package-backed adapter smoke runs, while the current shell still does not import `agents`.

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

Generate the release hygiene report:

```bash
PYTHONPATH=src python3 -m patchsmith.cli release-hygiene \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/release_hygiene.md \
  --json-output artifacts/experiments/release_hygiene.json \
  --json
```

Latest release hygiene evidence is saved in `artifacts/experiments/release_hygiene.md` and `artifacts/experiments/release_hygiene.json`. Current status is `ready_with_warnings`: CI, packaging metadata, architecture-diagram, demo-media, calibration-readiness, public issue corpus/context-preview evidence, and local Git metadata checks pass, while live LLM calibration remains unproven and must stay visible in release claims.

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

The context broker boundary, retrieval eval runner, repair eval runner, scaffold comparison runner, patch-search evaluator, public issue corpus validation/preflight/context preview, static artifact index/dashboard with normalized metrics and generated run-detail trace pages, failure review report, demo readiness report, live calibration readiness report, generated demo script, final evaluation report, release hygiene report, deterministic heuristic runtime, LangGraph orchestration runtime, DeepAgents adapter compatibility mode plus package-backed smoke evidence, OpenAI Agents SDK adapter compatibility mode, offline model-planner seam, credential-gated OpenAI Responses client, and Python Code Context Graph v0 now exist. The current seeded suite has 10 tasks and compares `native`, `native_hybrid`, `native_graph`, and `ctxhelm_cli` for retrieval, including aggregate context packing metadata. Scaffold comparison now includes trace complexity and debuggability metrics. The next useful development step is resolving the remaining live-provider warning, harder patch-search tasks with model-diverse candidates, or live-provider calibration when credentials and budget are explicitly available.

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
