# Release and Portfolio Plan

## Status

Draft v0.1

## Purpose

PatchSmith Research is both a working engineering project and a portfolio artifact. This document defines how to package it so recruiters, engineers, and research-oriented reviewers can understand its value quickly.

## Public positioning

Use this description:

> PatchSmith Research is an AI software-maintenance agent and evaluation lab that converts GitHub issues into tested patch diffs. It uses LangGraph-based orchestration, codebase retrieval, sandboxed execution, patch candidate search, and SWE-bench-style evaluation to study what makes coding agents reliable.

## Public repository requirements

The repository should include:

- polished README,
- demo GIF or video link,
- architecture diagram,
- quickstart commands,
- example run report,
- evaluation results,
- failure analysis,
- safety notes,
- roadmap,
- clean code structure,
- CI status badge if available.

## README outline

```markdown
# PatchSmith Research

## Demo
## Why this project exists
## What it does
## Architecture
## Features
## Research questions
## Evaluation results
## Example run
## Safety model
## Tech stack
## Quickstart
## Roadmap
## Limitations
```

## Demo video

Target length: 2 to 4 minutes.

### Demo script

1. Show the problem: real GitHub issue to tested patch is hard.
2. Submit issue to PatchSmith.
3. Show repo indexing and retrieval.
4. Show agent plan.
5. Show patch candidate generation.
6. Show sandboxed tests.
7. Show final diff and report.
8. Show evaluation dashboard.
9. Close with research comparison: baseline vs advanced mode.

### Current reproducible demo command

Generate the launch review surface from saved artifacts:

```bash
PYTHONPATH=src python3 -m patchsmith.cli demo-readiness \
  --artifacts-dir artifacts \
  --output artifacts/experiments/demo_readiness.md \
  --json-output artifacts/experiments/demo_readiness.json \
  --json
```

Current local evidence reports `ready_with_caveats`: the offline seeded-suite demo, dashboard, and failure-analysis artifacts are coherent, while live LLM calibration remains a clearly labeled follow-up unless non-offline provider metadata appears in saved artifacts.

Generate the timed recording script:

```bash
PYTHONPATH=src python3 -m patchsmith.cli demo-script \
  --artifacts-dir artifacts \
  --output artifacts/experiments/demo_script.md \
  --json-output artifacts/experiments/demo_script.json \
  --json
```

The current generated script targets a 3 minute 10 second walkthrough with six sections: problem thesis, evidence dashboard, runtime comparison, patch-search tradeoff, failure transparency, and caveats.

Generate demo media assets:

```bash
PYTHONPATH=src python3 -m patchsmith.cli demo-media \
  --artifacts-dir artifacts \
  --output artifacts/experiments/demo_media.md \
  --svg-output artifacts/experiments/demo_media.svg \
  --png-output artifacts/experiments/demo_media.png \
  --json-output artifacts/experiments/demo_media.json \
  --json
```

Current demo media output includes a readable SVG summary and compact PNG preview generated from saved evidence.

Generate the live calibration readiness report:

```bash
PYTHONPATH=src python3 -m patchsmith.cli live-calibration \
  --artifacts-dir artifacts \
  --output artifacts/experiments/calibration_readiness.md \
  --json-output artifacts/experiments/calibration_readiness.json \
  --json
```

Current live calibration readiness output is `not_configured`: the OpenAI SDK is importable locally, but `OPENAI_API_KEY` is not set and saved provider evidence is offline-only. DeepAgents has 10 saved package-backed adapter smoke runs and 30 compatibility-mode runs; this proves optional-package import compatibility, not live DeepAgents model quality. OpenAI Agents SDK has 10 saved package-backed adapter smoke runs and 20 compatibility-mode runs; this proves optional-package import compatibility, not live OpenAI Agents model quality.

Generate the live calibration execution plan:

```bash
PYTHONPATH=src python3 -m patchsmith.cli live-calibration-plan \
  --artifacts-dir artifacts \
  --output artifacts/experiments/live_calibration_plan.md \
  --json-output artifacts/experiments/live_calibration_plan.json \
  --json
```

Current live calibration plan output is `blocked` until `OPENAI_API_KEY` is configured. It records the required single-task live OpenAI smoke, follow-up seeded-suite eval, optional adapter refresh commands, success evidence, and claim boundaries without counting as live-provider evidence.

