# Testing Strategy

## Status

Draft v0.1

## Purpose

PatchSmith Research must test ordinary software behavior, agent workflows, safety boundaries, and evaluation reproducibility. The testing strategy should be practical and layered.

## Testing layers

| Layer | Purpose | Examples |
|---|---|---|
| Unit tests | Validate small functions | command parser, diff parser, cost calculator |
| Integration tests | Validate subsystem boundaries | retrieval plus context packing, sandbox runner |
| Agent smoke tests | Validate end-to-end flow | seeded bug run with mocked model |
| Sandbox safety tests | Validate containment and policies | blocked command, timeout, path traversal |
| Evaluation tests | Validate metrics and reports | retrieval recall calculation |
| Regression tests | Preserve known behavior | previously solved seeded bugs |

## Unit tests

Unit tests should cover:

- URL validation,
- file filtering,
- command policy,
- path normalization,
- diff parsing,
- patch application validation,
- token and cost calculation,
- metrics aggregation,
- config loading.

## Integration tests

Integration tests should cover:

- repo clone into workspace,
- index small repo,
- retrieve context from issue text,
- apply patch and generate diff,
- run tests in sandbox,
- store run artifacts,
- generate final report.

## Agent tests

Agent tests are expensive and flaky if they depend on live models. Use two categories.

### Mocked agent tests

Use deterministic fake model outputs to validate graph transitions.

Required cases:

- successful first-pass patch,
- failed test followed by retry,
- patch application failure,
- unsafe command rejection,
- max-iteration exit.

### Live model smoke tests

Use a tiny seeded bug suite and a low-cost model configuration.

Required cases:

- one simple Python logic bug,
- one failing import,
- one failing unit test expectation.

## Sandbox safety tests

Required safety tests:

- command timeout is enforced,
- memory limit is enforced where available,
- path traversal is rejected,
- host secret access is impossible,
- blocked commands are rejected,
- network-disabled mode blocks network commands where possible,
- workspace cleanup works.

## Evaluation tests

Test metrics independently from agent behavior.

Required metric tests:

- top-k touched-file recall,
- resolved rate,
- average cost,
- average latency,
- regression rate,
- success@k,
- failed tool-call count.

## CI quality gates

MVP CI should run:

```text
format check
lint
unit tests
integration tests without live model
sandbox policy tests
```

Research CI can run nightly or manually:

```text
seeded bug suite
retrieval ablation
agent smoke tests with live model
```

## Test data strategy

Keep seeded bugs small and versioned.

Suggested structure:

```text
evals/tasks/seeded_bugs_v1/
  task_001_logic_bug/
    repo/
    issue.md
    expected.json
  task_002_import_bug/
    repo/
    issue.md
    expected.json
```

Each `expected.json` should include:

```json
{
  "task_id": "task_001_logic_bug",
  "language": "python",
  "test_command": "python -m pytest",
  "expected_touched_files": ["src/calculator.py"],
  "failure_type": "logic_bug"
}
```

Keep public issue candidates separate from seeded tasks:

```text
evals/issue_corpora/public_issue_smoke_v1/
  issues.json
  README.md
```

Validate the corpus before citing real-world task breadth:

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-issue-corpus \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Preflight repository reachability before cloning:

```bash
PYTHONPATH=src python3 -m patchsmith.cli preflight-issue-corpus \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Preview context retrieval before converting candidates into executable tasks:

```bash
PYTHONPATH=src python3 -m patchsmith.cli preview-issue-corpus-context \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --context-provider native_hybrid \
  --top-k 5 \
  --json
```

Materialize source-free task manifests after context preview:

```bash
PYTHONPATH=src python3 -m patchsmith.cli materialize-issue-corpus-tasks \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Validate the materialized task contract before using it:

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-materialized-issue-tasks \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Check run readiness before executing public-repo tests:

```bash
PYTHONPATH=src python3 -m patchsmith.cli check-materialized-run-readiness \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Plan focused test commands from retrieved test-like files:

```bash
PYTHONPATH=src python3 -m patchsmith.cli plan-materialized-focused-tests \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --max-paths 2 \
  --json
```

Run the planned focused test commands:

```bash
PYTHONPATH=src python3 -m patchsmith.cli run-materialized-focused-tests \
  --plan artifacts/experiments/public_issue_corpus_v1/focused_test_plan_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --timeout-seconds 60 \
  --json
```

The current focused run attempted all three planned public issue commands and all three failed in the local snapshots. Treat that as public-repo dependency and suite-readiness evidence until a later run adds issue reproduction, a patch, and passing validation.

Diagnose focused test run failures:

```bash
PYTHONPATH=src python3 -m patchsmith.cli diagnose-focused-test-runs \
  --results artifacts/experiments/public_issue_corpus_v1/focused_test_run_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The current diagnosis classifies the three failures as one dependency setup issue and two environment fixture issues, with no unknown failures. Treat these as setup backlog items before public issue repair attempts.

Plan setup work from focused test diagnoses:

```bash
PYTHONPATH=src python3 -m patchsmith.cli plan-focused-test-setups \
  --diagnosis artifacts/experiments/public_issue_corpus_v1/focused_test_diagnosis_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The current setup plan has three planned setup tasks, all sandbox-required and network-risk-bearing. Treat it as the setup backlog before reproduction or repair runs, not as permission to install dependencies on the host.

Check setup readiness before executing setup commands:

```bash
PYTHONPATH=src python3 -m patchsmith.cli check-focused-test-setup-readiness \
  --setup-plan artifacts/experiments/public_issue_corpus_v1/focused_test_setup_plan_results.json \
  --docker-smoke artifacts/experiments/docker_smoke.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Current setup readiness has zero blocked tasks and three warning-class tasks because Docker smoke passes and each setup requires reviewed networked Docker execution. Do not run dependency setup until the setup-readiness report is reviewed and the selected sandbox/network policy is approved.

Dry-run setup execution before any dependency install:

```bash
PYTHONPATH=src python3 -m patchsmith.cli execute-focused-test-setups \
  --readiness artifacts/experiments/public_issue_corpus_v1/focused_test_setup_readiness_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

The setup executor keeps dependency installation blocked by default. The narrow editable-install setup policy requires Docker mode, `--allow-dependency-installs`, and explicit network selection such as `--sandbox-network bridge`; focused setup execution and validation default to `patchsmith-seeded-smoke:py312`. Use `--execute` only after the dry-run report and sandbox decision are approved.

Dry-run setup validation after setup execution:

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-focused-test-setups \
  --setup-execution artifacts/experiments/public_issue_corpus_v1/focused_test_setup_execution_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Setup validation now executes after setup completion and passes for all three current public issue corpus tasks. Passing setup validation proves only that the focused validation command runs after setup, not that PatchSmith repaired the issue.

The corpus, preflight, context-preview, materialization, validation, run-readiness, focused-test planning, focused-test run, focused-test diagnosis, focused-test setup-plan, setup-readiness, setup-execution, and setup-validation reports are planning and plumbing evidence. They are not repair-quality evidence until the issues are reproduced, patched, tested, and saved as normal PatchSmith run artifacts.

## Definition of test completion

A feature that affects runtime behavior is not complete unless it has one of:

- unit test,
- integration test,
- seeded bug run,
- experiment report.

## Known hard parts

- Live model tests may be nondeterministic.
- Repository setup may be flaky.
- Some tests pass for the wrong reason.
- Stronger models may hide retrieval weaknesses.

The solution is not to avoid tests. The solution is to label uncertainty and preserve artifacts.
