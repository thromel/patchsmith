# Sample Artifact Bundle: Empty Diff Blocked

This static sample shows the patch-review gate doing useful negative work. A
run with no generated patch should not be treated as low risk or ready to apply.

Claim boundary: `artifact_only`.

Key evidence:

- `metadata.json` records `empty_diff`.
- `final.diff` is intentionally empty.
- `traces.sample.jsonl` records a blocked diff review.
