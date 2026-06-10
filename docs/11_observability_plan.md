# Observability Plan

## Status

Draft v0.5. Static artifact-index, normalized metrics dashboard, and generated run-detail MVP are implemented for saved experiment review.

## Purpose

PatchSmith Research must be debuggable. Agent systems fail in opaque ways unless every model call, tool call, sandbox command, patch, and test result is observable.

## Observability goals

- understand why a run succeeded or failed,
- compare runtime scaffolds,
- measure cost and latency,
- debug tool and sandbox failures,
- support portfolio screenshots,
- support experiment reports.

## Telemetry types

### Traces

A trace captures the sequence of events in an agent run.

Required span/event types:

- run created,
- repo cloned,
- indexing started/completed,
- retrieval query,
- context packed,
- model call,
- tool call,
- file edit,
- patch generated,
- sandbox command,
- test result,
- failure analysis,
- retry decision,
- final review,
- report generated.

### Metrics

Required metrics:

- run count by status,
- average run latency,
- average model latency,
- average sandbox latency,
- average cost,
- token usage,
- test pass rate,
- timeout rate,
- unsafe command rejection count,
- retrieval top-k recall during eval.

### Logs

Logs should be structured. Avoid dumping huge model prompts into normal logs. Store large artifacts separately.

Log fields:

- timestamp,
- run ID,
- node name,
- event type,
- status,
- error code,
- short message.

### Artifacts

Artifacts include:

- final diff,
- patch candidates,
- stdout/stderr,
- final report,
- retrieval context,
- trace JSON,
- experiment result CSV.

## Trace schema

```json
{
  "run_id": "uuid",
  "event_id": "uuid",
  "parent_event_id": "uuid-or-null",
  "node_name": "planning_node",
  "event_type": "model_call",
  "status": "completed",
  "started_at": "timestamp",
  "completed_at": "timestamp",
  "latency_ms": 1234,
  "model": "model-name",
  "input_tokens": 1200,
  "output_tokens": 350,
  "estimated_cost": 0.02,
  "input_summary": "short summary",
  "output_summary": "short summary",
  "error": null
}
```

## Run report structure

Every run should produce a Markdown report:

```markdown
# PatchSmith Run Report

## Summary
## Input
## Repository Snapshot
## Runtime Configuration
## Retrieved Context
## Patch Candidates
## Test Results
## Final Diff
## Cost and Latency
## Trace Summary
## Risk Notes
## Final Verdict
```

## Dashboard views

### Run detail view

Show:

- status,
- issue summary,
- selected runtime,
- retrieved files,
- current phase,
- final diff,
- test results,
- trace timeline.

### Experiment dashboard

Show:

- aggregate success,
- cost,
- latency,
- retrieval metrics,
- failure categories,
- comparison by runtime.

Current MVP:

- `patchsmith index-artifacts` generates `artifacts/experiments/index.md`,
- optional JSON output supports future UI adapters,
- optional HTML output generates `artifacts/experiments/index.html`,
- each indexed experiment shows kind, report path, summary path, results path, result count, nested run count, and update timestamp,
- the static dashboard provides normalized research metrics, search, kind filtering, result/run load bars, and links into saved reports/results,
- Markdown and HTML show the latest 25 run artifacts with report, trace, diff, stdout, and stderr links,
- optional run-detail output writes `artifacts/experiments/run-details/{run_id}.html`,
- run-detail pages render trace timeline, retrieved context paths, context broker targets, diff preview, and log previews,
- JSON records normalized metric rows and the full discovered run list for future UI work.

## Cost tracking

Every model call should record:

- provider,
- model,
- input tokens,
- output tokens,
- cached tokens where available,
- estimated cost,
- node name,
- run ID.

Cost should be reported at:

- model call level,
- run level,
- experiment level.

## Failure categories

Use standardized categories:

- `clone_failed`,
- `install_failed`,
- `indexing_failed`,
- `retrieval_failed`,
- `model_failed`,
- `patch_apply_failed`,
- `test_failed`,
- `test_timeout`,
- `sandbox_failed`,
- `unsafe_command_rejected`,
- `max_iterations_reached`,
- `no_patch_generated`,
- `unknown`.

## Minimum MVP observability

The MVP must record:

- run lifecycle status,
- retrieved files,
- model call summaries,
- tool calls,
- sandbox commands,
- test output,
- final diff,
- cost estimate,
- latency,
- saved experiment/run artifact index,
- static artifact dashboard,
- normalized experiment metrics from saved summary/results JSON,
- run report/trace/diff drill-down links,
- generated run-detail pages for current demo runs,
- failure review report with repair-outcome categories and links back to run artifacts,
- demo readiness report with launch gates, caveats, and regeneration commands,
- live calibration plan with credential-gated run matrix, commands, and claim boundaries,
- generated demo script with timed segments and artifact review path,
- generated demo media assets for README or presentation use,
- final evaluation report with decisions, limitations, metric rows, and claim boundaries,
- launch blocker backlog with prioritized Docker, setup-readiness, live-calibration, and release actions,
- focused setup-execution report with dry-run, command-policy, sandbox, and blocked-execution evidence,
- focused setup-validation report with post-setup validation dry-run/execution evidence,
- release hygiene report with blockers, warnings, and launch checklist status.

## Portfolio screenshots to capture

- trace timeline,
- candidate patch comparison,
- final diff view,
- retrieval ranking table,
- evaluation metrics dashboard,
- artifact index table,
- failure analysis report.
- demo readiness report.
- live calibration plan.
- demo script.
- demo media.
- final evaluation report.
- launch blocker backlog.
- focused setup-execution report.
- focused setup-validation report.
- release hygiene report.
