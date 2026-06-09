# ADR 0006: Use ctxhelm as a pluggable context broker adapter

## Status

Accepted

## Context

PatchSmith Research needs strong repository context before an agent edits files. Native retrieval will eventually include keyword search, embeddings, symbol extraction, graph expansion, reranking, and related-test detection. Building all of that before the first credible repair loop would slow the project.

`ctxhelm` provides a local-first, read-only context compiler and MCP broker for coding agents. It can produce task-conditioned context plans, target files, related tests, dependency/co-change hints, validation commands, and budgeted context packs. That overlaps with PatchSmith's retrieval/context layer, but not with patch generation, sandbox execution, or evaluation.

## Decision

Integrate `ctxhelm` as a pluggable `ContextBroker` implementation.

Initial implementation:

- `CtxhelmCliBroker` using the local CLI and JSON inspector export where possible.
- `CtxhelmMcpBroker` after the CLI proof works.
- `PatchSmithNativeBroker` retained as a fallback and ablation baseline.

PatchSmith will not expose ctxhelm directly to agent nodes. All ctxhelm output will be normalized into internal PatchSmith contracts.

## Consequences

### Positive

- Faster path to a credible issue-to-context-to-patch MVP.
- Strong industry relevance through MCP-compatible context brokering.
- Research value through direct comparison against native retrieval and graph retrieval.
- Better safety posture because ctxhelm is read-only and source-free by default in reports.
- Better demo quality because target files, related tests, and context packs are inspectable.

### Negative

- Adds an external binary/runtime dependency.
- Requires version pinning and contract tests.
- May overlap with PatchSmith's own Code Context Graph work.
- Could hide retrieval learning if used as a crutch instead of an eval lane.

## Guardrails

- Keep ctxhelm behind the `ContextBroker` interface.
- Record ctxhelm version and doctor output for every reproducible eval run.
- Treat all returned paths and commands as untrusted until validated.
- Maintain native retrieval as a baseline.
- Do not let ctxhelm own editing, test execution, or patch selection.

## Alternatives considered

### Build native retrieval first

Rejected as the only path because it delays the first complete repair loop. Still retained as a research lane.

### Use ctxhelm as the sole retrieval system

Rejected because PatchSmith needs its own research substrate for ablations, graph retrieval, failure-conditioned re-retrieval, and benchmark reporting.

### Expose ctxhelm tools directly to agents

Rejected because it creates tool-surface coupling and weakens observability. Agents should consume normalized context bundles through PatchSmith.

## Reversal criteria

Revisit this decision if:

- ctxhelm output becomes unstable across releases,
- the adapter creates more maintenance burden than value,
- native retrieval outperforms ctxhelm consistently under equal cost,
- source-free/safety guarantees cannot be enforced in PatchSmith reports.
