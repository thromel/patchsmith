# Product Boundary Ownership

This document defines module ownership for the refactored product boundaries.
Ownership here means the code area responsible for a product concern, not a
human owner. Changes should stay inside the owning boundary unless the public
contract explicitly crosses into another area.

## Boundaries

| Boundary | Source Surface | Owns | Does Not Own | Focused Tests |
| --- | --- | --- | --- | --- |
| Chat shell | `patchsmith.chat.*`; compatibility wrapper `patchsmith.agent_chat` | REPL controller, slash routing, command registry, command handlers, chat state, hooks, custom commands, transcript writes, task dispatch, terminal formatting. | Repair planning, model invocation, benchmark aggregation, and persisted session reducers. | `tests/chat/*`, with `tests/test_agent_chat.py` retained as scenario smoke coverage. |
| Session evidence | `patchsmith.session.*`; compatibility wrapper `patchsmith.agent_session` | Transcript JSONL store, typed event decoding, saved-session metrics, gates, recommendations, summaries, timelines, and Markdown export. | Interactive command parsing, provider calls, and benchmark result extraction. | `tests/session/*` plus legacy transcript migration coverage. |
| CLI surface | `patchsmith.cli.*` | Parser registration, command grouping, shared agent/chat args, offline saved-session actions, and human-readable command output. | Domain policy and long-running evaluation/report logic beyond thin command handoff. | `tests/cli/*`. |
| DeepAgents runtime interface | `patchsmith.deepagents_*` | Context selection, manifest registry, repair interface, repo instructions, source hints, target history, budget/subagent routing, provider invocation, output parsing, and contract metadata. | Workspace mutation safety, sandbox execution, portfolio reporting, and benchmark gates. | `tests/deepagents/*`. |
| Runtime execution | `patchsmith.runtime.*`, `patchsmith.workflow`, `patchsmith.workflow_context`, `patchsmith.workspace_restore` | Framework-neutral repair execution, attempts, feedback retries, workspace restore, sandbox handoff, and run trace orchestration. | Chat commands, CLI parsing, public portfolio reports, and DeepAgents manifest rendering. | `tests/test_workflow.py`, `tests/test_runtime_feedback.py`, `tests/test_runtime_plan_diagnostics.py`, and runtime-focused slices. |
| Complex benchmark | `patchsmith.evaluation.complex.*`; compatibility wrapper `patchsmith.evaluation.runners.complex` | Complex-suite spec parsing, threshold registry, trace readers, result extraction, selection, summary aggregation, gates, follow-up generation, outputs, compatibility readers, and report rendering. | Public issue materialization/execution and portfolio release reporting. | `tests/evaluation/complex/*`. |
| Issue-corpus evaluation | `patchsmith.evaluation.issue_corpus.*`, issue-corpus CLI helpers, and public issue report modules | Public issue intake, materialization, setup/readiness checks, reproduction specs, focused-test setup/execution, repair readiness, repair attempts, and public issue report rendering. | Complex-suite aggregation and generic chat/session UX. | `tests/evaluation/test_issue_corpus_*.py` and issue-corpus CLI coverage. |
| Portfolio and release evidence | `patchsmith.portfolio.*`, portfolio CLI helpers | Demo/readiness/status reports, quality and release gates, launch blockers, evidence refresh, live-calibration summaries, project-status freshness, and public claim boundaries. | Running repair agents or changing benchmark result semantics. | `tests/portfolio/*`. |
| Retrieval and context | `patchsmith.context*`, `patchsmith.retrieval*`, `patchsmith.code_graph`, `patchsmith.target_localization` | Repository indexing, native/ctxhelm context providers, context packing, retrieval features, code graph expansion, and target localization evidence. | Patch application, runtime retries, and report gating. | `tests/test_context.py`, `tests/test_context_packing.py`, `tests/test_retrieval.py`, and localization coverage. |
| Patch safety and application | `patchsmith.agent_apply`, `patchsmith.agent_diff`, `patchsmith.patch_effects`, `patchsmith.patch_quality`, `patchsmith.patching`, `patchsmith.python_patch_safety`, `patchsmith.security`, `patchsmith.sandbox` | Diff inspection, apply/check/rewind operations, patch quality heuristics, Python patch safety, sandbox policy, and security checks. | Chat UI state, provider prompting, and benchmark report aggregation. | `tests/chat/test_apply_policy.py`, `tests/test_agent_apply.py`, `tests/test_patch_quality.py`, `tests/test_patching.py`, `tests/test_security.py`, and `tests/test_sandbox.py`. |
| Shared models and artifacts | `patchsmith.models`, `patchsmith.evaluation_models*`, `patchsmith.artifacts`, shared report helpers | Stable dataclasses, serialization helpers, artifact IO conventions, and compatibility exports used across boundaries. | Boundary-specific business logic that belongs in chat, session, runtime, benchmark, or portfolio modules. | Model, artifact, and package-specific tests near the consuming boundary. |

## Change Rules

- Compatibility wrappers may re-export old public symbols, but new behavior
  should be implemented in the owning boundary.
- Persisted artifact formats need compatibility tests before field renames or
  nested schema changes. See `docs/22_artifact_compatibility_policy.md`.
- New command families belong in `patchsmith.chat.handlers.*` for interactive
  chat behavior and `patchsmith.cli.commands.*` for process-level CLI behavior.
- New DeepAgents manifests should be added through the manifest registry and
  covered by focused `tests/deepagents/*` tests.
- New release or portfolio evidence must include claim-boundary language and a
  focused report-writer test.
