# Experiment 0002: Agent Scaffold Comparison

## Status

Aggregate local scaffold comparison complete; live model-backed scaffold comparison still planned.

## Research question

Which agent scaffold provides the best tradeoff between repair success, cost, latency, and debuggability?

## Hypothesis

The Agentless baseline will be competitive on simple localized bugs. DeepAgents should provide the best MVP balance of planning, review, sandbox feedback, and traceability, but may increase cost and latency on harder tasks.

## Dataset

Initial dataset:

- `seeded_bugs_v1`,
- 10 tasks.

Later dataset:

- curated GitHub issues,
- benchmark subset.

## Variants

| Variant | Description |
|---|---|
| agentless | localize, repair, validate |
| heuristic | deterministic seeded-task repair baseline |
| deepagents | DeepAgents-backed planning, edit, review, and retry loop |

## Fixed variables

- same model where possible,
- same retrieval strategy,
- same sandbox,
- same task set,
- same maximum cost budget where possible.

## Metrics

Primary:

- resolved rate.

Secondary:

- targeted test pass rate,
- full test pass rate,
- cost per run,
- latency per run,
- iterations,
- tool calls,
- failed tool calls,
- trace complexity,
- human debuggability score.

## Result table

| Scaffold | Resolved | Targeted tests passed | Avg cost | Avg latency | Avg trace events | Avg runtime nodes | Failed trace events | Avg retries | Debug score | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| agentless | 0.00 | 0.00 | n/a | 496ms | 9.0 | 0.0 | 10 | 0.0 | 4.0 | no-edit baseline; completes runs but generates no patches |
| heuristic | 1.00 | 1.00 | n/a | 469ms | 12.0 | 3.0 | 0 | 0.0 | 5.0 | deterministic 10-task seeded repair baseline |
| deepagents | 1.00 | 1.00 | n/a | 465ms | 15.0 | 6.0 | 0 | 0.0 | 5.0 | dependency-gated adapter in offline compatibility mode; live provider runs are tracked separately |

## Qualitative analysis

For each scaffold, inspect:

- how easy failures are to debug,
- whether the scaffold produces unnecessary tool calls,
- whether planning improves edits,
- whether retry logic improves or worsens results,
- whether the trace is readable.

## Decision rule

Use DeepAgents as the default runtime. Keep agentless and heuristic rows only as evaluation controls.

## Initial smoke result

Date: 2026-06-10

Aggregate command:

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

Aggregate artifacts:

- `artifacts/experiments/scaffold_comparison_v1/scaffold_report.md`
- `artifacts/experiments/scaffold_comparison_v1/scaffold_results.csv`
- `artifacts/experiments/scaffold_comparison_v1/scaffold_results.json`

Aggregate result:

- scaffold count: 3,
- agentless patch generated rate: 0.00,
- heuristic and DeepAgents targeted test pass rate: 1.00,
- DeepAgents exposes 15.0 average trace events and 6.0 average runtime nodes per task,
- total model cost: $0.00.

Nested repair reports:

- `artifacts/experiments/scaffold_comparison_v1/agentless/repair_report.md`
- `artifacts/experiments/scaffold_comparison_v1/heuristic/repair_report.md`
- `artifacts/experiments/scaffold_comparison_v1/deepagents/repair_report.md`

Interpretation:

This proves the repair-evaluation plumbing, patch artifact loop, DeepAgents adapter trace shape, model-planner JSON contract, provider/cost metadata plumbing, post-test repair outcome reporting, and trace-complexity measurement. It does not prove autonomous agent quality because current repair planners are deterministic or offline seeded-task baselines. Live package/model execution is tracked in separate calibration artifacts.

## Follow-up

Next step: refresh this comparison after a bounded live DeepAgents run.
