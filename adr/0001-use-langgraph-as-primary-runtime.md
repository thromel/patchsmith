# ADR 0001: Use LangGraph as the Primary Runtime

## Status

Accepted

## Context

PatchSmith Research requires long-running, stateful workflows with multiple steps: issue triage, retrieval, planning, editing, test execution, failure analysis, retries, review, and reporting.

A plain loop would be fast to start but difficult to trace, extend, and compare against other runtime scaffolds. The project also needs to demonstrate industry-relevant agent orchestration.

## Decision

Use LangGraph as the primary production runtime for the MVP repair loop.

The MVP graph will include:

```text
triage -> retrieve -> plan -> edit -> test -> analyze -> review -> report
```

## Consequences

### Positive

- Clear state-machine structure for agent workflows.
- Good fit for retries and branching.
- Strong portfolio signal for agent orchestration.
- Easier to instrument each node.
- Enables later comparison with DeepAgents and other runtimes.

### Negative

- Adds framework dependency.
- Requires learning and maintaining graph-specific state design.
- Could create lock-in if not isolated.

## Guardrail

LangGraph must sit behind the `AgentRuntime` interface. Domain models should not depend directly on LangGraph-specific types.

## Alternatives considered

### Plain Python loop

Pros:

- simplest to implement,
- minimal dependency.

Cons:

- harder to visualize,
- less suitable for runtime comparison,
- weaker portfolio signal.

### DeepAgents as primary runtime

Pros:

- higher-level agent features,
- useful for research experiments.

Cons:

- too much abstraction for MVP,
- less control over core repair loop.

### OpenAI Agents SDK as primary runtime

Pros:

- strong tool and guardrail abstractions,
- useful tracing model.

Cons:

- less ideal as the main framework comparison spine for this project.

## Follow-up

Create runtime adapters so additional frameworks can be added without rewriting the application.
