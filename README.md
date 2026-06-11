# PatchSmith

PatchSmith is a research platform for AI-assisted software maintenance. It takes an issue, retrieves the code that looks relevant, asks a repair scaffold to produce a bounded edit, runs the selected tests in a sandbox, and saves the evidence.

Patch generation is only one part of the job. PatchSmith is built to answer a harder question: which parts of an agentic repair system actually help? Retrieval strategy, graph context, scaffold design, sandbox feedback, patch search, model choice, and cost are all measured separately.

## What Works Today

- Repository clone/copy, file indexing, and issue-conditioned retrieval.
- Native keyword, hybrid, graph, and ctxhelm-backed context providers.
- Agent runtimes for `agentless`, `heuristic`, `langgraph`, `deepagents`, and `openai_agents`.
- DeepAgents integration with state-backed file reads, todo-driven planning, a patch-review subagent, structured patch output, read-only virtual filesystem permissions, and sandbox-feedback retries.
- Local and Docker sandbox execution with command policy checks.
- Seeded repair and retrieval benchmarks.
- Public issue corpus preparation, reproduction gates, repair-readiness gates, and repair-attempt reporting.
- Static artifact index, run reports, traces, diffs, stdout/stderr logs, failure reports, release hygiene checks, and quality gates.

The current saved evidence shows the seeded MVP is complete and the local quality gate passes. The public issue lane is still research evidence, not a claim that PatchSmith solves arbitrary GitHub issues.

## Why This Exists

Most coding-agent demos collapse everything into one number: did the agent fix the bug or not?

That hides the useful engineering signal. PatchSmith keeps the pieces apart:

- Did retrieval find the right files?
- Did the scaffold produce a safe, minimal edit?
- Did tests fail because the patch was bad, because setup was missing, or because the command was wrong?
- Did retries use real sandbox feedback?
- How much did the model call cost?
- Which failures are interesting enough to improve the system?

That separation makes PatchSmith useful as both a software-maintenance agent prototype and an evaluation harness.

## Architecture

```text
issue + repo
  -> clone/copy repository
  -> index files and symbols
  -> retrieve candidate context
  -> run repair scaffold
  -> apply one bounded text replacement
  -> run policy-checked tests
  -> write report, trace, diff, logs, and metrics
```

PatchSmith deliberately keeps model output away from direct filesystem writes. Agents can plan. PatchSmith applies the final edit through its own bounded replacement gate.

## Install

```bash
git clone https://github.com/thromel/patchsmith.git
cd patchsmith

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

For native DeepAgents runs:

```bash
python -m pip install -e ".[dev,deepagents]"
```

## Quickstart

Run the test suite:

```bash
PYTHONPATH=src python -m pytest -q
```

Run a deterministic repair on a seeded task:

```bash
PYTHONPATH=src python -m patchsmith.cli run \
  --repo evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo \
  --issue-file evals/tasks/seeded_bugs_v1/task_001_logic_bug/issue.md \
  --test-command "python3 -m pytest" \
  --runtime heuristic \
  --context-provider native_hybrid \
  --artifacts-dir artifacts \
  --json
```

Expected result: PatchSmith edits `src/simple_calc.py`, runs the targeted pytest command, and writes a report under `artifacts/runs/<run_id>/`.

When you have reviewed source hints from a reproduction spec or failure trace, force those files into the repair context:

```bash
PYTHONPATH=src python -m patchsmith.cli run \
  --repo path/to/repo \
  --issue-file path/to/issue.md \
  --context-provider native_hybrid \
  --context-path "src/package/module.py#suspected_symbol" \
  --json
```

`--context-path` can be repeated. PatchSmith strips the optional `#symbol` suffix before reading the file, but keeps the full hint in the issue text when public issue repairs provide reviewed hints.

## Run Evaluations

Validate the seeded benchmark:

```bash
PYTHONPATH=src python -m patchsmith.cli validate-dataset \
  --dataset evals/tasks/seeded_bugs_v1 \
  --output artifacts/experiments/seeded_dataset_validation_v1 \
  --json
```

Compare retrieval providers:

```bash
PYTHONPATH=src python -m patchsmith.cli eval-retrieval \
  --dataset evals/tasks/seeded_bugs_v1 \
  --context-provider native \
  --context-provider native_hybrid \
  --context-provider native_graph \
  --context-provider ctxhelm_cli \
  --output artifacts/experiments/retrieval_eval_v1 \
  --json
```

Run the repair benchmark:

```bash
PYTHONPATH=src python -m patchsmith.cli eval-repair \
  --dataset evals/tasks/seeded_bugs_v1 \
  --runtime langgraph \
  --planner fake_model \
  --context-provider native_hybrid \
  --output artifacts/experiments/langgraph_model_repair_eval_v1 \
  --json
```

