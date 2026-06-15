# Evaluation Plan

## Status

Draft v0.1

## Evaluation philosophy

PatchSmith Research should be judged by evidence, not demonstration theater. Every major claim must be backed by a repeatable evaluation, a saved run artifact, or a clearly labeled qualitative example.

## Evaluation goals

Measure:

- repair correctness,
- retrieval quality,
- test feedback usefulness,
- cost,
- latency,
- safety behavior,
- traceability,
- failure modes.

## Evaluation levels

### Level 0: Smoke tests

Purpose:

Verify the system can run end-to-end without evaluating quality.

Example:

```text
toy repo -> seeded bug -> known test command -> patch attempt -> report generated
```

### Level 1: Seeded bug suite

Purpose:

Fast controlled evaluation for development.

Characteristics:

- small repos,
- known bugs,
- deterministic tests,
- known touched files,
- cheap to run in CI.

### Level 2: Hand-curated GitHub issue set

Purpose:

Portfolio-realistic demonstration.

Characteristics:

- public issues,
- manageable repositories,
- clear expected behavior,
- tests available or easy to write,
- human-readable results.

### Level 3: SWE-bench-style subset

Purpose:

Credible benchmark-style comparison.

Characteristics:

- fixed task definitions,
- expected patches or tests,
- standardized reporting,
- used after MVP is stable.

## Datasets

### Seeded bugs v1

Initial target:

- 10 small Python tasks,
- 5 unit-test failures,
- 3 edge-case logic bugs,
- 2 configuration or import bugs.

Each task should include:

- repository path or URL,
- base commit,
- issue text,
- failing test command,
- expected touched files,
- optional reference patch.

Validation gate:

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-dataset \
  --dataset evals/tasks/seeded_bugs_v1 \
  --output artifacts/experiments/seeded_dataset_validation_v1 \
  --json
```

The validation report must show zero invalid tasks before retrieval or repair metrics are used as Gate 1 evidence.

### Graph retrieval v1

Initial target:

- 3 retrieval-only Python tasks,
- issue text emphasizes failing test paths,
- expected source files are reachable through import or test/source graph edges,
- native keyword and hybrid lanes should retrieve the failing tests while `native_graph` should recover the source files.

Validation gate:

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-dataset \
  --dataset evals/tasks/graph_retrieval_v1 \
  --output artifacts/experiments/graph_dataset_validation_v1 \
  --json
```

This dataset supports graph-localization evidence only. Do not use it as patch-success evidence unless repair rules or model planners are explicitly evaluated against it.

### Curated issues v1

Initial target:

- 10 public GitHub issues,
- Python-first,
- repositories that install reliably,
- issues that can be validated with tests.

### Benchmark subset v1

Initial target:

- 10 to 25 benchmark tasks,
- focus on environment reproducibility,
- run only after local pipeline is stable.

## Metrics

### Task-level metrics

| Metric | Definition |
|---|---|
| Attempted tasks | Number of tasks started |
| Completed tasks | Number of tasks that produced final reports |
| Patch generated | Whether a diff was produced |
| Targeted tests passed | Whether targeted tests passed |
| Full tests passed | Whether full test suite passed |
| Resolved rate | Share of tasks judged solved |
| Regression rate | Share of tasks where existing tests regressed |
| Human acceptability | Manual review score for patch quality |

### Retrieval metrics

| Metric | Definition |
|---|---|
| Top-1 touched-file recall | Correct touched file appears as rank 1 |
| Top-3 touched-file recall | Correct touched file appears in top 3 |
| Top-5 touched-file recall | Correct touched file appears in top 5 |
| Context precision | Share of retrieved context that is relevant |
| Context token count | Number of tokens sent as context |

### Agent metrics

| Metric | Definition |
|---|---|
| Iteration count | Number of repair attempts |
| Tool calls | Number of tool calls per run |
| Failed tool calls | Tool calls that failed |
| Test runs | Number of test executions |
| Timeout rate | Share of runs hitting timeout |
| Unsafe command rejections | Commands rejected by policy |

### Cost and latency metrics

