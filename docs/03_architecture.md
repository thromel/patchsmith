# Architecture

## Status

Draft v0.1

## Architecture goals

PatchSmith Research must support two modes:

1. an industry-grade product path for issue-to-patch workflows,
2. a research path for comparing retrieval, agents, and patch-search strategies.

The architecture should be modular, observable, and safe by default.

## High-level architecture

```mermaid
flowchart TD
    user["User or reviewer"] --> cli["CLI / future UI"]
    cli --> workflow["Repair workflow"]
    workflow --> ingest["Repository ingest and index"]
    workflow --> broker["Context broker"]
    broker --> native["Native retrieval"]
    broker --> graph["Code Context Graph"]
    broker --> ctxhelm["ctxhelm CLI adapter"]
    workflow --> runtime["Agent runtime boundary"]
    runtime --> agentless["Agentless baseline"]
    runtime --> langgraph["LangGraph runtime"]
    runtime --> deepagents["DeepAgents adapter"]
    runtime --> patchsearch["Patch-search mode"]
    workflow --> sandbox["Command policy and sandbox"]
    sandbox --> tests["Targeted tests"]
    workflow --> artifacts["Run artifacts"]
    artifacts --> traces["traces.jsonl"]
    artifacts --> reports["reports and diffs"]
    artifacts --> dashboard["artifact dashboard"]
    artifacts --> evals["evaluation reports"]
```

```text
                          User
                           |
                           v
                 +-------------------+
                 | Web UI or CLI     |
                 +---------+---------+
                           |
                           v
                 +-------------------+
                 | API Server        |
                 | FastAPI           |
                 +---------+---------+
                           |
                           v
          +----------------+----------------+
          | Job Orchestrator                |
          | queue, run lifecycle, status    |
          +----------------+----------------+
                           |
                           v
          +----------------+----------------+
          | Agent Runtime Layer             |
          | LangGraph, DeepAgents, baselines|
          +-----+------------+--------------+
                |            |
                v            v
       +----------------+   +----------------+
       | Retrieval      |   | Sandbox        |
       | Code Context   |   | Docker runner  |
       | Graph          |   | tests, tools   |
       +--------+-------+   +-------+--------+
                |                   |
                v                   v
       +----------------+   +----------------+
       | Storage        |   | Artifacts      |
       | Postgres       |   | diffs, logs    |
       | Vector index   |   | traces         |
       +--------+-------+   +-------+--------+
                |                   |
                +---------+---------+
                          v
                 +-------------------+
                 | Evaluation and    |
                 | Observability     |
                 +-------------------+
```

## Core components

### Web UI

Responsibilities:

- submit issue and repository input,
- display run progress,
- show retrieved files,
- show patch candidates,
- show diff viewer,
- show test output,
- show final report,
- show experiment dashboards.

Recommended stack:

- Next.js,
- TypeScript,
- Monaco editor or code diff component,
- simple charting library for eval dashboards.

### CLI

Responsibilities:

- run local experiments,
- trigger one-off repair runs,
- run evaluation suites,
- export reports.

The CLI is useful for development even if the portfolio demo uses the web UI.

### API server

Responsibilities:

- validate inputs,
- create run records,
- enqueue jobs,
- stream status updates,
- serve artifacts,
- expose metrics and reports.

Recommended stack:

- FastAPI,
- Pydantic,
- SQLAlchemy,
- Postgres,
- Redis queue or RQ/Celery.

### Job orchestrator

Responsibilities:

- manage run lifecycle,
- schedule indexing, agent execution, sandbox execution, and evaluation jobs,
- enforce timeouts,
- persist status transitions.

Run states:

```text
created -> cloning -> indexing -> retrieving -> planning -> patching -> testing -> reviewing -> completed
created -> cloning -> failed
created -> ... -> cancelled
```

### Agent runtime layer

The agent runtime layer hides framework differences behind a common interface.

```python
class AgentRuntime:
    async def run(self, task: AgentTask) -> AgentResult:
        ...
```

Supported runtimes:

