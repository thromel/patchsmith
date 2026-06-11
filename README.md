# PatchSmith

[![CI](https://github.com/thromel/patchsmith/actions/workflows/ci.yml/badge.svg)](https://github.com/thromel/patchsmith/actions/workflows/ci.yml)

PatchSmith is a research platform for studying AI software-maintenance agents.

Give it an issue and a repository. PatchSmith retrieves likely context, asks a repair
runtime for a bounded edit, applies that edit through its own patch gate, runs tests in a
sandbox, and writes down the evidence: reports, diffs, traces, stdout, stderr, timing, and
model-cost metadata when a live model is used.

The point is not to make a flashy claim that an agent fixed a bug. The point is to make the
repair attempt auditable.

## Why This Exists

Most coding-agent demos collapse everything into one question: did the final test pass?
That is too coarse for real engineering work.

PatchSmith keeps the repair loop split into parts:

- Did retrieval find the files that mattered?
- Did the agent propose a small, reviewable patch?
- Did the test command actually reproduce the issue?
- Did the patch fail because the model was wrong, setup was missing, or validation was weak?
- Did retries use real sandbox feedback?
- What did the live model call cost?

That separation matters. It lets us improve retrieval, scaffolding, validation, sandboxing,
and model choice without pretending that one better number proves the whole system is solved.

## What Works Today

PatchSmith currently includes:

- Repository clone/copy, file indexing, and issue-conditioned context retrieval.
- Native keyword, hybrid, graph, and `ctxhelm` context providers.
- Repair runtimes for `agentless`, `heuristic`, `langgraph`, `deepagents`, and
  `openai_agents`.
- A native DeepAgents planner with state-backed file reads, todo state, a patch-review
  subagent, read-only virtual filesystem permissions, structured patch output, and sandbox
  feedback retries.
- Local and Docker sandbox execution with command-policy checks.
- Seeded bug, retrieval, scaffold, repair, and public-issue smoke evaluation flows.
- Static artifact indexing, run reports, failure reports, traces, diffs, logs, release
  hygiene checks, and quality gates.

The seeded benchmark path is the stable development lane. The public issue lane is still
calibration work. Saved artifacts can show useful behavior on a tiny curated corpus, but they
should not be read as a broad GitHub-issue repair claim.

## How PatchSmith Works

```text
issue + repository
  -> clone or copy repository
  -> index files and symbols
  -> retrieve candidate context
  -> run a repair scaffold
  -> apply one bounded text replacement
  -> run policy-checked tests
  -> write reports, traces, diffs, logs, and metrics
```

PatchSmith keeps model output away from direct filesystem writes. A runtime can plan, inspect
context, and propose an edit. PatchSmith applies the final change through its own bounded
replacement gate and records what happened.

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

For OpenAI Agents SDK experiments:

```bash
python -m pip install -e ".[dev,openai-agents]"
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

Expected result: PatchSmith edits `src/simple_calc.py`, runs the targeted pytest command,
and writes a run report under `artifacts/runs/<run_id>/`.

If you already know a likely file, force it into the repair context:

```bash
PYTHONPATH=src python -m patchsmith.cli run \
  --repo path/to/repo \
  --issue-file path/to/issue.md \
  --context-provider native_hybrid \
  --context-path "src/package/module.py#suspected_symbol" \
  --json
```

`--context-path` can be repeated. PatchSmith strips the optional `#symbol` suffix before
reading the file, but keeps the full hint in the issue text when public-issue repair flows
provide reviewed hints.

## DeepAgents

PatchSmith has two DeepAgents paths:

- `runtime=deepagents, planner=heuristic`: adapter and scaffold compatibility.
- `runtime=deepagents, planner=deepagents`: native DeepAgents planning with a live
  OpenAI-compatible chat model.

Preflight a model before spending money:

```bash
OPENAI_API_KEY=... \
PYTHONPATH=src python -m patchsmith.cli openai-model-preflight \
  --model <model> \
  --json
```

Run the native DeepAgents planner on the seeded benchmark:

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

Do not cite a model result from README text alone. Use the saved artifact directory for the
exact run: model name, account, prompt, dataset, commit, and output files all matter.

## Evaluation

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

Run a repair benchmark:

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

Build an artifact index:

```bash
PYTHONPATH=src python -m patchsmith.cli index-artifacts \
  --artifacts-dir artifacts \
  --output artifacts/experiments/index.md \
  --json-output artifacts/experiments/index.json \
  --html-output artifacts/experiments/index.html \
  --run-detail-output-dir artifacts/experiments/run-details \
  --json
```

## Public Issue Corpus

The public issue smoke lane lives under `evals/issue_corpora/public_issue_smoke_v1`.

It has separate gates for:

- corpus validation,
- repository preflight,
- source-free context preview,
- task materialization,
- focused test planning,
- setup validation,
- reproduction evidence,
- repair readiness,
- repair attempts.

This is intentional. A public issue repair should only count after the failing behavior is
reproduced, a patch is generated, and validation passes. Passing setup checks are useful
evidence, but they do not prove repair quality.

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

Docker mode disables implicit image pulls, disables network by default, drops capabilities,
mounts the repository at `/workspace`, applies resource limits, and records the selected
sandbox in the trace.

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

The gate runs compile checks, whitespace checks, the full pytest suite, and package build.
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

No license file is included yet. Treat the code as source-available until a license is
added.