Compare scaffolds:

```bash
PYTHONPATH=src python -m patchsmith.cli eval-scaffold \
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

Generate the artifact dashboard:

```bash
PYTHONPATH=src python -m patchsmith.cli index-artifacts \
  --artifacts-dir artifacts \
  --output artifacts/experiments/index.md \
  --json-output artifacts/experiments/index.json \
  --html-output artifacts/experiments/index.html \
  --run-detail-output-dir artifacts/experiments/run-details \
  --json
```

## DeepAgents

PatchSmith has two DeepAgents paths:

- `runtime=deepagents, planner=heuristic`: adapter and scaffold compatibility evidence.
- `runtime=deepagents, planner=deepagents`: native DeepAgents planning with a live OpenAI-compatible chat model.

Preflight a model before spending money:

```bash
OPENAI_API_KEY=... \
PYTHONPATH=src python -m patchsmith.cli openai-model-preflight \
  --model gpt-5.4-mini \
  --json
```

Run the native DeepAgents planner:

```bash
OPENAI_API_KEY=... \
PATCHSMITH_DEEPAGENTS_MODEL=gpt-5.4-mini \
PYTHONPATH=src python -m patchsmith.cli eval-repair \
  --dataset evals/tasks/seeded_bugs_v1 \
  --runtime deepagents \
  --planner deepagents \
  --max-retries 1 \
  --context-provider native_hybrid \
  --output artifacts/experiments/deepagents_native_repair_eval_v1 \
  --json
```

Saved live evidence currently uses `gpt-5.4-mini`. The requested `gpt-5.5-mini` model was not exposed by the available OpenAI account during the latest checks, and the most recent clipboard key returned `401 Unauthorized`. Do not cite `gpt-5.5-mini` results unless you rerun the preflight and the benchmark with a valid key that has access to that model.

## Docker Sandbox

Build the seeded smoke image:

```bash
docker build -f docker/seeded-smoke.Dockerfile -t patchsmith-seeded-smoke:py312 .
```

Run with Docker isolation:

```bash
PYTHONPATH=src python -m patchsmith.cli run \
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

Docker mode disables implicit image pulls, disables network by default, drops capabilities, mounts the repository at `/workspace`, applies resource limits, and records the selected sandbox in the trace.

## Public Issue Corpus

PatchSmith includes a small public issue smoke lane under `evals/issue_corpora/public_issue_smoke_v1`.

The lane has separate gates for:

- corpus validation,
- repository preflight,
- source-free context preview,
- task materialization,
- focused test planning,
- setup validation,
- reproduction evidence,
- repair readiness,
- repair attempts.

This is intentional. A public issue repair should only count after the failing behavior is reproduced, the patch is generated, and validation passes. Passing setup checks are useful evidence, but they do not prove repair quality.

## Quality Gates

Run the local release gate:

```bash
PYTHONPATH=src python -m patchsmith.cli quality-gate \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/quality_gate.md \
  --json-output artifacts/experiments/quality_gate.json \
  --logs-dir artifacts/experiments/quality_gate_logs \
  --json
```

The gate runs:

- Python compile checks,
- whitespace diff checks,
- full pytest,
- package build.

CI also runs Ruff, Ruff format check, mypy, compile, pytest, and package build.

## Current Status

As of the latest local evidence:

- MVP progress: `100%`.
- Quality gate: `passed`.
- Delivery audit: `in_progress_with_blockers`.
- Release hygiene: `ready_with_warnings`.
- DeepAgents package evidence: present.
- Live-provider evidence: present for `deepagents_openai_chat` and `openai_responses`.
- Public issue repair quality: not launch-grade yet. The latest all-task DeepAgents public issue attempt validated 2 of 3 tasks.

That mix is important. The seeded benchmark and platform plumbing are in good shape. The real-world repair lane still needs more work before it should be presented as robust autonomous repair.

## Repository Layout

```text
src/patchsmith/
  cli/                     CLI commands
  evaluation/              seeded and public-issue evaluation flows
  observability/           artifact index, failure reports, HTML/Markdown renderers
  portfolio/               readiness, delivery, release, and demo reports
  runtime/                 agent runtime adapters
  deepagents_planner.py    native DeepAgents planner
  retrieval.py             native retrieval providers
  sandbox.py               local and Docker command execution

docs/                       architecture, safety, evaluation, and runbook docs
evals/                      seeded tasks and public issue corpora
adr/                        architecture decision records
experiments/                experiment plans
templates/                  report and ADR templates
```

## Good First Commands

```bash
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m patchsmith.cli quality-gate --json
PYTHONPATH=src python -m patchsmith.cli project-status --json
PYTHONPATH=src python -m patchsmith.cli demo-readiness --json
```

## License

No license file is included yet. Treat the code as source-available until a license is added.
