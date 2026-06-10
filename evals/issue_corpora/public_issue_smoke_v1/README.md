# Public Issue Smoke Corpus v1

This corpus tracks public real-world issue candidates for the next evaluation lane.
It is not solved-run evidence. Entries are curated metadata that should be cloned,
reproduced, and converted into executable tasks before making repair-quality claims.

Validation command:

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-issue-corpus \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Repository preflight command:

```bash
PYTHONPATH=src python3 -m patchsmith.cli preflight-issue-corpus \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Context preview command:

```bash
PYTHONPATH=src python3 -m patchsmith.cli preview-issue-corpus-context \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --context-provider native_hybrid \
  --top-k 5 \
  --json
```

The context preview records source-free retrieved-file summaries only. It does
not prove issue reproduction, patch generation, or test success.

Task materialization command:

```bash
PYTHONPATH=src python3 -m patchsmith.cli materialize-issue-corpus-tasks \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Materialized task manifests and runbooks are source-free setup artifacts. They
do not prove issue reproduction, patch generation, or test success.

Materialized task validation command:

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-materialized-issue-tasks \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Validation checks manifest shape, source-free context summaries, task files,
local repository snapshots, and suggested run commands.

Run-readiness command:

```bash
PYTHONPATH=src python3 -m patchsmith.cli check-materialized-run-readiness \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Run readiness checks command-policy allowlist status and execution risk without
running public-repo tests.

Focused test planning command:

```bash
PYTHONPATH=src python3 -m patchsmith.cli plan-materialized-focused-tests \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --max-paths 2 \
  --json
```

Focused test planning derives scoped pytest commands from retrieved test-like
files and checks those commands through the same command policy.

Focused test execution command:

```bash
PYTHONPATH=src python3 -m patchsmith.cli run-materialized-focused-tests \
  --plan artifacts/experiments/public_issue_corpus_v1/focused_test_plan_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --timeout-seconds 60 \
  --json
```

Focused test execution records whether the scoped commands run in the captured
public repository snapshots. The current lane is readiness evidence only; it is
not solved-run evidence until issue reproduction, patch generation, and passing
validation are added.

Selection criteria:

- public GitHub issue URL,
- Python repository,
- maintenance task that can plausibly exercise retrieval, planning, and patching,
- recent enough or still open at capture time to represent live project maintenance.
