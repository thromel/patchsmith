# ADR 0003: Put Frameworks Behind Runtime Adapters

## Status

Accepted

## Context

PatchSmith Research should include industry-relevant frameworks and research-oriented scaffolds. Candidate runtimes include LangGraph, DeepAgents, OpenAI Agents SDK, Agentless baseline, and tree-search mode.

Without an adapter boundary, the project can become tightly coupled to one framework and difficult to evaluate or change.

## Decision

Define a common `AgentRuntime` interface and implement each framework as an adapter.

```python
class AgentRuntime:
    async def run(self, task: AgentTask) -> AgentResult:
        ...
```

Supported runtime implementations:

- `LangGraphRuntime`,
- `DeepAgentsRuntime`,
- `OpenAIAgentsRuntime`,
- `AgentlessRuntime`,
- `TreeSearchRuntime`.

## Consequences

### Positive

- Enables fair scaffold comparison.
- Reduces lock-in.
- Keeps domain models clean.
- Allows experiments without rewriting core systems.

### Negative

- Requires careful interface design.
- Some framework-specific features may not map cleanly.
- Adapter layer adds upfront complexity.

## Alternatives considered

### Single-framework architecture

Rejected because scaffold comparison is a core research goal.

### Framework-free architecture

Rejected because the project also needs to demonstrate industry-relevant agent tooling.

## Guardrail

Framework-specific objects must not cross into storage, evaluation, or UI layers. Store normalized traces and results.
