# Benchmark Manifest Schema

PatchSmith benchmark rows should be reproducible, bounded, and explicit about
their claim boundary.

## YAML Shape

```yaml
schema_version: patchsmith.benchmark-task.v1
task_id: public_issue_smoke_v1/pytest_001
repo: pytest-dev/pytest
commit: abc123
issue_url: https://github.com/pytest-dev/pytest/issues/14552
issue_summary: Short human-readable task summary.
reproduction:
  command: python -m pytest tests/test_target.py -q
  expected_failure: "AssertionError"
validation:
  focused_command: python -m pytest tests/test_target.py -q
  full_command: python -m pytest
claim_boundary: focused_validation_only
reviewed_context:
  - src/_pytest/pathlib.py#import_path
runtime_constraints:
  max_model_responses: 12
  max_model_tokens: 200000
  max_retries: 1
fairness:
  same_context_bundle: true
  same_validation_command: true
  direct_repo_mutation_allowed: false
```

## Required Fields

| Field | Why It Matters |
| --- | --- |
| `task_id` | Stable join key for reports and artifacts. |
| `repo` and `commit` | Repository snapshot must be reproducible. |
| `issue_summary` or `issue_url` | Repair intent must be inspectable. |
| `reproduction.command` | Shows the failure before the repair attempt. |
| `validation.focused_command` | Defines the pass/fail evidence. |
| `claim_boundary` | Prevents focused validation from becoming upstream acceptance. |
| `reviewed_context` | Makes extra hints explicit. |
| `runtime_constraints` | Makes cost/retry budgets comparable. |

## Claim Boundaries

- `focused_validation_only`: targeted command passed; no broad claim.
- `full_suite_validation`: broader test suite passed in the captured snapshot.
- `setup_only`: setup/reproduction was proven, but no repair claim was made.
- `artifact_only`: saved for inspection; not a benchmark row.
