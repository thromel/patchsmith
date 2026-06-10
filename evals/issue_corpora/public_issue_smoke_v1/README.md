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

Selection criteria:

- public GitHub issue URL,
- Python repository,
- maintenance task that can plausibly exercise retrieval, planning, and patching,
- recent enough or still open at capture time to represent live project maintenance.
