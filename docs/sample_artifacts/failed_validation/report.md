# PatchSmith Sample: Failed Validation

The run generated a patch, but the focused validation command failed.

```diff
-    return left - right
+    return left * right
```

```text
assert add(2, 3) == 5
E assert 6 == 5
```

The important part is not that the patch failed. The important part is that the
run remains inspectable: the proposed diff, validation output, and failure
category survive after the terminal session ends.
