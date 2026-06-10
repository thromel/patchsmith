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

Selection criteria:

- public GitHub issue URL,
- Python repository,
- maintenance task that can plausibly exercise retrieval, planning, and patching,
- recent enough or still open at capture time to represent live project maintenance.
