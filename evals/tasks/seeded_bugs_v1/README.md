# Seeded Bugs v1

This dataset contains small deterministic Python bugs for PatchSmith development and evaluation.

Each task directory contains:

- `repo/` - repository snapshot used as the repair target,
- `issue.md` - issue text,
- `expected.json` - expected touched files, related tests, and validation metadata.

The dataset starts intentionally small. Add tasks only when the runner can preserve per-task artifacts and distinguish infrastructure failures from retrieval or agent failures.

Validate the dataset before treating retrieval or repair evals as release evidence:

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-dataset \
  --dataset evals/tasks/seeded_bugs_v1 \
  --output artifacts/experiments/seeded_dataset_validation_v1 \
  --json
```
