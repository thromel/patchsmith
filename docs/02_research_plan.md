# Research Plan

## Status

Draft v0.1

## Research thesis

Real-world AI software-maintenance performance depends on more than model quality. It depends on retrieval, repository representation, agent scaffold design, sandbox feedback, test-time search, cost control, and evaluation discipline.

PatchSmith Research will study those factors through controlled comparisons.

## Research posture

This project is an applied research engineering system. It does not need to claim state-of-the-art leaderboard performance. It should instead demonstrate:

- clear research questions,
- honest baselines,
- reproducible experiments,
- meaningful metrics,
- failure analysis,
- practical engineering constraints.

## Research questions

### RQ1: Retrieval quality

Does Code Context Graph retrieval improve fault localization and patch success compared with embeddings-only and keyword-only retrieval?

Hypothesis:

A graph-augmented retrieval pipeline that combines symbols, imports, tests, stack traces, keyword search, embeddings, and reranking will improve touched-file recall and downstream patch success.

Metrics:

- top-1 touched-file recall,
- top-3 touched-file recall,
- top-5 touched-file recall,
- context precision,
- patch success rate,
- cost per run.

### RQ2: Agent scaffold design

How do different agent scaffolds compare on software repair tasks?

Scaffolds:

- Agentless baseline,
- LangGraph single repair loop,
- DeepAgents multi-agent scaffold,
- OpenAI Agents SDK runtime,
- tree-search research mode.

Hypothesis:

More complex scaffolds will improve hard-task success but may increase cost, latency, and trace complexity. Simpler scaffolds may perform competitively on localized bugs.

Metrics:

- resolved rate,
- average cost,
- average latency,
- average iterations,
- failed tool calls,
- timeout rate,
- trace complexity,
- qualitative debuggability score.

### RQ3: Test-time patch search

Does multi-candidate patch search improve success compared with a single repair trajectory?

Hypothesis:

Generating multiple candidate patches and selecting using sandboxed test feedback will improve success at the cost of higher latency and token usage.

Metrics:

- success@1,
- success@k,
- selected-candidate correctness,
- average test runs,
- cost per successful patch,
- regression rate.

### RQ4: Execution feedback

How much does sandboxed execution feedback improve patch quality?

Hypothesis:

Test feedback will improve patch quality substantially, especially when failure analysis is used to guide retries. However, noisy or incomplete tests may create false confidence.

Metrics:

- success without tests,
- success with targeted tests,
- success with full tests,
- false positive patch rate,
- regression rate.

### RQ5: Episodic memory and reusable skills

Can failed and successful runs generate reusable debugging skills that improve future performance?

Hypothesis:

Curated memory can improve recurring task families, but ungated memory can introduce misleading priors.

Metrics:

- before/after success rate,
- accepted skill count,
- rejected skill count,
- regression caused by skill usage,
- human approval rate,
- average cost delta.

### RQ6: Prompt/module optimization

Can DSPy-optimized modules improve issue triage, localization, patch planning, or review scoring compared with manually written prompts?

Hypothesis:

Optimized modules can improve structured subtasks like localization and risk review more reliably than free-form patch generation.

Metrics:

- localization F1,
- reviewer score correlation with test success,
- patch-plan usefulness rating,
- prompt token usage,
- success rate impact.

## Experimental principles

1. Always compare against a simple baseline.
2. Keep model choice constant when comparing scaffolds.
3. Keep scaffold constant when comparing models.
4. Report cost and latency with accuracy metrics.
5. Preserve failed examples.
6. Prefer small reproducible experiments over large vague claims.
7. Separate dev set from final reporting set.

## Evaluation datasets

### Seeded bug suite

A controlled suite of small repositories with known injected bugs.

Use for:

- fast iteration,
- CI-friendly tests,
- debugging the framework,
- evaluating simple failure modes.

### Hand-curated GitHub issue set

A curated set of public issues from small and medium repositories.

Use for:

- realistic product demo,
- qualitative failure analysis,
- portfolio examples.

### SWE-bench-style subset

A small subset of benchmark tasks used after the system has a stable baseline.

Use for:

- credible comparison,
- research report,
- advanced evaluation.

## Experiment matrix

| Experiment | Independent variable | Dependent variable | Primary metric |
|---|---|---|---|
| Retrieval ablation | retrieval strategy | localization quality | top-5 touched-file recall |
| Scaffold comparison | agent runtime | repair performance | resolved rate |
| Patch search | candidate count | repair performance | success@k |
| Memory ablation | memory enabled | repair performance | success delta |
| DSPy optimization | prompt module | subtask quality | localization F1 |

## Baseline hierarchy

Start with these baselines:

1. Keyword-only retrieval plus single patch prompt.
2. Embedding retrieval plus single patch prompt.
3. Agentless localization-repair-validation pipeline.
4. LangGraph repair loop.
5. DeepAgents multi-agent runtime.
6. Multi-candidate patch-search mode.

## Reporting format

Each experiment report must include:

- research question,
- hypothesis,
- dataset,
- configuration,
- metrics,
- results table,
- cost and latency,
- qualitative observations,
- failure cases,
- decision.

## Success bar

The research layer is successful when it produces at least three credible reports:

1. retrieval ablation,
2. scaffold comparison,
3. patch-search ablation.

The final README should summarize those reports in one clear table.
