# Graph Retrieval v1

This dataset contains retrieval-only Python localization tasks designed to test graph expansion from failing test files to imported source files.

The issue reports intentionally emphasize failing test paths and omit source module names. The expected source file should be recovered through deterministic file, import, symbol, and test/source graph edges.

Use this dataset for retrieval evaluation, not repair success claims:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-retrieval \
  --dataset evals/tasks/graph_retrieval_v1 \
  --context-provider native \
  --context-provider native_hybrid \
  --context-provider native_graph \
  --output artifacts/experiments/graph_retrieval_eval_v1 \
  --json
```