Generate the final evaluation narrative:

```bash
PYTHONPATH=src python3 -m patchsmith.cli final-evaluation \
  --artifacts-dir artifacts \
  --output artifacts/experiments/final_evaluation.md \
  --json-output artifacts/experiments/final_evaluation.json \
  --json
```

Current final evaluation output has `ready_with_caveats`, 29 normalized metric rows, nine decision bullets, and six limitations. Use it as the public-claim boundary for the offline seeded-suite portfolio demo.

Generate the launch blocker backlog:

```bash
PYTHONPATH=src python3 -m patchsmith.cli launch-blockers \
  --artifacts-dir artifacts \
  --output artifacts/experiments/launch_blockers.md \
  --json-output artifacts/experiments/launch_blockers.json \
  --json
```

Current launch blocker output is `ready_with_warnings`: Docker smoke is ready and focused public issue setup-readiness is warning-class rather than blocked. Live-provider calibration, release hygiene, and public issue setup-validation failures remain caveats. The generated backlog includes dependency-chain and remediation-command sections so the blocker order and next runnable commands are preserved with the evidence.

Generate the MVP progress report:

```bash
PYTHONPATH=src python3 -m patchsmith.cli mvp-progress \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/mvp_progress.md \
  --json-output artifacts/experiments/mvp_progress.json \
  --json
```

Current MVP progress output is `ready_with_caveats` at `96.7%`: 28 evidence-backed checklist items pass, two are warnings, and no item is blocked or missing. Use it as the snapshot answer for "how far are we?" while keeping the live-calibration warning explicit.

Generate the consolidated project status report:

```bash
PYTHONPATH=src python3 -m patchsmith.cli project-status \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/project_status.md \
  --json-output artifacts/experiments/project_status.json \
  --json
```

Current project-status output is the status briefing artifact. It reads saved evidence from the MVP progress, delivery audit, quality gate, launch blocker, Docker smoke, live calibration, final evaluation, artifact index, and release hygiene reports without rerunning those checks.

Refresh the lightweight review evidence bundle:

```bash
PYTHONPATH=src python3 -m patchsmith.cli refresh-evidence \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/evidence_refresh.md \
  --json-output artifacts/experiments/evidence_refresh.json \
  --json
```

Current evidence-refresh output records the review-artifact regeneration order, per-step status, duration, output paths, and skipped quality-gate status. Use it after code/doc changes to refresh portfolio evidence without accidentally running Docker or live-provider work.

Run the executable quality gate:

```bash
PYTHONPATH=src python3 -m patchsmith.cli quality-gate \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/quality_gate.md \
  --json-output artifacts/experiments/quality_gate.json \
  --logs-dir artifacts/experiments/quality_gate_logs \
  --json
```

Current quality-gate output is a required release review artifact. It records compileall, whitespace diff check, full pytest, package build, exit codes, durations, and per-command stdout/stderr logs.

Generate the delivery audit:

```bash
PYTHONPATH=src python3 -m patchsmith.cli delivery-audit \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/delivery_audit.md \
  --json-output artifacts/experiments/delivery_audit.json \
  --json
```

Current delivery audit output is `in_progress_with_blockers`: requirements, roadmaps, sprint plans, process docs, development commits, executable quality-gate evidence, saved evaluation artifacts, Docker smoke evidence, and the live-calibration execution plan are present, while public issue setup validation and live LLM calibration remain blocker-class evidence gaps.

Generate the Docker smoke report:

```bash
PYTHONPATH=src python3 -m patchsmith.cli docker-smoke \
  --project-root . \
  --artifacts-dir artifacts \
  --image patchsmith-seeded-smoke:py312 \
  --output artifacts/experiments/docker_smoke.md \
  --json-output artifacts/experiments/docker_smoke.json \
  --json
```

Current Docker smoke output records a passing seeded Docker run when Docker is reachable, including Docker-related environment/socket diagnostics, host-side Docker Desktop/Colima hints, and remediation commands. A passing Docker smoke artifact is required before claiming Docker-sandboxed seeded tests.

Generate the public issue corpus report:

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-issue-corpus \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Current corpus output should validate three public GitHub issue candidates. Use it to show real-world task-breadth planning, not solved issue quality.

Preflight the public issue repositories:

