# Comparison Matrix

PatchSmith should be positioned as an evidence harness, not as another coding
agent.

| System | Primary Job | Mutation Owner | Evidence Surface | PatchSmith Difference |
| --- | --- | --- | --- | --- |
| PatchSmith | Audit repair attempts across planners/runtimes. | Harness-owned patch gate and sandbox. | Run directory: context, diff, trace, logs, cost, claim boundary. | Optimizes inspectability and fair comparison before autonomy. |
| SWE-agent-style systems | Let an agent operate in a repo-like environment. | Agent/tool loop. | Trajectory plus benchmark result. | PatchSmith can wrap or compare planners while keeping mutation/validation separate. |
| OpenHands-style systems | General software-engineering agent runtime. | Agent runtime with tools. | Evented runtime state and task outputs. | PatchSmith narrows the task to repair evidence, patch gates, and benchmark discipline. |
| Agentless-style baselines | Deterministic or retrieval-driven patching baselines. | Baseline pipeline. | Patch and validation result. | PatchSmith keeps these as comparable baselines beside live planners. |
| Plain prompt scripts | One-off model instructions. | User or script. | Usually transcript-only. | PatchSmith makes context, patch, validation, logs, and caveats durable artifacts. |
| CI | Validate committed code. | Developer/repo workflow. | Test logs and checks. | PatchSmith records the pre-commit repair attempt and claim boundary before CI. |

## What PatchSmith Is Not

- It is not an autonomous GitHub issue fixer.
- It is not a hosted repair service.
- It is not proof that a focused test pass equals upstream acceptance.
- It is not a leaderboard claim that PatchSmith beats coding agents.
- It is not a replacement for human review.

The project is strongest when it says: agents may propose; PatchSmith owns the
evidence.
