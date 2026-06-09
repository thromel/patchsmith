# Project Charter: PatchSmith Research

## Status

Draft v0.1

## Owner

Romel

## Vision

Build a production-grade AI software-maintenance agent that converts GitHub issues into tested patch diffs while serving as a research platform for coding-agent architecture, retrieval, sandbox feedback, test-time patch search, and evaluation.

PatchSmith Research should look like a serious engineering system and read like a small applied research lab.

## Primary goal

Create a flagship AI-engineering portfolio project that demonstrates:

- agentic AI engineering,
- ML engineering discipline,
- strong software architecture,
- production safety judgment,
- research-oriented evaluation,
- clear communication through demos and reports.

## Product thesis

Real-world coding agents are not just model wrappers. Their quality depends on:

- repository understanding,
- retrieval and fault localization,
- safe tool execution,
- test feedback loops,
- patch search strategy,
- observability,
- evaluation discipline,
- human approval boundaries.

PatchSmith Research will make those dimensions explicit and measurable.

## Target audience

### Primary audience

- AI engineering recruiters,
- ML engineering teams,
- software engineering teams building AI developer tools,
- research-oriented engineering groups.

### Secondary audience

- open-source maintainers,
- developers evaluating coding agents,
- engineering managers looking for practical AI systems talent.

## Core user promise

A user can provide a GitHub issue or issue text. PatchSmith will inspect the repository, retrieve relevant code context, plan a fix, generate one or more patch candidates, run tests in a sandbox, and return a PR-ready patch report with evidence.

## Flagship demo

The demo should show:

1. issue intake,
2. repository indexing,
3. retrieval results,
4. agent plan,
5. generated patch candidates,
6. sandboxed test execution,
7. failure analysis and iteration,
8. selected patch,
9. final diff report,
10. run metrics: cost, latency, test status, trace, and risk score.

## Scope

### In scope for v1

- Python repositories first,
- public GitHub repositories,
- issue text or issue URL input,
- repository clone at a fixed commit,
- repo indexing and file search,
- hybrid retrieval,
- LangGraph-based repair loop,
- Docker-based sandbox execution,
- patch diff generation,
- run trace and logs,
- custom seeded-bug evaluation suite,
- a clean web UI or CLI demo.

### In scope after v1

- DeepAgents runtime adapter,
- OpenAI Agents SDK runtime adapter,
- Agentless baseline,
- Code Context Graph retrieval,
- multi-candidate patch search,
- DSPy-optimized modules,
- self-improving skill registry,
- SWE-bench-style evaluation,
- local model serving through vLLM,
- hosted demo.

### Out of scope for v1

- autonomous PR submission,
- private repository support,
- broad multi-language support,
- complex Kubernetes deployment,
- fine-tuning custom models,
- replacing a developer review process,
- claiming full autonomous software engineering.

## Non-goals

- Build a clone of existing coding assistants.
- Optimize leaderboard score before building a reliable baseline.
- Add frameworks without adapter boundaries.
- Build a SaaS platform before proving the core repair loop.
- Hide failures or inflate results.

## Success criteria

### MVP success

- The system accepts an issue and repository.
- The system retrieves relevant files.
- The LangGraph runtime produces a patch attempt.
- The sandbox runs tests and captures results.
- The system returns a final report with a diff and trace.

### Research success

- At least three agent scaffolds can be compared on the same task set.
- At least three retrieval strategies can be compared.
- At least one patch-search ablation is completed.
- Results include correctness, cost, latency, and failure-mode analysis.

### Portfolio success

- The GitHub repository has a polished README.
- A 2 to 4 minute demo video exists.
- Architecture and evaluation docs are readable by a recruiter and credible to an engineer.
- The project has honest results and failure cases.

## Guiding principles

1. Build vertical slices before horizontal infrastructure.
2. Keep framework dependencies behind interfaces.
3. Measure before optimizing.
4. Treat untrusted code as hostile.
5. Human approval is required for external side effects.
6. Prefer simple baselines before advanced scaffolds.
7. Write reports that explain both wins and failures.

## Project slogan

From GitHub issue to tested patch, with evidence.
