# PatchSmith Artifact Gallery

PatchSmith's strongest public claim is that a repair attempt should leave an
inspectable run directory. The gallery starts with three committed samples and a
repeatable command that regenerates the same artifact classes locally.

## Canonical Demo

Run:

```bash
patchsmith demo seeded-logic-bug
```

Inspect:

```bash
patchsmith inspect artifacts/demo/seeded_logic_bug/runs/<run_id>
```

Static sample:

- [sample README](sample_artifacts/seeded_logic_bug/README.md)
- [sample report](sample_artifacts/seeded_logic_bug/report.md)
- [sample diff](sample_artifacts/seeded_logic_bug/final.diff)
- [sample metadata](sample_artifacts/seeded_logic_bug/metadata.json)
- [sample trace](sample_artifacts/seeded_logic_bug/traces.sample.jsonl)
- [sample selected context](sample_artifacts/seeded_logic_bug/context/selected_files.json)

## Gallery Rows

| Run | Outcome | Why It Exists |
| --- | --- | --- |
| [`seeded-logic-bug`](sample_artifacts/seeded_logic_bug/README.md) | `patch_validated` | Shows the happy path: context, patch, validation, and report. |
| [`empty-diff-blocked`](sample_artifacts/empty_diff_blocked/README.md) | `empty_diff` blocked | Shows that a model cannot pass review by producing no patch. |
| [`failed-validation`](sample_artifacts/failed_validation/README.md) | `patch_failed_tests` | Shows that failed runs still become evidence. |

## Artifact Contract

Every gallery row should expose:

- `metadata.json`: machine-readable summary, claim boundary, and artifact paths.
- `report.md`: human-readable run narrative.
- `final.diff`: generated patch or empty-diff evidence.
- `traces.jsonl`: lifecycle, context, runtime, test, and outcome events.
- `logs/stdout.txt` and `logs/stderr.txt`: validation output.
- `context/selected_files.json`: selected files or symbols when available.
