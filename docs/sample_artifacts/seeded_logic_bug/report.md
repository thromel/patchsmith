# PatchSmith Sample Run Report

## Summary

- Run ID: `sample-seeded-logic-bug`
- Status: `completed`
- Runtime: `heuristic`
- Planner: `heuristic`
- Retrieval: `native_hybrid`
- Sandbox: `local`
- Patch generation: `patch_generated`
- Claim boundary: `focused_validation_only`

The issue says `add(2, 3)` returns `-1` instead of `5`. PatchSmith selected the
implementation and its focused test, proposed a one-line patch, and validated it
with `python3 -m pytest`.

## Retrieved Context

1. `src/simple_calc.py`
2. `tests/test_simple_calc.py`

## Final Diff

```diff
--- a/src/simple_calc.py
+++ b/src/simple_calc.py
@@ -1,5 +1,5 @@
 def add(left: int, right: int) -> int:
-    return left - right
+    return left + right


 def subtract(left: int, right: int) -> int:
```

## Validation

```text
tests/test_simple_calc.py ..                                             [100%]
2 passed
```

## Final Verdict

`patch_validated`

This focused pass is useful evidence for the seeded fixture. It is not an
upstream-acceptance claim.
