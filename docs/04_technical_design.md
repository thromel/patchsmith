# Technical Design

## Status

Draft v0.1

## Design overview

PatchSmith Research is divided into subsystems that can be built independently but connected through a single repair-run lifecycle.

Core lifecycle:

```text
create run -> clone repo -> index repo -> retrieve context -> run agent -> test patch -> finalize report
```

## 1. Repository ingestion

### Inputs

- repository URL,
- issue URL or issue text,
- optional commit hash,
- optional branch,
- optional test command,
- runtime configuration.

### Outputs

- cloned workspace,
- commit hash,
- repository metadata,
- file inventory,
- detected language and framework,
- candidate test commands.

### Implementation notes

Use a shell wrapper or GitPython for cloning. The system should always resolve a concrete commit hash before running repair logic.

Pseudo-flow:

```text
validate repo URL
  -> clone into workspace/runs/{run_id}/repo
  -> checkout commit or branch
  -> record commit hash
  -> inspect file tree
```

### File filtering

Exclude:

- `.git/`,
- dependency folders like `node_modules/`, `.venv/`, `venv/`,
- build artifacts,
- binary files,
- very large files,
- lockfiles from LLM context unless needed for dependency analysis.

## 2. Repository indexing

### Index artifacts

- `FileIndex`: path, size, extension, language, hash,
- `SymbolIndex`: name, kind, file path, line range,
- `ImportIndex`: source file, imported module,
- `TestIndex`: test file, test name, referenced symbols,
- `EmbeddingIndex`: chunk ID, vector, text span,
- `CodeContextGraph`: nodes and edges.

### Parser strategy

MVP:

- simple file scanning,
- regex-based symbol extraction for Python,
- keyword index.

Advanced:

- tree-sitter parser,
- language-specific symbol extractors,
- import graph,
- test relationship inference.

## 3. Retrieval subsystem

### Interface

```python
class RetrievalStrategy:
    async def retrieve(self, query: RetrievalQuery) -> list[RetrievedContext]:
        ...
```

### Retrieval query

Fields:

- issue text,
- stack trace if present,
- failing test output if present,
- repository metadata,
- prior retrieved files,
- runtime budget.

### Retrieval methods

#### Keyword retrieval

Use BM25 or equivalent lexical ranking over file chunks.

#### Symbol retrieval

Match issue terms, stack traces, function names, class names, and test names to symbols.

#### Embedding retrieval

Embed file chunks and issue text, then perform vector search.

#### Graph expansion

Expand from retrieved nodes through graph edges:

```text
mentioned symbol -> defining file -> tests for file -> imports -> related files
```

#### Reranking

Rerank candidate chunks using a stronger model or cross-encoder style reranker where practical.

### Context packing

The context packer should build a compact model input containing:

- issue summary,
- repository summary,
- relevant file snippets,
- symbol definitions,
- failing tests,
- constraints,
- previously attempted edits.

It must track source paths and line ranges.

## 4. Agent runtime subsystem

### Common interface

```python
@dataclass
class AgentTask:
    run_id: str
    repo_path: str
    issue_text: str
    retrieved_context: list[RetrievedContext]
    config: AgentConfig

@dataclass
class AgentResult:
    status: str
    final_diff: str | None
    patch_candidates: list[PatchCandidate]
    test_results: list[TestResult]
    trace: list[TraceEvent]
    summary: str
```

```python
class AgentRuntime(Protocol):
    async def run(self, task: AgentTask) -> AgentResult:
        ...
```

### LangGraph MVP graph

```text
triage_node
  -> retrieval_node
  -> planning_node
  -> edit_node
  -> test_node
  -> failure_analysis_node
  -> should_retry?
      -> edit_node
      -> final_review_node
  -> report_node
```

### Node responsibilities

#### Triage node

- classify issue type,
- extract symptoms,
- identify likely test command,
- detect risk level.

#### Retrieval node

- call retrieval subsystem,
- select context pack,
- record retrieval metrics.

#### Planning node

- produce repair plan,
- identify files to inspect or edit,
- estimate risk.

#### Edit node

- apply structured patch instructions,
- reject edits outside workspace,
- record diff.

#### Test node

- run targeted or full tests,
- capture output,
- summarize failures.

