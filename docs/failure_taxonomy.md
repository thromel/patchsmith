# Failure Taxonomy

PatchSmith treats failed attempts as useful evidence. A failed run should explain
which harness layer failed before anyone compares planner quality.

## Core Categories

| Category | Layer | Meaning | Next Action |
| --- | --- | --- | --- |
| `validated` | validation | Patch generated and focused validation passed. | Review diff and broaden validation before claiming more. |
| `validated_with_warnings` | validation | Focused validation passed, but patch quality risk is high. | Human review before promotion. |
| `no_patch_generated` | planner | Runtime did not produce a usable patch. | Inspect trace, improve context or feedback. |
| `empty_diff` | patch gate | Generated patch artifact is empty or has no changed files. | Treat as no patch; do not apply. |
| `malformed_patch_plan` | patch gate | Structured patch proposal cannot be interpreted safely. | Feed parser error back to planner. |
| `old_span_not_found` | patch gate | Target span was not found in the current repository snapshot. | Refresh context or reject stale patch. |
| `unsafe_path_rejected` | patch gate | Patch targets outside the allowed workspace or policy boundary. | Reject patch and inspect prompt/tool scope. |
| `test_failure_after_patch` | validation | Patch applied, but focused validation failed. | Use stdout/stderr as retry feedback. |
| `tests_do_not_reproduce_issue` | validation | Tests pass without a patch. | Re-check reproduction command. |
| `missing_test_command` | validation | No validation command was available. | Add focused validation before judging repair quality. |
| `test_environment_policy_blocked` | sandbox | Command policy blocked the validation command. | Adjust allowed command or fixture. |
| `test_environment_timeout` | sandbox | Validation exceeded the sandbox timeout. | Tighten command or increase controlled timeout. |
| `test_environment_missing_pytest` | sandbox | Fixture cannot run because pytest is missing. | Fix environment setup before model retries. |
| `model_preflight_blocked` | provider | Live model auth or model availability failed before a run. | Fix credentials/model id before spending. |
| `budget_preflight_blocked` | provider | Estimated budget would be exceeded before a run. | Lower scope or raise explicit budget. |

## Reporting Rule

Reports and benchmark rows should separate:

- setup and provider preflight failures,
- planner failures,
- patch-shape failures,
- sandbox/validation failures,
- validated runs with warning-level evidence.

This prevents benchmark rows from mixing "the model could not repair the bug"
with "the task never had a valid validation environment."
