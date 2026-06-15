# ADR 0003: Keep DeepAgents Behind the Runtime Boundary

## Status

Accepted

## Context

PatchSmith Research now standardizes on DeepAgents as the only production agent framework. Deterministic and agentless baselines remain useful for evaluation, but they are controls rather than competing agent frameworks.

Without an adapter boundary, the project can become tightly coupled to one framework and difficult to evaluate or change.

## Decision

Keep the common `AgentRuntime` interface and implement DeepAgents behind that boundary.

```python
class AgentRuntime:
    async def run(self, task: AgentTask) -> AgentResult:
        ...
```

Supported runtime implementations:

- `DeepAgentsRuntime`,
- `HeuristicRuntime`,
- `AgentlessRuntime`.

## Consequences

### Positive

- Keeps DeepAgents isolated from domain models.
- Preserves fair baseline comparison.
- Keeps domain models clean.
- Lets PatchSmith expose harness-owned artifacts, such as `/.patchsmith/AGENTS.md`,
  repair skills, and `/.patchsmith/source-hints.md`, without leaking framework
  objects into storage or evaluation code.
- Allows experiments without rewriting core systems.

### Negative

- Requires careful interface design.
- Some DeepAgents-specific features may not map cleanly.
- Adapter layer adds upfront complexity.

## Alternatives considered

### Framework-free architecture

Rejected because the project also needs to demonstrate industry-relevant agent tooling.

## Guardrail

Framework-specific objects must not cross into storage, evaluation, or UI layers. Store normalized traces and results.
