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

Generate the final evaluation narrative:

```bash
PYTHONPATH=src python3 -m patchsmith.cli final-evaluation \
  --artifacts-dir artifacts \
  --output artifacts/experiments/final_evaluation.md \
  --json-output artifacts/experiments/final_evaluation.json \
  --json
```

Current final evaluation output has `ready_with_caveats`, 29 normalized metric rows, nine decision bullets, and six limitations. Use it as the public-claim boundary for the offline seeded-suite portfolio demo.

Generate the release hygiene report:

```bash
PYTHONPATH=src python3 -m patchsmith.cli release-hygiene \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/release_hygiene.md \
  --json-output artifacts/experiments/release_hygiene.json \
  --json
```

Current release hygiene output is `ready_with_warnings`: generated review artifacts now include calibration-readiness evidence, package build metadata exists, local Git metadata exists, and the remaining release caveat is live LLM calibration.

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
