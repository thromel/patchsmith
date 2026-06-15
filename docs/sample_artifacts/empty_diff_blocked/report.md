# PatchSmith Sample: Empty Diff Blocked

The run produced no patch. PatchSmith records this as `empty_diff` and blocks
review/apply promotion.

```text
Diff risk review:
- Risk: not_available
- Decision: blocked
- Finding: empty_diff
```

This is not a model-quality success or failure claim. It is evidence that the
harness did not let an empty artifact pass as a safe patch.