#### Failure analysis node

- explain failing tests,
- decide whether to retry,
- update plan.

#### Final review node

- inspect diff,
- score risk,
- check for suspicious changes.

#### Report node

- write final report,
- persist artifacts.

## 5. Tool design

### Tool principles

- Tools must use structured inputs and outputs.
- Tools must validate paths.
- Tools must not execute arbitrary commands without policy checks.
- Tools must emit trace events.

### Core tools

| Tool | Purpose |
|---|---|
| `read_file` | Read bounded file ranges |
| `search_repo` | Search file content |
| `list_files` | List filtered repository files |
| `apply_patch` | Apply unified diff or structured edit |
| `run_tests` | Run allowed test command |
| `get_diff` | Return current workspace diff |
| `revert_changes` | Reset workspace to baseline |
| `summarize_test_output` | Compress logs for agent use |

## 6. Sandbox subsystem

### Interface

```python
class SandboxRunner:
    async def run_command(self, request: CommandRequest) -> CommandResult:
        ...
```

### Command request

Fields:

- run ID,
- workspace path,
- command,
- timeout seconds,
- environment variables,
- network policy,
- memory limit,
- CPU limit.

### Command result

Fields:

- exit code,
- stdout,
- stderr,
- duration,
- timeout flag,
- resource usage,
- command policy decision.

### Policy enforcement

Reject commands containing:

- host filesystem paths,
- destructive shell commands outside workspace,
- secret access attempts,
- network commands when network is disabled,
- privilege escalation attempts.

MVP can implement a conservative allowlist:

- `pytest`,
- `python -m pytest`,
- `npm test`,
- `pnpm test`,
- `ruff`,
- `mypy`,
- `python -m unittest`.

## 7. Patch candidate subsystem

### Patch candidate fields

- candidate ID,
- generation strategy,
- diff,
- files changed,
- test results,
- reviewer score,
- risk notes,
- selected flag.

### Candidate strategies

- minimal fix,
- test-driven fix,
- alternative localization fix,
- stronger-model fix,
- failure-analysis repair.

### Selection function

A simple initial scoring function:

```text
score =
  50 * targeted_tests_passed
+ 30 * full_tests_passed
-  5 * changed_file_count
-  3 * diff_risk_score
-  2 * failed_test_count
```

This can later be replaced with a learned or LLM-assisted selector.

## 8. Evaluation subsystem

### Evaluation runner

Inputs:

- task dataset,
- runtime configuration,
- retrieval strategy,
- model configuration,
- budget configuration.

Outputs:

- per-task run report,
- aggregate metrics,
- experiment report.

### Experiment config example

```yaml
experiment_name: retrieval_ablation_v1
dataset: seeded_bugs_v1
runtime: langgraph
model: default_strong
retrieval_strategy: code_context_graph
max_iterations: 3
max_candidates: 1
```

## 9. Observability subsystem

### Trace event fields

- run ID,
- node name,
- event type,
- start time,
- end time,
- status,
- input summary,
- output summary,
- model name,
- token usage,
- cost estimate,
- error.

### Required traces

- model call,
- tool call,
- sandbox command,
- patch application,
- test run,
- retry decision,
- final review.

## 10. Error handling

Failure categories:

- clone failure,
- dependency installation failure,
- indexing failure,
- retrieval failure,
- model failure,
- patch application failure,
- sandbox failure,
- test timeout,
- no patch generated,
- unsafe command rejected.

Every failure must produce a readable final status.

## 11. Configuration

Configuration should be file-based and reproducible.

Example:

```yaml
runtime: langgraph
retrieval:
  strategy: hybrid_v0
  max_files: 8
agent:
  max_iterations: 3
  model: strong_default
sandbox:
  timeout_seconds: 300
  network: disabled
patch_search:
  enabled: false
  max_candidates: 1
```

## 12. Implementation order

1. Run model-free repo clone and indexing.
2. Implement sandbox command runner.
3. Implement basic retrieval.
4. Implement LangGraph repair graph with mock model.
5. Connect real model calls.
6. Add diff report.
7. Add evaluation runner.
8. Add advanced retrieval.
9. Add additional runtimes.
10. Add patch search.
