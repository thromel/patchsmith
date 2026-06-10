# Data Model

## Status

Draft v0.1

## Data model goals

The data model must support:

- reproducible runs,
- traceability,
- evaluation metrics,
- artifact storage,
- runtime comparison,
- retrieval analysis,
- patch candidate comparison.

## Core entities

```text
Project
  -> RepositorySnapshot
  -> Run
      -> RetrievedContext
      -> TraceEvent
      -> PatchCandidate
          -> TestRun
          -> ReviewResult
      -> FinalReport
Experiment
  -> ExperimentRun
      -> Run
```

## Entity definitions

### Project

Represents a repository being analyzed.

Fields:

| Field | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| name | string | display name |
| repo_url | string | public repository URL |
| default_branch | string | optional |
| primary_language | string | detected language |
| created_at | timestamp | creation time |
| updated_at | timestamp | update time |

### RepositorySnapshot

Represents a repository at a concrete commit.

| Field | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| project_id | UUID | foreign key |
| commit_hash | string | immutable commit |
| branch | string | optional |
| file_count | integer | indexed files |
| language_summary | JSON | language counts |
| package_manager | string | detected package manager |
| test_commands | JSON | candidate commands |
| created_at | timestamp | creation time |

### Run

Represents one issue-to-patch attempt.

| Field | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| project_id | UUID | foreign key |
| snapshot_id | UUID | foreign key |
| issue_url | string | optional |
| issue_text | text | raw issue text |
| runtime | string | langgraph, deepagents, openai_agents, agentless |
| retrieval_strategy | string | strategy name |
| model_config | JSON | model settings |
| status | string | lifecycle status |
| started_at | timestamp | run start |
| completed_at | timestamp | run end |
| total_input_tokens | integer | aggregate |
| total_output_tokens | integer | aggregate |
| estimated_cost | decimal | aggregate |
| latency_ms | integer | aggregate |
| error_summary | text | nullable |

### RetrievedContext

Represents a file chunk or symbol included by retrieval.

| Field | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| run_id | UUID | foreign key |
| file_path | string | repository-relative path |
| symbol_name | string | optional |
| start_line | integer | optional |
| end_line | integer | optional |
| retrieval_method | string | keyword, embedding, graph, rerank |
| rank | integer | final rank |
| score | float | retrieval score |
| included_in_prompt | boolean | context packing decision |
| content_hash | string | reproducibility |

### PatchCandidate

Represents one candidate diff.

| Field | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| run_id | UUID | foreign key |
| candidate_index | integer | 1-based index |
| generation_strategy | string | minimal, test-driven, etc. |
| diff | text | unified diff |
| files_changed | JSON | file list |
| lines_added | integer | diff stat |
| lines_removed | integer | diff stat |
| selected | boolean | final selection |
| status | string | generated, tested, rejected, selected |
| reviewer_score | float | optional |
| risk_score | float | optional |
| created_at | timestamp | creation time |

### TestRun

Represents one command execution for one run or candidate.

| Field | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| run_id | UUID | foreign key |
| patch_candidate_id | UUID | nullable |
| command | string | command executed |
| exit_code | integer | process result |
| stdout_path | string | artifact path |
| stderr_path | string | artifact path |
| duration_ms | integer | execution time |
| timed_out | boolean | timeout flag |
| sandbox_config | JSON | resource/network settings |
| created_at | timestamp | creation time |

### TraceEvent

Represents a structured event in a run.

| Field | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| run_id | UUID | foreign key |
| parent_event_id | UUID | nullable |
| event_type | string | model_call, tool_call, sandbox, etc. |
| node_name | string | graph node |
| status | string | started, completed, failed |
| input_summary | text | truncated |
| output_summary | text | truncated |
| payload | JSON | structured data |
| started_at | timestamp | start |
| completed_at | timestamp | end |
| latency_ms | integer | duration |
| input_tokens | integer | nullable |
| output_tokens | integer | nullable |
| estimated_cost | decimal | nullable |

### ReviewResult

Represents an automated or human review.

| Field | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| patch_candidate_id | UUID | foreign key |
| reviewer_type | string | model, human, static |
| score | float | normalized score |
| verdict | string | accept, reject, needs_review |
| risk_notes | text | explanation |
| created_at | timestamp | creation time |

### FinalReport

Represents the user-facing run summary.

| Field | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| run_id | UUID | foreign key |
| markdown_path | string | artifact path |
| final_diff_path | string | artifact path |
| summary | text | short summary |
| selected_candidate_id | UUID | nullable |
| created_at | timestamp | creation time |

### Experiment

Represents an evaluation experiment.

| Field | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| name | string | experiment name |
| hypothesis | text | research hypothesis |
| dataset_name | string | dataset |
| config | JSON | full config |
| git_commit | string | project code commit |
| created_at | timestamp | creation time |

### ExperimentRun

Links experiments to repair runs.

| Field | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| experiment_id | UUID | foreign key |
| run_id | UUID | foreign key |
| task_id | string | dataset task ID |
| expected_files | JSON | known touched files |
| resolved | boolean | evaluation result |
| metrics | JSON | task metrics |

## Artifact storage

Artifacts should be stored on disk or object storage with paths referenced in the database.

Artifact types:

- cloned repository snapshot metadata,
- raw logs,
- stdout/stderr,
- final diff,
- patch candidate diffs,
- run report markdown,
- traces,
- experiment CSV or JSON.

Suggested local structure:

```text
artifacts/
  runs/
    {run_id}/
      repo/
      patches/
      logs/
      traces/
      report.md
  experiments/
    {experiment_id}/
      results.csv
      report.md
```

## Initial database choice

Use Postgres for relational metadata. Use pgvector or a separate vector store for embeddings. For MVP, SQLite is acceptable if the interface is kept portable.

## Schema migration principle

Every schema change should be linked to one of:

- product requirement,
- evaluation metric,
- observability need,
- safety requirement.

Avoid storing data that is not used for a report, trace, evaluation, or UI.