| Metric | Definition |
|---|---|
| Input tokens | Total prompt tokens |
| Output tokens | Total completion tokens |
| Estimated model cost | Cost calculated from provider pricing config |
| Wall-clock latency | Total run duration |
| Sandbox latency | Time spent executing commands |
| Cost per successful patch | Total cost divided by successful tasks |
| Attempted cost per validated task | Total model cost across evaluated attempts divided by validated tasks |
| Selected cost per validated task | Model cost for the retained best attempt per task divided by validated tasks |
| Attempted tokens per validated task | Total model tokens across evaluated attempts divided by validated tasks |
| Selected tokens per validated task | Model tokens for the retained best attempt per task divided by validated tasks |
| Max attempted task cost | Highest model cost observed for any attempted task |
| Max selected task cost | Highest model cost among retained selected attempts |
| Max attempted task tokens | Highest model token count observed for any attempted task |
| Max selected task tokens | Highest model token count among retained selected attempts |

### Safety metrics

| Metric | Definition |
|---|---|
| Policy rejection count | Number of rejected unsafe commands |
| External action attempts | Attempts to push, open PR, or call network |
| Sandbox failure count | Container-level failures |
| Prompt injection flags | Suspicious repo content detected |

## Experiment types

### Retrieval ablation

Compare:

- native keyword-only,
- native hybrid,
- native graph,
- ctxhelm CLI context broker,
- embeddings-only,
- future Code Context Graph reranking.

Primary metric:

- top-5 touched-file recall.

Secondary metrics:

- patch success,
- context token count,
- cost.

### Scaffold comparison

Compare:

- Agentless,
- Heuristic baseline,
- DeepAgents.

Primary metric:

- resolved rate.

Secondary metrics:

- cost,
- latency,
- trace complexity,
- failure modes.

### Patch search ablation

Compare:

- one candidate,
- three candidates,
- five candidates,
- five candidates plus failure repair.

Primary metric:

- success@k.

Secondary metrics:

- cost per successful patch,
- latency,
- selected-candidate correctness.

### Memory ablation

Compare:

- no memory,
- raw reflections,
- gated approved skills.

Primary metric:

- before/after success delta.

Secondary metrics:

- regression caused by skill use,
- cost delta.

### DSPy optimization experiment

Compare:

- manually written prompts,
- DSPy-optimized modules.

Primary metric:

- subtask quality, especially localization.

Secondary metrics:

- token count,
- downstream patch success.

## Reporting template

Each experiment should produce:

```text
Experiment name
Date
Commit hash
Dataset version
Model configuration
Runtime configuration
Retrieval configuration
Metrics table
Failure cases
Decision
Next action
```

## Evaluation gates

### Gate 1: MVP readiness

Required:

- 5 seeded tasks run end-to-end,
- every run produces a report,
- no host safety violations,
- logs and traces available.

### Gate 2: Research readiness

Required:

- at least 10 seeded tasks,
- baseline runtime implemented,
- DeepAgents runtime implemented,
- retrieval metrics implemented.

### Gate 3: Portfolio readiness

Required:

- at least 3 experiment reports,
- final demo issue selected,
- README has summary metrics,
- failure analysis published.

## Honest reporting rules

- Do not remove failed runs from aggregate results unless the exclusion rule was defined before the run.
- Separate infrastructure failures from model failures.
- Record exact configuration for every experiment.
- Report cost and latency next to success rates.
- Include at least three failure examples in the final report.

## Initial evaluation table

| Experiment | Dataset | Runtime | Retrieval | Candidate count | Success | Avg cost | Avg latency | Notes |
|---|---|---|---|---:|---:|---:|---:|---|
| baseline_v0 | seeded_bugs_v1 | agentless | keyword | 1 | TBD | TBD | TBD | First baseline |
| deepagents_v0 | seeded_bugs_v1 | deepagents | hybrid_v0 | 1 | TBD | TBD | TBD | MVP runtime |
| patch_search_v0 | seeded_bugs_v1 | deepagents | hybrid_v0 | 3 | TBD | TBD | TBD | Research mode |
