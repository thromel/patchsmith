# Experiment 0004: Memory and Skill Registry Ablation

## Status

Planned

## Research question

Can episodic memory and gated reusable skills improve future repair runs without increasing regression risk?

## Hypothesis

Curated skills based on previous failure analysis will help repeated task families. Raw ungated reflections may hurt performance by introducing misleading assumptions.

## Dataset

Initial dataset:

- seeded bug families with repeated patterns,
- example families: import error, fixture mismatch, boundary condition bug, config mismatch.

## Variants

| Variant | Description |
|---|---|
| no_memory | no prior reflections or skills |
| raw_reflection | agent receives previous run reflections |
| gated_skills | only approved skills from offline eval are available |

## Metrics

Primary:

- success rate delta versus no memory.

Secondary:

- cost delta,
- latency delta,
- skill usage rate,
- accepted skill count,
- rejected skill count,
- regression rate,
- human approval score.

## Result table

| Variant | Success rate | Avg cost | Avg latency | Regression rate | Skill usage | Notes |
|---|---:|---:|---:|---:|---:|---|
| no_memory | TBD | TBD | TBD | TBD | NA |  |
| raw_reflection | TBD | TBD | TBD | TBD | TBD |  |
| gated_skills | TBD | TBD | TBD | TBD | TBD |  |

## Skill format

```json
{
  "skill_id": "pytest_fixture_debugging_v1",
  "name": "Inspect pytest fixtures before editing implementation",
  "applicability": ["pytest", "fixture", "test failure"],
  "strategy": "When a failure mentions a fixture, inspect fixture definitions and factories before editing production code.",
  "evidence": ["task_003", "task_007"],
  "status": "candidate"
}
```

## Approval rule

A skill can move from candidate to approved only if:

- it improves or preserves success rate on a validation subset,
- it does not increase regression rate,
- it does not bypass safety policy,
- it has human-readable rationale.

## Failure cases to inspect

- stale skills applied to unrelated repos,
- skills causing overfitting to seeded tasks,
- raw reflections causing confident wrong edits,
- increased cost without quality improvement.

## Decision rule

Use gated skills only if they improve repeated task families without harming general tasks.
