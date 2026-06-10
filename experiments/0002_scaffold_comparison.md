# Experiment 0002: Agent Scaffold Comparison

## Status

Aggregate local scaffold comparison complete; live model-backed scaffold comparison still planned.

## Research question

Which agent scaffold provides the best tradeoff between repair success, cost, latency, and debuggability?

## Hypothesis

The Agentless baseline will be competitive on simple localized bugs. LangGraph will provide the best MVP balance of control and observability. DeepAgents or tree-search modes may help harder tasks but increase cost and trace complexity.

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
| langgraph | stateful repair loop |
| deepagents | multi-agent high-level scaffold |
| openai_agents | structured tool and handoff runtime |
| tree_search | research mode with search over actions or plans |

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
| langgraph | 1.00 | 1.00 | n/a | 512ms | 15.0 | 6.0 | 0 | 1.0 | 5.0 | deterministic planner inside LangGraph graph |
| langgraph_fake_model | 1.00 | 1.00 | 0.00 | 482ms | 15.0 | 6.0 | 0 | 1.0 | 5.0 | offline JSON model-planner contract; no live provider |
| deepagents | 1.00 | 1.00 | n/a | 465ms | 15.0 | 6.0 | 0 | 0.0 | 5.0 | dependency-gated adapter in offline compatibility mode; no live DeepAgents package/model execution |
| deepagents_live | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | install optional extra and configure model provider before running |
| openai_agents | 1.00 | 1.00 | n/a | 466ms | 16.0 | 7.0 | 0 | 0.0 | 5.0 | dependency-gated OpenAI Agents SDK adapter in offline compatibility mode; no live Agents model execution |
| tree_search | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |  |

## Qualitative analysis

For each scaffold, inspect:

- how easy failures are to debug,
- whether the scaffold produces unnecessary tool calls,
- whether planning improves edits,
- whether retry logic improves or worsens results,
- whether the trace is readable.

## Decision rule

Use LangGraph as the default runtime unless another scaffold demonstrates clear quality gains without unacceptable cost or complexity.

## Initial smoke result

Date: 2026-06-10

Aggregate command:

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

Aggregate artifacts:

- `artifacts/experiments/scaffold_comparison_v1/scaffold_report.md`
- `artifacts/experiments/scaffold_comparison_v1/scaffold_results.csv`
- `artifacts/experiments/scaffold_comparison_v1/scaffold_results.json`

Aggregate result:

- scaffold count: 6,
- agentless patch generated rate: 0.00,
- heuristic, LangGraph heuristic, LangGraph fake-model, DeepAgents adapter, and OpenAI Agents adapter targeted test pass rate: 1.00,
- LangGraph variants expose 15.0 average trace events, 6.0 average runtime nodes, and 1.0 retry-decision events per task,
- OpenAI Agents adapter exposes 16.0 average trace events and 7.0 average runtime nodes per task,
- offline fake-model provider: `offline_fake_model`,
- total model cost: $0.00.

Nested repair reports:

- `artifacts/experiments/scaffold_comparison_v1/agentless/repair_report.md`
- `artifacts/experiments/scaffold_comparison_v1/heuristic/repair_report.md`
- `artifacts/experiments/scaffold_comparison_v1/langgraph/repair_report.md`
- `artifacts/experiments/scaffold_comparison_v1/langgraph_fake_model/repair_report.md`
- `artifacts/experiments/scaffold_comparison_v1/deepagents/repair_report.md`
- `artifacts/experiments/scaffold_comparison_v1/openai_agents/repair_report.md`

Interpretation:

This proves the repair-evaluation plumbing, patch artifact loop, LangGraph orchestration trace shape including `analyze` and `retry`, DeepAgents adapter trace shape, OpenAI Agents SDK adapter trace shape, model-planner JSON contract, provider/cost metadata plumbing, post-test repair outcome reporting, and trace-complexity measurement. It does not prove autonomous agent quality because current repair planners are deterministic or offline seeded-task baselines. The current DeepAgents and OpenAI Agents rows are adapter compatibility evidence; live package/model execution remains a follow-up.

## Follow-up

If DeepAgents performs better but is harder to control, keep it as research mode rather than MVP default.
