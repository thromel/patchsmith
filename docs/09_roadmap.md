# Roadmap

## Status

Draft v0.1

## Roadmap philosophy

Build the smallest credible system first. Add research sophistication only after the baseline loop works.

The roadmap is milestone-based, not date-based.

## Milestone 0: Documentation foundation

### Goal

Create the project operating system.

### Deliverables

- project charter,
- PRD,
- research plan,
- architecture doc,
- technical design,
- evaluation plan,
- safety doc,
- data model,
- engineering playbook,
- initial ADRs.

### Exit criteria

- core docs exist,
- MVP scope is clear,
- first three ADRs accepted,
- first implementation target is defined.

## Milestone 1: MVP repair loop

### Goal

Run one issue through one end-to-end repair attempt.

### Deliverables

- CLI issue input,
- repository clone,
- basic file index,
- keyword retrieval,
- LangGraph repair graph,
- file read/search tools,
- patch application,
- Docker test runner,
- final Markdown report.

### Exit criteria

- one seeded bug produces a patch attempt,
- tests are executed in sandbox,
- final report includes diff, test output, and trace summary.

## Milestone 2: Reliable baseline and seeded bug suite

### Goal

Make the MVP repeatable on a controlled task suite.

### Deliverables

- 10 seeded bug tasks,
- run configuration files,
- evaluation runner,
- metrics logger,
- run artifacts,
- baseline report.

### Exit criteria

- all seeded tasks run through the same pipeline,
- success, cost, latency, and failure categories are recorded,
- infrastructure failures are distinguishable from model failures.

## Milestone 3: Hybrid retrieval

### Goal

Improve fault localization beyond keyword search.

### Deliverables

- embeddings index,
- symbol extraction,
- path and stack-trace heuristics,
- context packer,
- retrieval metrics.

### Exit criteria

- retrieval ablation report compares keyword, embedding, and hybrid retrieval,
- top-k touched-file recall is reported,
- final context is inspectable in reports.

## Milestone 4: Code Context Graph

### Goal

Add graph-augmented repository understanding.

### Deliverables

- graph schema,
- file and symbol nodes,
- import edges,
- test relationship edges,
- graph expansion retrieval,
- reranking hook.

### Exit criteria

- Code Context Graph retrieval runs on seeded suite,
- retrieval ablation includes graph mode,
- graph mode is compared against hybrid v0.

## Milestone 5: Runtime adapter comparison

### Goal

Compare agent scaffolds without rewriting the system.

### Deliverables

- `AgentRuntime` interface,
- Agentless runtime,
- LangGraph runtime cleanup,
- DeepAgents runtime adapter,
- optional OpenAI Agents SDK adapter,
- scaffold comparison report.

### Exit criteria

- same task can run under at least two runtimes,
- metrics are comparable across runtimes,
- scaffold comparison report is published.

## Milestone 6: Multi-candidate patch search

### Goal

Test whether patch search improves success.

### Deliverables

- candidate generator,
- per-candidate sandbox execution,
- patch selector,
- candidate comparison UI or report,
- patch-search ablation.

### Exit criteria

- one-candidate and multi-candidate modes are compared,
- success@k and cost per success are reported,
- selected candidate is justified in final report.

## Milestone 7: Observability and UI polish

### Goal

Make the system inspectable and demo-ready.

### Deliverables

- trace viewer,
- run history,
- cost and latency dashboard,
- diff viewer,
- retrieved context viewer,
- failure summary.

### Exit criteria

- demo issue can be shown in a clean UI,
- every major node has trace events,
- portfolio screenshots are available.

## Milestone 8: Research extensions

### Goal

Add high-signal research features selectively.

### Candidate deliverables

- episodic memory,
- gated skill registry,
- DSPy optimization,
- tree-search mode,
- generated distinguishing tests.

### Exit criteria

- each extension has an experiment plan,
- each extension has a baseline comparison,
- weak extensions are cut or labeled experimental.

## Milestone 9: Portfolio launch

### Goal

Publish the project as a recruiter-grade artifact.

### Deliverables

- polished README,
- 2 to 4 minute demo video,
- architecture diagram,
- final evaluation report,
- launch blocker backlog,
- public issue reproduction-plan gate,
- public issue repair-readiness gate,
- failure analysis report,
- blog post series,
- stable tagged release.

### Exit criteria

- public repo is clean,
- demo is understandable in 60 seconds,
- evaluation results are honest and visible,
- project can be discussed deeply in interviews.

## Cutline

If time becomes limited, prioritize:

1. MVP repair loop,
2. seeded bug evaluation,
3. retrieval ablation,
4. patch report quality,
5. polished README and demo.

Deprioritize:

- Kubernetes,
- fine-tuning,
- private repository support,
- broad language support,
- complex hosted execution,
- fully autonomous PR creation.
