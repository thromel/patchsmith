# Delivery Process

## Status

Draft v0.1

## Purpose

This document defines the delivery process for PatchSmith Research. It turns the project principles into a repeatable engineering loop with planning, implementation, verification, documentation, and release gates.

## Process model

PatchSmith uses a lightweight Agile plus research-gate process:

```text
Sprint plan -> Implement vertical slice -> Verify -> Evaluate -> Document -> Decide
```

This is intentionally not a heavyweight enterprise process. The project still needs professional controls because it handles untrusted code, generated patches, model calls, and research claims.

## Work item lifecycle

```text
idea -> ready -> in progress -> verification -> documented -> accepted
                       \-> blocked
                       \-> cut
```

### Ready

A task can start when it has:

- a user-visible or research-visible outcome,
- an acceptance criterion,
- known safety impact,
- a verification command or artifact,
- a narrow enough scope for one sprint.

### In progress

Implementation should:

- prefer vertical slices over horizontal infrastructure,
- preserve adapter boundaries,
- add tests at the layer touched,
- emit trace events for runtime behavior,
- keep artifacts inspectable.

### Verification

Verification should include the smallest sufficient combination of:

- unit tests,
- integration tests,
- seeded bug run,
- retrieval eval run,
- safety-policy regression test,
- generated report inspection.

### Documented

Docs must be updated when the change affects:

- requirements,
- roadmap,
- architecture,
- safety,
- evaluation,
- runbook,
- public portfolio claims.

### Accepted

A task is accepted only when evidence proves the acceptance criteria. Intent, partial implementation, or plausible behavior is not enough.

## Required gates

### Gate A: Code quality

Required for every implementation sprint:

```bash
PYTHONPATH=src python3 -m patchsmith.cli quality-gate \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/quality_gate.md \
  --json-output artifacts/experiments/quality_gate.json \
  --logs-dir artifacts/experiments/quality_gate_logs \
  --json
```

The executable gate runs compileall, whitespace diff checks, the full pytest suite, and package build. Use focused pytest commands during implementation, then regenerate the quality-gate artifact before sprint review.

### Gate B: Runtime safety

Required when command execution, sandboxing, patching, or external tools change:

- command allowlist tests pass,
- path traversal tests pass,
- Docker runner command construction and environment filtering tests pass when Docker mode changes,
- `docker-smoke` is regenerated when Docker sandbox evidence changes,
- no host secrets are intentionally mounted,
- unsafe commands are rejected before execution.

### Gate C: Artifact integrity

Required when reports, traces, or evals change:

- run artifacts are saved under `artifacts/`,
- reports are readable without raw logs,
- source-bearing artifacts are not copied into public reports,
- trace events include enough metadata to debug failures.

### Gate D: Research integrity

Required when experiment results are produced:

- dataset and config are recorded,
- baseline is included,
- cost and latency are reported next to quality metrics,
- failed cases are preserved,
- conclusions distinguish quality gains from cost increases.

## Planning artifacts

Tracked planning docs:

- `docs/09_roadmap.md` for milestone sequence,
- `docs/17_sprint_plans.md` for sprint decomposition,
- `docs/18_delivery_process.md` for execution process,
- `experiments/*.md` for research plans,
- `adr/*.md` for accepted architectural decisions.

Generated artifacts:

- `artifacts/runs/{run_id}/report.md`,
- `artifacts/runs/{run_id}/traces.jsonl`,
- `artifacts/experiments/{experiment_id}/report.md`,
- `artifacts/experiments/{experiment_id}/results.csv`,
- `artifacts/experiments/index.md`,
- `artifacts/experiments/failure_report.md`,
- `artifacts/experiments/demo_readiness.md`,
- `artifacts/experiments/calibration_readiness.md`,
- `artifacts/experiments/demo_script.md`,
- `artifacts/experiments/demo_media.svg`,
- `artifacts/experiments/demo_media.png`,
- `artifacts/experiments/quality_gate.md`,
- `artifacts/experiments/quality_gate.json`,
- `artifacts/experiments/final_evaluation.md`,
- `artifacts/experiments/release_hygiene.md`.

Generated artifacts are not tracked by default, but they are authoritative evidence for sprint review.

## Sprint review format

Each sprint review should answer:

1. What was the sprint goal?
2. What changed in code?
3. What command proves the main workflow?
4. What artifacts were produced?
5. What failed or remained incomplete?
6. What decision does this evidence support?
7. What is the next sprint task?

## Change control

Use an ADR when:

- a framework becomes first-class,
- a safety boundary changes,
- a storage or data contract changes,
- a research lane becomes a product default,
- a reversal would be expensive.

Use an experiment plan when:

- the work makes a quality claim,
- two strategies are compared,
- model, retrieval, scaffold, or search behavior changes,
- the result should influence roadmap priority.

Use the risk register when:

- a new high-impact failure mode appears,
- a mitigation changes,
- public demo safety changes,
- dependency or cost risk changes.

## Current delivery decision

The active implementation work is Sprint 10 portfolio launch execution. Static artifact indexing, failure inspection, demo-readiness reporting, live-calibration readiness reporting and execution planning, objective-to-evidence delivery auditing, launch-blocker reporting with dependency-chain remediation commands, focused setup-execution gating, focused setup-validation gating, Docker-only setup dependency policy, demo-script generation, demo-media generation, final-evaluation reporting, executable quality-gate reporting, release-hygiene reporting, package build metadata, CI workflow coverage, demo media, architecture evidence, and local Git metadata now provide the review surface. The next implementation work should focus on resolving Docker smoke availability, unblocking focused public issue setup-readiness, and running live-provider calibration only when credentials and budget are available while keeping offline seeded-suite claims separate from live LLM quality claims.
