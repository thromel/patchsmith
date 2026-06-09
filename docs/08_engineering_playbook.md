# Engineering Playbook

## Status

Draft v0.1

## Purpose

This document defines the lean operating system for building PatchSmith Research. It should keep the project moving quickly without letting it drift into architecture soup.

## Development principles

1. Build vertical slices.
2. Prefer simple baselines before advanced research modes.
3. Every framework must sit behind an interface.
4. Every research feature must have an experiment plan.
5. Every safety-sensitive feature must update the threat model.
6. Every runtime feature must emit trace events.
7. Every portfolio claim must map to an artifact.

## The core loop

```text
Define -> Build -> Evaluate -> Document -> Decide
```

### Define

Write or update the smallest necessary design note.

### Build

Implement one vertical outcome.

### Evaluate

Run a smoke test, seeded task, or experiment.

### Document

Update README, relevant docs, and experiment reports.

### Decide

Continue, revise, or cut the feature.

## Work item categories

| Category | Required artifact |
|---|---|
| Product feature | PRD section or issue |
| Architecture decision | ADR |
| Research experiment | experiment plan |
| Safety-sensitive change | safety doc update |
| Schema change | data model update |
| Runtime behavior | trace event update |
| Portfolio change | README or demo update |

## Branching strategy

```text
main
  stable, demo-ready code

dev
  integration branch

feature/*
  product or infrastructure features

experiment/*
  research experiments and ablations

docs/*
  documentation-only changes
```

For a solo portfolio project, this can be simplified:

- `main` stays stable,
- short-lived feature branches are merged frequently,
- experiments can be tagged instead of permanently branched.

## Commit style

Use clear commit prefixes:

```text
feat: add LangGraph MVP repair loop
fix: handle sandbox command timeout
exp: run retrieval ablation v1
docs: add safety threat model
adr: accept runtime adapter boundary
test: add seeded bug task for import failure
```

## Definition of done

A feature is done when:

- code is implemented,
- tests pass,
- relevant docs are updated,
- traces/logging exist for runtime behavior,
- safety implications are reviewed,
- evaluation hook exists if the feature affects quality,
- README or demo is updated if it affects portfolio value.

## Review checklist

Before merging:

- [ ] Does this support the MVP, research plan, safety plan, or portfolio?
- [ ] Is there a simpler baseline?
- [ ] Is the framework isolated behind an interface?
- [ ] Are failures handled and reported?
- [ ] Are run artifacts preserved?
- [ ] Are cost and latency tracked where relevant?
- [ ] Does the change make the demo stronger?

## Weekly rhythm

### Day 1: Choose one vertical outcome

Examples:

- run one seeded bug end-to-end,
- add sandbox timeout enforcement,
- record retrieval metrics,
- produce first patch report.

### Days 2 to 4: Implement

Stay focused on the chosen outcome.

### Day 5: Evaluate

Run the relevant smoke test or experiment.

### Day 6: Document

Update docs and write the result.

### Day 7: Polish or rest

Avoid endless feature churn.

## Roadmap discipline

Each milestone must have:

- one user-visible outcome,
- one engineering artifact,
- one evaluation artifact.

Example:

| Milestone | User-visible outcome | Engineering artifact | Evaluation artifact |
|---|---|---|---|
| MVP Agent | issue-to-diff report | LangGraph runtime | 5 seeded bug runs |
| Advanced retrieval | retrieved context view | Code Context Graph | retrieval ablation |
| Patch search | candidate comparison | patch selector | success@k report |

## Framework adoption rule

Before adding a framework, answer:

1. What problem does it solve?
2. What simpler option was considered?
3. Where is the adapter boundary?
4. How will we evaluate whether it helps?
5. What is the removal plan if it does not help?

## Research feature rule

Before adding research complexity, define:

- hypothesis,
- baseline,
- dataset,
- metric,
- budget,
- expected decision.

No hypothesis, no experiment. Otherwise the project becomes a chandelier made of TODOs.

## Documentation rule

Documentation should make the next decision easier. It should not duplicate every line of code.

Update docs when:

- scope changes,
- architecture changes,
- safety model changes,
- data model changes,
- evaluation results change,
- public demo changes.

## Portfolio rule

Every week, ask:

> Would a recruiter or senior engineer understand why this project is impressive from the README and latest demo artifacts?

If not, polish communication before adding another feature.
