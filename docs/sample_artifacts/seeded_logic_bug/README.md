# Sample Artifact Bundle: Seeded Logic Bug

This directory is a static, source-controlled preview of the canonical
`patchsmith demo seeded-logic-bug` run. It lets readers inspect the shape of a
PatchSmith run without generating local artifacts first.

The live command is:

```bash
patchsmith demo seeded-logic-bug
```

The generated run directory contains the same artifact classes shown here:

- `report.md`: human-readable run report.
- `final.diff`: the proposed bounded patch.
- `traces.sample.jsonl`: representative trace events.
- `metadata.json`: machine-readable run summary and claim boundary.
- `context/selected_files.json`: selected source/test context.
- `logs/stdout.txt` and `logs/stderr.txt`: validation output.

Claim boundary: `focused_validation_only`. This sample proves that the harness
can retrieve context, propose a bounded patch, validate it with the configured
focused command, and preserve evidence. It does not claim broad upstream
acceptance or real public-issue repair quality.
