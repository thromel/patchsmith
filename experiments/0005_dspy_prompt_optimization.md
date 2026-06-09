# Experiment 0005: DSPy Prompt and Module Optimization

## Status

Planned

## Research question

Can structured and optimized language-model modules improve subtask quality compared with manually written prompts?

## Hypothesis

DSPy-style optimized modules will improve structured subtasks such as issue triage, fault localization, failure summarization, and risk review. They may be less directly useful for full patch generation.

## Candidate modules

| Module | Input | Output |
|---|---|---|
| IssueTriage | issue text, repo summary | issue type, symptoms, risk |
| FaultLocalization | issue, repo map, failing tests | candidate files and rationale |
| PatchPlan | issue, context | edit plan |
| FailureSummary | test output, diff | failure cause and next step |
| RiskReview | diff, tests | risk score and notes |

## Dataset

Initial dataset:

- seeded bugs with known touched files,
- saved run traces from baseline runs.

## Variants

| Variant | Description |
|---|---|
| manual_prompt | hand-written prompts |
| dspy_zero_shot | DSPy signatures without optimization |
| dspy_optimized | optimized modules using labeled examples |

## Metrics

Primary:

- fault localization top-k recall.

Secondary:

- patch-plan human score,
- failure-summary usefulness,
- reviewer score correlation with test success,
- token usage,
- downstream patch success.

## Result table

| Variant | Localization top-5 | Plan score | Review correlation | Avg tokens | Patch success | Notes |
|---|---:|---:|---:|---:|---:|---|
| manual_prompt | TBD | TBD | TBD | TBD | TBD |  |
| dspy_zero_shot | TBD | TBD | TBD | TBD | TBD |  |
| dspy_optimized | TBD | TBD | TBD | TBD | TBD |  |

## Decision rule

Adopt DSPy modules only for subtasks where optimization shows measurable improvement and does not make the system harder to debug.

## Follow-up

If DSPy improves localization but not patch success, combine it with the retrieval ablation analysis.