```bash
PYTHONPATH=src python3 -m patchsmith.cli preflight-issue-corpus \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Current preflight output should show both public repositories reachable. Use it before converting corpus entries into executable eval tasks.

Preview public issue context retrieval:

```bash
PYTHONPATH=src python3 -m patchsmith.cli preview-issue-corpus-context \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --context-provider native_hybrid \
  --top-k 5 \
  --json
```

Current context-preview output should complete all three public issue candidates with source-free retrieved-file summaries. Use it as clone/index/retrieval evidence only; it does not prove public issue repair quality.

Materialize public issue task manifests:

```bash
PYTHONPATH=src python3 -m patchsmith.cli materialize-issue-corpus-tasks \
  --corpus evals/issue_corpora/public_issue_smoke_v1/issues.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Current materialization output should write three source-free task manifests and runbooks. Use it as external-evaluation setup evidence only; it does not prove public issue reproduction or repair quality.

Validate materialized public issue tasks:

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-materialized-issue-tasks \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Current materialized-task validation output should report three valid tasks, zero errors, zero warnings, and source-free manifests. Use it as external-evaluation setup validation only; it does not prove public issue reproduction or repair quality.

Check materialized public issue run readiness:

```bash
PYTHONPATH=src python3 -m patchsmith.cli check-materialized-run-readiness \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Current run-readiness output should show zero blocked tasks and three warning-classified tasks because the suggested public-repo test commands are policy-allowed but run full pytest suites on medium or large repositories.

Plan focused public issue tests:

```bash
PYTHONPATH=src python3 -m patchsmith.cli plan-materialized-focused-tests \
  --tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --max-paths 2 \
  --json
```

Current focused-test output should plan three policy-allowed scoped pytest commands, with zero fallbacks and zero blocked commands. Use it to reduce full-suite execution risk before attempting public issue repairs.

Run focused public issue tests:

```bash
PYTHONPATH=src python3 -m patchsmith.cli run-materialized-focused-tests \
  --plan artifacts/experiments/public_issue_corpus_v1/focused_test_plan_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --timeout-seconds 60 \
  --json
```

Current focused-run output attempts three scoped public-repo commands, with zero blocked commands and three failures. The pytest task currently fails before collection because the checked-out snapshot lacks generated `_pytest._version`; the requests tasks currently collect 341 tests but fail setup around the `httpbin` fixture. Use this as environment-readiness evidence, not repair success evidence.

Diagnose focused public issue test failures:

```bash
PYTHONPATH=src python3 -m patchsmith.cli diagnose-focused-test-runs \
  --results artifacts/experiments/public_issue_corpus_v1/focused_test_run_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Current diagnosis output classifies one dependency issue, two environment issues, zero timeouts, zero blocked tasks, and zero unknown failures. Use it as a dependency/setup backlog before making public issue repair claims.

Plan focused public issue setup:

```bash
PYTHONPATH=src python3 -m patchsmith.cli plan-focused-test-setups \
  --diagnosis artifacts/experiments/public_issue_corpus_v1/focused_test_diagnosis_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Current setup-plan output has three planned setup tasks, one dependency setup, two environment fixture setups, and three network/sandbox-required tasks. Use this to gate future public issue reproduction attempts.

Check focused public issue setup readiness:

```bash
PYTHONPATH=src python3 -m patchsmith.cli check-focused-test-setup-readiness \
  --setup-plan artifacts/experiments/public_issue_corpus_v1/focused_test_setup_plan_results.json \
  --docker-smoke artifacts/experiments/docker_smoke.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Current setup-readiness output has zero blocked tasks and three warning-class tasks because each setup requires reviewed networked Docker execution. Use this as a reviewed gate before public issue dependency setup is executed.

Dry-run focused public issue setup execution:

```bash
PYTHONPATH=src python3 -m patchsmith.cli execute-focused-test-setups \
  --readiness artifacts/experiments/public_issue_corpus_v1/focused_test_setup_readiness_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Current setup-execution output completes all three setup tasks in Docker with explicit warning, dependency-install, and bridge-network approval. This artifact is setup evidence only; it does not prove public issue repair quality.

The default command policy still blocks dependency installation. Setup execution only permits the narrow editable-install setup policy when `--allow-dependency-installs` is set with Docker mode; networked dependency setup must also use an explicit sandbox network such as `--sandbox-network bridge` and remain labeled in reports.

Dry-run focused public issue setup validation:

```bash
PYTHONPATH=src python3 -m patchsmith.cli validate-focused-test-setups \
  --setup-execution artifacts/experiments/public_issue_corpus_v1/focused_test_setup_execution_results.json \
  --output artifacts/experiments/public_issue_corpus_v1 \
  --json
