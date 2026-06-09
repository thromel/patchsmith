# Experiment 0003: Patch Search Ablation

## Status

Executed deterministic baseline; model-diverse candidates still planned.

## Research question

Does generating and testing multiple patch candidates improve repair success compared with a single patch attempt?

## Hypothesis

Multi-candidate patch search will improve success@k and final selected-patch success, but it will increase cost and latency. It will be most useful on tasks where retrieval includes multiple plausible localization paths.

## Dataset

Initial dataset:

- `seeded_bugs_v1`,
- tasks that are not trivially solved by baseline.

Later dataset:

- curated GitHub issues,
- benchmark subset.

## Variants

| Variant | Candidate count | Repair iterations | Selection method |
|---|---:|---:|---|
| candidates_1 | 1 | 1 | first passing targeted test result |
| candidates_3 | 3 | 1 | first passing targeted test result |
| candidates_5 | 5 | 1 | test result plus risk score |
| candidates_5_repair | 5 | 2 | test result plus failure repair |

## Fixed variables

- same runtime,
- same retrieval,
- same model,
- same sandbox,
- same test command.

## Metrics

Primary:

- success@k,
- selected candidate success.

Secondary:

- average cost,
- average latency,
- number of test runs,
- regression rate,
- diff size,
- reviewer risk score.

## Result table

Latest command:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-patch-search \
  --dataset evals/tasks/seeded_bugs_v1 \
  --candidate-count 1 \
  --candidate-count 3 \
  --context-provider native_hybrid \
  --output artifacts/experiments/patch_search_eval_v1 \
  --json
```

Latest artifact:

- `artifacts/experiments/patch_search_eval_v1/patch_search_report.md`

| Variant | Success@1 | Success@3 | Success@5 | Selected success | Avg cost | Avg latency | Avg test runs | Regression rate | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| candidates_1 | 1.00 | NA | NA | 1.00 | $0.00 | 442ms | 1.0 | TBD | deterministic primary heuristic candidate succeeds on all seeded tasks |
| candidates_3 | 1.00 | 1.00 | NA | 1.00 | $0.00 | 1371ms | 3.0 | TBD | adds no-op and deletion control candidates; no success improvement on easy seeded suite |
| candidates_5 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |  |
| candidates_5_repair | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |  |

## Candidate strategies

- minimal patch,
- test-driven patch,
- alternative localization patch,
- architecture-aware patch,
- stronger-model escalation.

## Selection signals

- targeted tests passed,
- full tests passed,
- static analysis passed,
- diff size,
- reviewer risk score,
- failure-output consistency.

## Failure cases to inspect

- all candidates fail for same reason,
- selected candidate passes visible tests but is risky,
- expensive candidate generation with no quality gain,
- selector prefers small but incorrect patch,
- test suite is too weak to distinguish candidates.

## Decision rule

Use patch search as a research and demo mode if it improves success enough to justify cost. Keep single-candidate mode as default for low-budget runs.

Current deterministic-baseline decision:

Keep single-candidate mode as the default on `seeded_bugs_v1`. Three-candidate deterministic search validates candidate isolation and selection plumbing, but it triples test runs and latency without improving success because the primary heuristic candidate already solves every task. The next useful patch-search experiment needs harder tasks or genuinely diverse model/planner candidates.
