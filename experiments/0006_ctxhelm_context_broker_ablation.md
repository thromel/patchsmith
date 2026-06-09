# Experiment 0006: ctxhelm Context Broker Ablation

## Status

Initial 10-task retrieval smoke run complete; full end-to-end ablation still planned.

## Purpose

Measure whether using ctxhelm as a context broker improves fault localization, related-test discovery, patch success, cost, and latency compared with PatchSmith-native retrieval strategies.

## Hypothesis

ctxhelm will improve early-stage PatchSmith performance by producing better target-file and related-test suggestions than a naive keyword baseline. A hybrid lane that uses ctxhelm seeds plus PatchSmith Code Context Graph expansion/reranking should perform best on repository-level bug-fix tasks.

## Research question

> Does a local-first read-only context broker improve real issue-to-patch outcomes compared with native retrieval under equal model, runtime, and sandbox conditions?

## Treatment lanes

| Lane | Description |
|---|---|
| `native_keyword` | PatchSmith keyword/BM25 baseline |
| `native_hybrid` | PatchSmith keyword + path + symbol baseline |
| `ctxhelm_cli` | ctxhelm CLI context broker only |
| `ctxhelm_mcp` | ctxhelm MCP context broker only |
| `ctxhelm_plus_ccg` | ctxhelm seeds + PatchSmith Code Context Graph expansion/reranking |
| `ctxhelm_plus_patch_search` | ctxhelm context + multi-candidate patch search |

## Controlled variables

- same repository snapshot,
- same issue text,
- same model configuration,
- same LangGraph repair loop,
- same sandbox configuration,
- same maximum iterations,
- same test timeout,
- same context budget class where possible.

## Task set

Start with:

- 10 seeded bugs from the custom suite,
- 5 real public GitHub issues manually curated for reproducibility,
- optional SWE-bench Lite/Verified subset once the runner is stable.

## Metrics

### Retrieval metrics

- top-1 touched-file recall,
- top-3 touched-file recall,
- top-5 touched-file recall,
- retrieval target coverage,
- related-test recall,
- validation-command usefulness,
- context token budget used,
- false-context rate.

### End-to-end metrics

- patch success rate,
- regression rate,
- first-pass success,
- average iterations,
- average sandbox test runs,
- cost per attempted run,
- cost per successful patch,
- latency per attempted run,
- failure category distribution.

### Safety/privacy metrics

- source-free report conformance,
- invalid path rejection count,
- unsafe validation command rejection count,
- ctxhelm fallback count,
- source-bearing artifact retention compliance.

## Procedure

1. Pin ctxhelm version.
2. Record `ctxhelm --version`, `ctxhelm --help`, and `ctxhelm doctor --repo` artifacts.
3. Run each task under every lane.
4. Store normalized `ContextBundle` output for each run.
5. Execute the same repair loop and sandbox policy.
6. Record patch, tests, trace, cost, latency, and final verdict.
7. Generate aggregate tables and per-task failure notes.

## Success threshold

The ctxhelm integration is worth keeping as a first-class provider if at least one ctxhelm lane shows:

- no source-free contract violations,
- lower or equal infrastructure failure rate than native retrieval,
- improved top-5 touched-file recall over `native_keyword`,
- improved related-test recall over `native_keyword`,
- equal or improved patch success rate under acceptable cost increase.

## Analysis plan

Report:

- aggregate table by lane,
- per-task winner/loser notes,
- examples where ctxhelm helped,
- examples where ctxhelm missed target files,
- cost/latency trade-off,
- whether ctxhelm should be default, optional, or research-only.

## Expected result format

```markdown
| Lane | Top-5 target recall | Related-test recall | Patch success | Avg cost | Avg latency | Notes |
|---|---:|---:|---:|---:|---:|---|
| native_keyword | TBD | TBD | TBD | TBD | TBD | baseline |
| native_hybrid | TBD | TBD | TBD | TBD | TBD | native advanced |
| ctxhelm_cli | TBD | TBD | TBD | TBD | TBD | broker baseline |
| ctxhelm_plus_ccg | TBD | TBD | TBD | TBD | TBD | hybrid research |
```

## Initial smoke result

Date: 2026-06-09

Dataset:

- `evals/tasks/seeded_bugs_v1`
- task count: 10

Command:

```bash
PYTHONPATH=src python3 -m patchsmith.cli eval-retrieval \
  --dataset evals/tasks/seeded_bugs_v1 \
  --context-provider native \
  --context-provider native_hybrid \
  --context-provider ctxhelm_cli \
  --output artifacts/experiments/retrieval_eval_v1 \
  --json
```

Artifacts:

- `artifacts/experiments/retrieval_eval_v1/report.md`
- `artifacts/experiments/retrieval_eval_v1/results.csv`
- `artifacts/experiments/retrieval_eval_v1/results.json`
- `artifacts/experiments/retrieval_eval_v1/summary.json`

Smoke result:

| Lane | Task count | Top-1 target recall | Top-5 target recall | Related-test recall | Source-free violations | Notes |
|---|---:|---:|---:|---:|---:|---|
| native | 10 | 0.80 | 1.00 | 1.00 | 0 | keyword baseline over-ranked tests on two tasks |
| native_hybrid | 10 | 1.00 | 1.00 | 1.00 | 0 | path and symbol scoring fixes the observed native top-1 misses |
| ctxhelm_cli | 10 | 1.00 | 1.00 | 1.00 | 0 | ctxhelm 2.4.0 CLI broker on seeded smoke tasks |

Decision:

This proves the evaluation runner and context-broker lane wiring, not end-to-end patch success. The first signal is that `native_hybrid` and `ctxhelm_cli` improve top-1 localization over naive keyword on this small suite, while all lanes reach top-5 recall. Continue by adding harder localization cases and then measuring whether localization changes improve patch success.

## Failure analysis categories

- broker unavailable,
- stale inventory,
- target file absent from plan,
- related test absent,
- invalid suggested command,
- context too broad,
- context too narrow,
- agent ignored broker evidence,
- patch generated but tests failed,
- sandbox/infrastructure failure.
