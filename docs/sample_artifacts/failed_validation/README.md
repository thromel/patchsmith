# Sample Artifact Bundle: Failed Validation

This static sample shows a run that generated a patch but failed focused
validation. PatchSmith keeps the diff and logs instead of collapsing the row
into a generic failure.

Claim boundary: `focused_validation_only`.

Key evidence:

- `final.diff` contains a plausible but wrong patch.
- `logs/stdout.txt` preserves the failed assertion.
- `metadata.json` records `test_failure_after_patch`.
