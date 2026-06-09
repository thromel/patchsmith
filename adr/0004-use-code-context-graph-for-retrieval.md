# ADR 0004: Use Code Context Graph for Advanced Retrieval

## Status

Accepted for research mode

## Context

Basic retrieval over code often misses relationships that matter for software repair: imports, tests, fixtures, call relationships, stack traces, and symbol definitions. Embeddings alone can retrieve semantically similar text while missing exact code relationships.

PatchSmith Research needs a retrieval system that is both practical and research-oriented.

## Decision

Implement a Code Context Graph as the advanced retrieval strategy after the MVP baseline.

The graph will include:

- files,
- symbols,
- imports,
- tests,
- fixtures,
- stack traces,
- issue mentions,
- patch candidates.

Retrieval will combine:

- keyword search,
- embeddings,
- symbol matching,
- graph expansion,
- reranking.

## Consequences

### Positive

- Stronger repository understanding.
- Better fault-localization research surface.
- Enables retrieval ablation experiments.
- Differentiates the project from generic RAG.

### Negative

- More indexing complexity.
- Language support becomes harder.
- Graph quality may be noisy.
- Requires careful evaluation to prove value.

## Alternatives considered

### Embeddings-only retrieval

Simple, but too shallow for code repair.

### Keyword-only retrieval

Fast and interpretable, but misses semantic matches.

### Full LSP integration first

Powerful, but too heavy for MVP.

## Guardrail

The graph must be introduced after keyword and hybrid retrieval baselines exist. No advanced retrieval without ablation metrics.
