# ADR 0005: Use Multi-Candidate Patch Search as Research Mode

## Status

Accepted for research mode

## Context

A single agent trajectory can fail due to bad localization, brittle reasoning, or unlucky patch generation. Test-time search can generate multiple candidate patches, execute tests, and select a stronger candidate using evidence.

However, multi-candidate search is more expensive and slower than single-candidate repair.

## Decision

Implement multi-candidate patch search as an optional research mode, not the MVP default.

Candidate strategies may include:

- conservative minimal fix,
- test-driven fix,
- alternative localization fix,
- architecture-aware fix,
- stronger-model escalation.

Selection signals:

- targeted tests,
- full tests,
- static analysis,
- diff size,
- reviewer risk score,
- generated distinguishing tests where available.

## Consequences

### Positive

- Strong research differentiation.
- Enables success@k evaluation.
- Makes execution feedback central.
- Provides compelling demo material.

### Negative

- Higher model cost.
- Higher sandbox cost.
- More complex artifact management.
- Candidate selection may be noisy.

## Alternatives considered

### Single trajectory only

Simpler and cheaper, but less research-oriented.

### Always-on patch search

Rejected because it is too expensive for MVP and may slow iteration.

## Guardrail

Patch search must have budget controls:

- max candidates,
- max iterations per candidate,
- max test runs,
- max cost,
- max wall-clock time.
