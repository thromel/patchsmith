# Experiment 0001: Retrieval Ablation

## Status

Executed seeded v1; broader lanes still planned.

## Research question

Does advanced retrieval improve fault localization and patch success compared with simpler retrieval methods?

## Hypothesis

Hybrid retrieval and Code Context Graph retrieval will improve top-k touched-file recall compared with keyword-only or embeddings-only retrieval. Better retrieval should improve patch success, especially when the issue requires understanding tests, imports, or symbols.

## Dataset

Initial dataset:

- `seeded_bugs_v1`,
- 10 controlled tasks,
- known expected touched files.

Later dataset:

- curated GitHub issues,
- benchmark subset.

## Variants

| Variant | Description |
|---|---|
| native | lexical search only |
| native_hybrid | lexical search plus Python symbol matching, source-over-test ranking, direct path hints, and traceback path/symbol hints |
| native_graph | native_hybrid plus Python Code Context Graph nodes and import/test graph expansion |
| ctxhelm_cli | ctxhelm CLI context broker lane |
| embeddings_only | future vector search lane |
| code_context_graph_full | future multi-language graph expansion and learned or model reranking lane |

## Fixed variables

- same model,
- same runtime,
- same max iterations,
- same dataset,
- same context token budget where possible.

## Metrics

Primary:

- top-5 touched-file recall.

Secondary:

- top-1 touched-file recall,
- top-3 touched-file recall,
- context precision,
- context token count,
- patch success rate,
- cost,
- latency.

## Result table

Latest command:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-retrieval \
  --dataset evals/tasks/seeded_bugs_v1 \
  --context-provider native \
  --context-provider native_hybrid \
  --context-provider native_graph \
  --context-provider ctxhelm_cli \
  --output artifacts/experiments/retrieval_eval_v1 \
  --json
```

Latest artifact:

- `artifacts/experiments/retrieval_eval_v1/report.md`

| Variant | Top-1 recall | Top-3 recall | Top-5 recall | Related test recall | Patch success | Avg context tokens | Avg cost | Avg latency | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| native | 0.80 | 1.00 | 1.00 | 1.00 | n/a | 37 | $0.00 | 4ms | Keyword baseline; test files outranked source files on task 002 and task 006. |
| native_hybrid | 1.00 | 1.00 | 1.00 | 1.00 | n/a | 35 | $0.00 | 3ms | Symbol/path/traceback hybrid lane; source file ranked first on all seeded tasks. |
| native_graph | 1.00 | 1.00 | 1.00 | 1.00 | n/a | 35 | $0.00 | 4ms | Python graph v0; file, symbol, import, and test edges match hybrid on this suite. |
| ctxhelm_cli | 1.00 | 1.00 | 1.00 | 1.00 | n/a | 54 | $0.00 | 141ms | External context broker lane; no fallbacks or source-free violations in this run. |
| embeddings_only | TBD | TBD | TBD | TBD | n/a | TBD | TBD | TBD | Future lane. |
| code_context_graph_full | TBD | TBD | TBD | TBD | n/a | TBD | TBD | TBD | Future lane. |

Patch success is not measured in this experiment. Use `eval-repair` artifacts for repair success and cost. Average context tokens are approximate and derived from packed excerpt characters rather than a model-specific tokenizer.

## Graph-specific stress result

The `graph_retrieval_v1` dataset contains three retrieval-only tasks where the issue report names a failing test path but omits the source module. The target source file is reachable through Python import and test/source graph edges.

Latest command:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-retrieval \
  --dataset evals/tasks/graph_retrieval_v1 \
  --context-provider native \
  --context-provider native_hybrid \
  --context-provider native_graph \
  --output artifacts/experiments/graph_retrieval_eval_v1 \
  --json
```

Latest artifacts:

- `artifacts/experiments/graph_dataset_validation_v1/validation_report.md`,
- `artifacts/experiments/graph_retrieval_eval_v1/report.md`.

| Variant | Top-1 recall | Top-3 recall | Top-5 recall | Related test recall | Avg context tokens | Avg latency | Notes |
|---|---:|---:|---:|---:|---:|---:|---|
| native | 0.00 | 0.00 | 0.00 | 1.00 | 22 | 8ms | Retrieves the mentioned test file but not the imported source file. |
| native_hybrid | 0.00 | 0.00 | 0.00 | 1.00 | 22 | 4ms | Path and symbol boosts stay on the failing test file. |
| native_graph | 1.00 | 1.00 | 1.00 | 1.00 | 47 | 5ms | Expands from failing tests to imported source files and ranks source first. |

## Failure cases to inspect

- issue text does not mention relevant code terms,
- retrieved file is related but not sufficient,
- correct file retrieved but context snippet misses important lines,
- embeddings retrieve conceptually similar but wrong files,
- graph expansion adds too much noise.

## Decision rule

Adopt Code Context Graph retrieval as default only if it improves top-5 touched-file recall or patch success enough to justify added complexity and cost.

Current seeded-suite decision:

Keep `native_hybrid` as the default low-cost native retrieval lane for repair experiments until graph-specific retrieval wins translate into patch-success wins or the repair suite includes test-path-only issues. `native_graph` now runs as the Code Context Graph v0 lane: it matches `native_hybrid` plus `ctxhelm_cli` top-k recall on the controlled 10-task suite and beats `native_hybrid` on the three-task graph-specific retrieval suite. Keep `ctxhelm_cli` as the external context-broker comparison lane.

## Follow-up

If graph retrieval improves recall but not patch success, investigate context packing and patch planning.
