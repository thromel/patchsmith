# Product Requirements Document

## Status

Draft v0.1

## Product name

PatchSmith Research

## Product summary

PatchSmith Research is an AI software-maintenance system that converts GitHub issues into tested patch diffs. It combines industry-standard agent orchestration with research-oriented evaluation of retrieval, agent scaffolds, patch search, and self-improvement.

## Problem statement

Developers and engineering teams need AI systems that can operate on real repositories, not just isolated coding prompts. A useful AI software-maintenance agent must inspect repository context, reason over issues, edit code safely, run tests, recover from failures, and explain the resulting patch.

Most portfolio AI projects stop at chat, summarization, or shallow RAG. PatchSmith Research will demonstrate a deeper engineering loop: issue understanding, repository intelligence, controlled tool use, sandboxed execution, evaluation, and traceability.

## Goals

### Product goals

- Provide an end-to-end issue-to-patch workflow.
- Make every run inspectable through logs, traces, diffs, and metrics.
- Support human approval before external write actions.
- Offer a recruiter-friendly demo and engineer-friendly implementation.

### Research goals

- Compare agent scaffolds under the same task and model conditions.
- Measure retrieval quality and its effect on patch success.
- Test whether multi-candidate patch search improves outcomes.
- Test whether episodic memory and reusable skills improve future runs.

### Portfolio goals

- Show AI engineering depth.
- Show ML engineering evaluation discipline.
- Show software engineering architecture.
- Show safety and operational maturity.

## Personas

### Recruiter or hiring manager

Wants to understand quickly whether the project is substantial. Needs a clear demo, concise description, metrics, and credible architecture.

### Senior engineer reviewer

Wants to inspect design decisions, code quality, safety boundaries, testing, and observability.

### Research-oriented reviewer

Wants to see hypotheses, baselines, ablations, metrics, and failure analysis.

### Developer user

Wants a patch suggestion that is easy to review and backed by test evidence.

## Core user flow

```text
User submits GitHub issue URL or issue text
  -> system resolves repository and commit
  -> system clones repository in sandbox workspace
  -> system indexes files, symbols, tests, and dependencies
  -> system retrieves relevant context
  -> agent produces repair plan
  -> agent edits files
  -> sandbox runs targeted tests
  -> agent analyzes failures and optionally iterates
  -> system selects final patch
  -> user reviews patch report
```

## MVP feature requirements

### F1. Issue intake

The system must accept:

- GitHub issue URL,
- raw issue text,
- repository URL,
- optional commit hash,
- optional test command.

Acceptance criteria:

- Valid inputs create a run record.
- Invalid URLs or unsupported repositories return actionable errors.
- The run is associated with an immutable repository commit when possible.

### F2. Repository cloning

The system must clone the target repository into an isolated workspace.

Acceptance criteria:

- The workspace is unique per run.
- The system records commit hash and branch.
- The system does not expose host secrets to the workspace.

### F3. Basic repository indexing

The system must produce:

- file list,
- language summary,
- package manager detection,
- candidate test commands,
- basic file summaries.

Acceptance criteria:

- Indexed metadata is stored.
- Files ignored by `.gitignore` or size limits are excluded.
- Binary files are excluded from LLM context.

### F4. Hybrid retrieval v0

The system must retrieve likely relevant files using:

- keyword search,
- path heuristics,
- embeddings where available,
- issue text similarity.

Acceptance criteria:

- Retrieval output includes ranks, scores, and method labels.
- Retrieved context can be inspected in the run report.

### F5. LangGraph repair loop

The system must implement the MVP repair loop with LangGraph:

```text
triage -> retrieve -> plan -> edit -> test -> analyze -> finalize
```

Acceptance criteria:

- Each node emits trace events.
- Tool inputs and outputs are recorded.
- The loop has a maximum iteration limit.
- The loop can fail gracefully.

### F6. File editing

The system must allow the agent to propose controlled edits.

Acceptance criteria:

- Edits are applied only inside the run workspace.
- Every edit is recorded as a diff.
- The final patch can be exported as a unified diff.

### F7. Test execution

The system must run tests inside the sandbox.

Acceptance criteria:

- Command, exit code, duration, stdout, and stderr are captured.
- Timeouts are enforced.
- Failing tests are summarized.

### F8. Final patch report

The system must produce a report containing:

- issue summary,
- retrieved files,
- repair plan,
- final diff,
- test results,
- cost estimate,
- latency,
- risk notes,
- trace link or trace summary.

Acceptance criteria:

- Report is saved for each run.
- Report is readable without inspecting logs.

## Advanced feature requirements

### AF1. Code Context Graph

Build a graph representation of code files, symbols, imports, tests, stack traces, and issue references.

### AF2. Runtime adapters

Support multiple agent scaffolds through a common interface:

- LangGraph runtime,
- DeepAgents runtime,
- OpenAI Agents SDK runtime,
- Agentless baseline,
- mini-SWE-agent-inspired baseline.

### AF3. Multi-candidate patch search

Generate multiple patch candidates, execute tests for each, and select the most promising patch.

### AF4. Self-improving skill registry

Store and evaluate reusable debugging skills generated from failed or successful runs.

### AF5. Evaluation dashboard

Show success rate, retrieval hit rate, cost, latency, and failure modes across experiments.

## Non-functional requirements

### Reliability

- The system should fail gracefully when cloning, installing, indexing, testing, or model calls fail.
- The system should preserve run artifacts for debugging.

### Security

- All repository code and generated commands run in a sandbox.
- Host secrets must never be mounted into execution workspaces.
- External write actions require human approval.

### Performance

- MVP runs should support small to medium repositories.
- Long-running operations should execute as background jobs.
- The UI should stream run progress where practical.

### Cost control

- Every model call should be logged with model, tokens, estimated cost, and node name.
- Advanced modes must have explicit cost budgets.

### Usability

- The MVP should support a CLI-first path and optionally a web UI.
- The final report should be readable by non-experts.

## MVP exclusions

- Authentication for private repositories,
- enterprise permissioning,
- autonomous PR creation,
- broad language support,
- visual issue understanding,
- large-scale distributed sandboxing.

## Product analytics

Track:

- number of attempted runs,
- number of completed runs,
- average run latency,
- average cost,
- test pass rate,
- user approval rate,
- patch export rate.

## Open questions

- Which language should be first-class in v1: Python only, or Python plus TypeScript?
- Should the first interface be CLI-only, web-only, or both?
- Which model provider should be the default for public demo mode?
- How much of SWE-bench should be supported in the first evaluation milestone?
