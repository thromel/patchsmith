# PatchSmith

[![CI](https://github.com/thromel/patchsmith/actions/workflows/ci.yml/badge.svg)](https://github.com/thromel/patchsmith/actions/workflows/ci.yml)

PatchSmith is a research platform for testing AI software-maintenance agents under a controlled repair loop.

Give it an issue and a repository. PatchSmith selects likely context, asks a repair runtime to propose a bounded edit, applies that edit through its own replacement gate, runs tests in a sandbox, and saves the evidence: reports, diffs, traces, stdout, stderr, and cost metadata when a live model is involved.

PatchSmith is deliberately plain about the hard part: it writes down what happened.

## Why It Exists

Most repair benchmarks flatten the result into one question: did the agent fix the bug?

That hides the useful parts. PatchSmith keeps the repair pipeline split into pieces:

- Did retrieval find the files that matter?
- Did the scaffold produce a small, reviewable patch?
- Did the test command actually reproduce the issue?
- Did the run fail because the patch was wrong, because setup was missing, or because the validation command was bad?
- Did retries use real sandbox feedback?
- What did the live model call cost?

With those pieces separated, you can improve one part without pretending the whole system got better.

## What Works Today

- Repository clone/copy, file indexing, and issue-conditioned retrieval.
- Native keyword, hybrid, graph, and `ctxhelm` context providers.
- Repair runtimes for `agentless`, `heuristic`, `langgraph`, `deepagents`, and `openai_agents`.
- Native DeepAgents planning with state-backed file reads, todo state, a patch-review subagent, read-only virtual filesystem permissions, structured patch output, and sandbox-feedback retries.
- Local and Docker sandbox execution with command-policy checks.
- Seeded repair and retrieval benchmarks.
- A small public issue smoke corpus with separate setup, reproduction, readiness, and repair-attempt gates.
- Static artifact indexing, run reports, traces, diffs, logs, failure reports, quality gates, and release-hygiene checks.

## Current Status

The seeded MVP path is implemented and the local quality gate passes in the saved project evidence.

The public issue lane is still research evidence, not a broad repair claim. The latest saved all-task DeepAgents public issue attempt validated 2 of 3 tasks. Treat that as useful calibration data, not proof that PatchSmith can solve arbitrary GitHub issues.

Live DeepAgents evidence exists for `deepagents_openai_chat`, but any model-quality claim should name the exact model, account, prompt, dataset, and artifact directory used for that run.

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

PatchSmith deliberately keeps model output away from direct filesystem writes. Agents can plan and propose an edit. PatchSmith applies the final edit through its own bounded replacement gate.

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

Force reviewed files into the repair context when you already know where the issue lives:

```bash
PYTHONPATH=src python -m patchsmith.cli run \
  --repo path/to/repo \
  --issue-file path/to/issue.md \
  --context-provider native_hybrid \
  --context-path "src/package/module.py#suspected_symbol" \
  --json
```

`--context-path` can be repeated. PatchSmith strips the optional `#symbol` suffix before reading the file, but keeps the full hint in the issue text when public issue repairs provide reviewed hints.

## DeepAgents

PatchSmith has two DeepAgents paths:

- `runtime=deepagents, planner=heuristic`: adapter and scaffold compatibility evidence.
- `runtime=deepagents, planner=deepagents`: native DeepAgents planning with a live OpenAI-compatible chat model.

Preflight a model before spending money:

```bash
OPENAI_API_KEY=... \
PYTHONPATH=src python -m patchsmith.cli openai-model-preflight \
  --model <model> \
  --json
```

Run the native DeepAgents planner:

```bash
OPENAI_API_KEY=... \
PATCHSMITH_DEEPAGENTS_MODEL=<model> \
PYTHONPATH=src python -m patchsmith.cli eval-repair \
  --dataset evals/tasks/seeded_bugs_v1 \
  --runtime deepagents \
  --planner deepagents \
  --max-retries 1 \
  --context-provider native_hybrid \
  --output artifacts/experiments/deepagents_native_repair_eval_v1 \
  --json
```

Do not cite a model result from README text alone. Use the saved artifact directory for the exact run you want to discuss.

## Evaluation Commands

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

CI also runs Ruff, Ruff format check, mypy, compile checks, pytest, and package build.

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
