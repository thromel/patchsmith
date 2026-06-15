# Runtime Fairness Checks

PatchSmith compares repair behavior only when the harness contract is stable
across runtimes.

## Invariants

- Every runtime receives the same task text.
- Every runtime receives the same selected context bundle unless the experiment
  is explicitly about context selection.
- Every runtime uses the same validation command.
- No runtime mutates the original repository directly.
- Retry budgets are explicit and recorded.
- Extra hints are visible in the artifact, not hidden in a prompt.
- Provider/model ids and token/cost budgets are recorded before the run.
- Patch application is owned by PatchSmith, not by the model runtime.

## Promotion Gate

A runtime comparison should not be promoted unless the artifact set proves:

1. the task manifest is identical or the intentional difference is documented,
2. the context bundle is identical or the context experiment is named,
3. the same sandbox policy and validation command were used,
4. all retries and feedback are transcripted,
5. every selected run has `report.md`, `final.diff`, `traces.jsonl`, and logs,
6. failure categories are assigned before aggregate claims are written.
