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

Expected future LangGraph command:

```bash
patchsmith run \
  --repo https://github.com/example/repo \
  --issue-file examples/issues/issue_001.md \
  --runtime langgraph \
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

LangGraph orchestration evaluation with the current deterministic planner:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-repair \
  --dataset evals/tasks/seeded_bugs_v1 \
  --runtime langgraph \
  --context-provider native_hybrid \
  --output artifacts/experiments/langgraph_repair_eval_v1 \
  --json
```

LangGraph evaluation through the offline model-planner contract:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-repair \
  --dataset evals/tasks/seeded_bugs_v1 \
  --runtime langgraph \
  --planner fake_model \
  --context-provider native_hybrid \
  --output artifacts/experiments/langgraph_model_repair_eval_v1 \
  --json
```

`fake_model` is an offline JSON model double. It exercises prompt construction, model-output parsing, retrieved-path validation, LangGraph patch application, reports, and eval metrics without live credentials.

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

Scaffold comparison:

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

The scaffold report includes patch/test rates, latency, trace event counts, runtime node counts, failed trace events, retry events, and a 0-5 debug score.
The `deepagents` and `openai_agents` variants currently use PatchSmith's dependency-gated adapters in offline compatibility mode unless their optional extras are installed.

OpenAI Agents SDK adapter smoke:

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

This proves the `openai-agents` import boundary and PatchSmith adapter contract when the extra is installed. It does not prove live OpenAI Agents model quality unless credentials, model config, and non-offline provider metadata are present.

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

`run`, `eval-repair`, `eval-scaffold`, and `eval-patch-search` all accept `--sandbox-mode local|docker` plus `--sandbox-image`. Local mode remains the default for fast deterministic development runs. Docker mode wraps the same command-policy decision in `docker run` with implicit image pulls disabled, network disabled, dropped capabilities, a `/workspace` bind mount, resource limits, and sanitized host environment. Use a prebuilt image containing the test runner and task dependencies; otherwise the Docker run can fail even when the patch is correct.

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

The Docker smoke report preserves daemon, image, and seeded-run evidence. `not_available` means Docker was not reachable in the current shell; it does not satisfy the MVP Docker checkbox.

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

Live calibration readiness:

```bash
PYTHONPATH=src python3 -m patchsmith.cli live-calibration \
  --artifacts-dir artifacts \
  --output artifacts/experiments/calibration_readiness.md \
  --json-output artifacts/experiments/calibration_readiness.json \
  --json
```

The live calibration readiness report checks whether the OpenAI SDK is importable, credentials are configured, cost-rate environment variables are present, the optional DeepAgents package is importable in the current shell, saved DeepAgents traces prove package-backed adapter execution, and saved artifacts contain non-offline provider metadata. `not_configured` means live calibration has not been run and public claims must stay scoped to offline seeded-suite evidence.

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

Release hygiene:

```bash
PYTHONPATH=src python3 -m patchsmith.cli release-hygiene \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/release_hygiene.md \
  --json-output artifacts/experiments/release_hygiene.json \
  --json
```

The release hygiene report checks required docs, generated review artifacts, demo readiness, failure visibility, live-provider caveats, Git metadata, packaging metadata, CI, demo media, architecture diagram evidence, and README caveat markers. Treat `blocked` as a hard stop for tagged/public release claims.

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
  --runtime langgraph \
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
