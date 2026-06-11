# PatchSmith

[![CI](https://github.com/thromel/patchsmith/actions/workflows/ci.yml/badge.svg)](https://github.com/thromel/patchsmith/actions/workflows/ci.yml)

PatchSmith is a research platform for evaluating AI software-maintenance agents.

Give it a repository, an issue, and a test command. PatchSmith retrieves likely
context, lets an agent propose a bounded patch, runs validation in a sandbox,
and writes down the evidence: diffs, traces, stdout, stderr, timing, reports,
and model-cost metadata when a live model is used.

The goal is not to pretend every passing test means "the agent fixed it."
PatchSmith is built to answer the more useful question: what happened, why did
it happen, and can someone audit the repair attempt later?

## Status

PatchSmith is active R&D code.

The seeded benchmark lane is the stable development path. It is useful for
testing retrieval, scaffold behavior, sandbox execution, reporting, and release
gates. The public GitHub issue lane exists, but it is still calibration work.
Treat public-issue repair results as experimental unless they come with a saved
artifact directory that includes the repository state, issue spec, reproduction
command, patch, validation output, and model metadata.

## What It Does

- Clones or copies target repositories into controlled workspaces.
- Indexes files, symbols, and issue text for context retrieval.
- Supports native keyword, hybrid, graph, and `ctxhelm` context providers.
- Runs repair attempts through `agentless`, `heuristic`, `langgraph`,
  `deepagents`, and `openai_agents` runtime adapters.
- Includes a native DeepAgents planner with file reads, todo state, structured
  patch output, a patch-review subagent, and sandbox-feedback retries.
- Applies model output through PatchSmith's own bounded text-replacement gate.
- Runs local or Docker sandbox validation with command-policy checks.
- Produces Markdown, JSON, HTML, trace, diff, stdout, stderr, timing, and cost
  artifacts.
- Ships local quality gates for tests, static checks, package build, release
  hygiene, demo readiness, and artifact indexing.

## Why This Exists

Most coding-agent demos compress the whole story into one number: did the final
test pass?

That is too coarse for repair research. A run can fail because retrieval missed
the right file, the prompt scaffold asked the wrong thing, the model produced an
unsafe edit, the reproduction command was weak, the sandbox was misconfigured,
or the issue was never reproducible in the first place.

PatchSmith keeps those pieces separate. It is meant for comparing repair systems
without hiding setup failures, weak validation, or lucky patches.

## How It Works

```text
issue + repository + test command
  -> clone or copy repository
  -> index files and symbols
  -> retrieve candidate context
  -> run a repair runtime
  -> apply one bounded patch
  -> run policy-checked validation
  -> write reports, traces, logs, diffs, and metrics
```

PatchSmith does not let a model write freely into the repository. A runtime can
inspect context and propose an edit. PatchSmith applies the final patch through
its own gate and records the result.

## Install

```bash
git clone https://github.com/thromel/patchsmith.git
cd patchsmith

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

For native DeepAgents experiments:

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

Run a deterministic repair on a seeded bug:

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

Expected behavior: PatchSmith edits the seeded task repository, runs the pytest
command, and writes a run report under `artifacts/runs/<run_id>/`.

If you already know a likely file, force it into the context:

```bash
PYTHONPATH=src python -m patchsmith.cli run \
  --repo path/to/repo \
  --issue-file path/to/issue.md \
  --context-provider native_hybrid \
  --context-path "src/package/module.py#suspected_symbol" \
  --json
```

`--context-path` can be repeated. PatchSmith strips the optional `#symbol`
suffix before reading the file, but keeps the full hint in the issue text for
repair flows that provide reviewed hints.

## DeepAgents

PatchSmith has two DeepAgents modes:

- `runtime=deepagents, planner=heuristic`: adapter and scaffold compatibility.
- `runtime=deepagents, planner=deepagents`: native DeepAgents planning with a
  live OpenAI-compatible chat model.

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

Do not cite model performance from a README command. Use the saved artifact
directory for the exact run: model name, account, prompt, dataset, commit, diff,
logs, and validation output all matter.

## Evaluation Commands

Validate the seeded dataset:

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

Compare scaffold variants:

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

The public issue smoke lane lives under
`evals/issue_corpora/public_issue_smoke_v1`.

It has separate gates for corpus validation, repository preflight, source-free
context preview, task materialization, focused test planning, setup validation,
reproduction evidence, repair readiness, and repair attempts.

That separation is intentional. A public issue repair should only count after
the failing behavior is reproduced, a patch is generated, and validation passes.
Passing setup checks are useful evidence, but they do not prove repair quality.

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

Docker mode disables implicit image pulls, disables network by default, drops
capabilities, mounts the repository at `/workspace`, applies resource limits,
and records the selected sandbox in the trace.

## Quality Gate

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

The gate runs compile checks, whitespace checks, the full pytest suite, and a
package build. CI also runs Ruff, Ruff format check, mypy, compile checks,
pytest, and package build.

## Repository Layout

```text
src/patchsmith/
  cli/                     CLI commands
  evaluation/              seeded and public-issue evaluation flows
  observability/           artifact index, failure reports, renderers
  portfolio/               readiness, release, and demo reports
  runtime/                 agent runtime adapters
  deepagents_planner.py    native DeepAgents planner
  deepagents_schema.py     native DeepAgents structured output schema
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

## Roadmap

- Calibrate live DeepAgents runs against the seeded benchmark.
- Expand public-issue reproduction coverage without treating setup success as
  repair success.
- Add more model/provider cost accounting.
- Improve artifact comparison for retrieval, patch quality, retries, and
  validation strength.
- Keep the runtime adapters small enough to read and test.

## License

No license file is included yet. Treat the code as source-available until a
license is added.
