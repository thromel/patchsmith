# Risk Register

## Status

Draft v0.1

## Purpose

This document tracks major risks and mitigation plans. Update it whenever project scope, architecture, or execution model changes.

## Risk scoring

Use simple scoring:

- Probability: Low, Medium, High
- Impact: Low, Medium, High
- Status: Open, Mitigated, Accepted, Closed

## Risks

| ID | Risk | Probability | Impact | Status | Mitigation |
|---|---|---|---|---|---|
| R1 | Scope creep from too many frameworks | High | High | Open | Use runtime adapters and milestone gates |
| R2 | Unsafe execution of untrusted code | Medium | High | Open | Docker sandbox, command policy, no secrets |
| R3 | Repository setup failures dominate results | High | Medium | Open | Start with seeded suite and curated repos |
| R4 | Evaluation results are too weak for portfolio | Medium | Medium | Open | Emphasize honest ablations and failure analysis |
| R5 | Costs become too high | Medium | Medium | Open | Add budget configs, caching, cheaper models for subtasks |
| R6 | Agent traces become too complex to debug | Medium | Medium | Open | Structured trace schema and run reports |
| R7 | DeepAgents or other framework changes API | Medium | Medium | Open | Keep adapter boundaries |
| R8 | Patch success depends on lucky examples | Medium | High | Open | Use seeded suite and report aggregate metrics |
| R9 | Public demo cannot safely run arbitrary repos | Medium | High | Open | Use preselected demo repos or offline artifacts |
| R10 | Memory system creates bad priors | Medium | Medium | Open | Gate skills through offline evaluation and approval |

## Mitigation priorities

### Highest priority

- sandbox safety,
- lean MVP scope,
- reproducible evaluation,
- adapter boundaries.

### Medium priority

- hosted demo reliability,
- UI polish,
- local model serving.

### Lower priority

- broad language support,
- Kubernetes deployment,
- autonomous PR actions.

## Risk review cadence

Review this file at the end of each milestone.

For every open high-impact risk, record one mitigation action in the next milestone.