- `LangGraphRuntime`: primary production workflow,
- `DeepAgentsRuntime`: dependency-gated adapter for DeepAgents-style scaffold comparison,
- `OpenAIAgentsRuntime`: dependency-gated OpenAI Agents SDK scaffold adapter,
- `AgentlessRuntime`: baseline localization-repair-validation runtime,
- `TreeSearchRuntime`: research mode for test-time exploration.

### Retrieval layer

Responsibilities:

- index repository files,
- parse symbols and dependencies,
- perform keyword search,
- perform vector search,
- expand through Code Context Graph,
- rerank candidate context,
- pack final context for the model.

Retrieval pipeline:

```text
issue text
  -> keyword search
  -> symbol search
  -> embedding search
  -> graph expansion
  -> reranking
  -> context packing
```

### Code Context Graph

The Code Context Graph represents repository structure.

Node types:

- repository,
- file,
- function,
- class,
- method,
- import,
- package,
- test,
- fixture,
- stack trace,
- issue mention,
- patch candidate.

Edge types:

- defines,
- imports,
- calls,
- inherits,
- tests,
- mentions,
- fails_in,
- modified_by,
- depends_on,
- similar_to.

### Sandbox runtime

Responsibilities:

- create isolated workspace,
- install dependencies if allowed,
- apply patches,
- run tests,
- enforce resource limits,
- capture stdout/stderr,
- return structured results.

Sandbox principles:

- no host secrets,
- strict workspace boundary,
- command allowlist,
- timeouts,
- optional network isolation,
- audit logs.

### Patch search layer

Responsibilities:

- generate multiple patch candidates,
- run tests per candidate,
- analyze failures,
- optionally repair candidates,
- select best candidate,
- produce final patch report.

Candidate strategies:

- conservative minimal fix,
- test-driven fix,
- architecture-aware fix,
- alternative localization fix,
- stronger-model escalation.

### Evaluation layer

Responsibilities:

- run benchmark tasks,
- record metrics,
- run ablations,
- produce reports,
- compare configurations.

Evaluation outputs:

- experiment table,
- failure analysis,
- run artifacts,
- charts,
- final summary.

### Observability layer

Responsibilities:

- trace agent nodes,
- log tool calls,
- track tokens and cost,
- track latency,
- capture errors,
- expose debugging views.

## Data flow

### Single repair run

```text
Input validation
  -> run created
  -> repo cloned
  -> repo indexed
  -> context retrieved
  -> agent runtime starts
  -> plan generated
  -> files edited
  -> patch candidate produced
  -> tests executed
  -> candidate reviewed
  -> final report generated
```

### Evaluation run

```text
Experiment config
  -> dataset loaded
  -> tasks scheduled
  -> repair run per task
  -> metrics collected
  -> artifacts stored
  -> aggregate report generated
```

## Framework boundaries

Frameworks must not leak into the domain layer.

Good:

```text
AgentRuntime interface -> LangGraph implementation
```

Bad:

```text
LangGraph-specific state objects passed through the entire backend
```

## Deployment architecture for MVP

```text
Local development:
- Docker Compose
- API server
- Postgres
- Redis
- worker
- web app
- Docker daemon for sandbox jobs
```

Public demo can initially be simulated with pre-recorded runs to avoid unsafe arbitrary code execution on a hosted server.

## Key architecture decisions

- Use LangGraph as primary runtime.
- Use Docker sandbox for execution.
- Keep frameworks behind runtime adapters.
- Use Code Context Graph for advanced retrieval.
- Use multi-candidate patch search only after MVP baseline.

## Constraints

- Model calls may be slow and costly.
- Repository setup can be unreliable.
- Public repositories may contain malicious scripts.
- Tests may be missing, flaky, or expensive.
- Benchmarks may require careful environment reproduction.

## Architecture quality attributes

| Attribute | Approach |
|---|---|
| Safety | sandboxing, approval gates, command policy |
| Reproducibility | commit pinning, config snapshots, artifact storage |
| Observability | trace events, logs, metrics, cost tracking |
| Extensibility | runtime adapters, retrieval strategy interfaces |
| Lean delivery | vertical slices, milestone gates |
| Research quality | baselines, ablations, reports |