```

Current setup-validation output executes all three validation commands and fails all three on upstream test-environment issues: the pytest snapshot reports its own dev version below its configured `minversion`, and the requests snapshots hit a recursive `httpbin` fixture dependency. This is setup/reproduction evidence, not repair-quality evidence.

Generate the release hygiene report:

```bash
PYTHONPATH=src python3 -m patchsmith.cli release-hygiene \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/release_hygiene.md \
  --json-output artifacts/experiments/release_hygiene.json \
  --json
```

Current release hygiene output is `ready_with_warnings`: generated review artifacts now include quality-gate, project-status, project-status freshness, environment-readiness, calibration-readiness, live-calibration plan, delivery audit, launch-blocker, and public issue context-preview/materialization validation/readiness/focused-test plan/run/diagnosis/setup-plan/setup-readiness/setup-execution/setup-validation evidence, package build metadata exists, local Git metadata exists, and the remaining release caveats are unproven live LLM calibration plus warning-class environment/setup evidence.

## Example flagship demo scenario

Ideal demo issue:

- small enough to run quickly,
- real enough to be credible,
- has failing tests or easy validation,
- retrieval is non-trivial,
- agent needs at least one tool call and one test run,
- final patch is understandable.

## Blog post series

### Post 1

Title:

`Building an AI code-repair agent from GitHub issue to tested patch`

Focus:

- system overview,
- product motivation,
- end-to-end flow.

### Post 2

Title:

`Why embeddings-only code retrieval was not enough`

Focus:

- retrieval ablation,
- symbol search,
- graph retrieval,
- touched-file recall.

### Post 3

Title:

`Evaluating coding agents beyond vibes`

Focus:

- seeded bug suite,
- metrics,
- failure categories,
- cost and latency.

### Post 4

Title:

`Designing safe tool use for AI agents that run code`

Focus:

- sandbox,
- command policy,
- prompt injection,
- human approval gates.

## Resume bullets

```text
Built PatchSmith Research, an AI software-maintenance agent that converts GitHub issues into tested patch diffs using LangGraph orchestration, hybrid code retrieval, opt-in Docker sandboxing, and evaluation-driven development.

Implemented a research harness comparing Agentless, LangGraph, DeepAgents, OpenAI Agents SDK, and patch-search scaffolds across success rate, retrieval hit rate, cost, latency, and failure modes.

Designed a Code Context Graph combining files, symbols, imports, tests, stack traces, and retrieval signals to improve fault-localization analysis over simple embeddings.

Built an execution-grounded patch-search system that generates multiple candidate diffs, runs targeted tests in isolated sandboxes, and selects final patches using test and review signals.
```

## Release milestones

### Internal alpha

Criteria:

- CLI works,
- one seeded bug solved or attempted end-to-end,
- run report generated,
- safety checklist partially implemented.

### Public technical preview

Criteria:

- clean README,
- Docker Compose setup,
- 5 to 10 seeded tasks,
- baseline metrics,
- demo video.

### Portfolio release

Criteria:

- polished UI or polished CLI demo,
- three experiment reports,
- failure analysis,
- architecture diagram,
- stable tagged release.

## Portfolio quality bar

A recruiter should understand the project in 60 seconds.

A senior engineer should find credible architecture in 10 minutes.

A research-oriented reviewer should find meaningful experiments in 20 minutes.

## Limitations to state publicly

- The system provides PR-ready patch suggestions, not unsupervised production changes.
- Public demo may use preselected repositories for safety and reproducibility.
- Results depend on repository setup quality and test coverage.
- Advanced research modes may be more expensive and slower than baseline modes.

## Assets checklist

- [x] README with demo media path.
- [x] Architecture diagram.
- [ ] Final run report sample.
- [x] Evaluation results table.
- [x] Failure cases.
- [x] Timed demo script.
- [x] Demo media asset.
- [x] Final evaluation narrative.
- [x] Release hygiene checklist.
- [x] CI workflow.
- [ ] Safety note.
- [ ] Blog post draft.
- [ ] Resume bullets.
- [ ] LinkedIn project summary.
