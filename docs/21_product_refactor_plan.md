# PatchSmith Product Refactor Plan

Date: 2026-06-15

This review treats the current worktree as the source of truth. The codebase is
test-green, but it is structurally still closer to a fast-moving research system
than a long-lived product. The main risk is not that the agent fails today; it
is that future agent features require coordinated edits across very large
modules, repeated threshold lists, untyped transcript payloads, and monolithic
tests.

## Current Evidence

- Source size: 286 Python files under `src/patchsmith`, about 60.3k lines.
- Test size: 111 Python files under `tests`, about 35.0k lines.
- Largest source files:
  - `src/patchsmith/runtime/attempts.py`: 1108 lines.
  - `src/patchsmith/runtime/feedback.py`: 735 lines.
  - `src/patchsmith/session/recommendations.py`: 716 lines.
  - `src/patchsmith/evaluation/issue_corpus/public_issue_repairs.py`: 637 lines.
  - `src/patchsmith/evaluation/complex/summary.py`: 631 lines.
  - `src/patchsmith/workflow.py`: 625 lines.
  - `src/patchsmith/agent_cli.py`: 608 lines.
  - `src/patchsmith/session/metrics.py`: 588 lines.
- Largest tests:
  - `tests/test_agent_chat.py`: 3661 lines.
  - `tests/evaluation/test_runners.py`: 2608 lines.
  - `tests/evaluation/test_issue_corpus_public_issues.py`: 2586 lines.
  - `tests/test_deepagents_planner.py`: 2398 lines.
  - `tests/test_cli.py`: 1770 lines.
- Current validation:
  - `uv run ruff check src tests docs README.md`: passed.
  - `uv run mypy src`: passed on 286 source files.
  - `uv run pytest -q`: 742 passed.
- Current local smoke:
  - `patchsmith chat` persisted a natural-language memory note and reloaded it
    from `.patchsmith/instructions.md`.

## Package Inventory

PatchSmith already has useful domain folders, but too much product logic still
lives in root-level modules. That is why the current package tree feels flatter
than the product actually is.

| Area | Files | Lines | Read |
| --- | ---: | ---: | --- |
| root modules | 89 | 18506 | Agent shell compatibility, DeepAgents, workflow, retrieval, patching, models, safety, and mixed helpers are still colocated. |
| evaluation | 62 | 15132 | Rich benchmark functionality; the complex-suite runner is now thin, but CLI and issue-corpus flows still need simplification. |
| portfolio | 52 | 9188 | Public status/evidence reporting is separated, but many modules are report-fragment style rather than domain services. |
| cli | 31 | 5591 | Command surface is split by broad command groups: agent, chat/offline session actions, model preflight, direct repository commands, shared agent argument/config helpers, and shared run-result output are isolated; `run.py` now owns only the legacy issue-to-report command. |
| chat | 27 | 4085 | Command handlers, custom command fallback, command registry, task execution, resume hydration, controller lifecycle, hooks, transcript recording, terminal formatting, and shared replay helpers are split out. |
| session | 9 | 2612 | Typed store/metrics/gates/reporting are split out behind compatibility exports. |
| runtime | 6 | 2414 | Runtime execution is compact relative to evaluation/chat, but attempt and feedback modules are large. |
| observability | 10 | 2321 | HTML/report rendering is reasonably isolated. |

Top internal coupling hotspots by number of imported PatchSmith areas:

| Module | Internal areas imported | Risk |
| --- | ---: | --- |
| `deepagents_planner.py` | 12 | Planner owns or coordinates nearly every DeepAgents concern. |
| `workflow.py` | 12 | Main repair workflow imports analysis, planning, reporting, runtime, sandbox, tracing, and restore paths. |
| `evaluation/runners/patch_search.py` | 11 | Evaluation runner is coupled to artifacts, context, ingestion, patching, reports, retrieval, and sandbox. |
| `cli/commands/chat.py` | 9 | Chat CLI owns interactive startup and offline saved-session actions, while shared agent arguments stay in `cli.agent_args`. |
| `chat/controller.py` | 2 | Chat controller owns REPL/session glue, slash dispatch, and workflow callbacks while custom commands, registry assembly, hook execution, transcript writes, and terminal formatting are isolated. |

Definition-count hotspots:

| Module | Definitions | Read |
| --- | ---: | --- |
| `runtime/feedback.py` | 43 | Feedback extraction, localization, and retry guidance are still dense. |
| `patch_quality.py` | 38 | Patch quality heuristics should be grouped behind smaller policy helpers. |
| `runtime/attempts.py` | 39 | Attempt orchestration and artifact selection remain broad. |
| `python_patch_safety.py` | 32 | Python-specific safety checks are still concentrated in one module. |
| `evaluation/complex/trace_readers.py` | 32 | Newly extracted pure trace readers; keep adding fixture coverage here. |
| `evaluation/_helpers.py` | 32 | Shared evaluation helpers should be split if new runners keep expanding. |
| `evaluation/complex/followups.py` | 31 | Newly extracted follow-up candidate policy for budget, verifier, retry, and quality reruns. |
| `evaluation_models_issue_focused.py` | 30 | Issue-focused evaluation models should be split if the corpus policy surface keeps expanding. |
| `agent_cli.py` | 26 | Agent config, preflight, one-shot run, and result payload helpers still share one module. |
| `session/recommendations.py` | 25 | Recommendation policy is separated but still dense enough to split if new strategy hints keep growing. |
| `evaluation/complex/summary.py` | 24 | Newly extracted summary aggregation and resource-budget accounting. |
| `portfolio/_helpers.py` | 23 | Shared portfolio rendering helpers are still broad. |
| `retrieval_features.py` | 21 | Retrieval feature extraction remains broad. |
| `agent_evidence.py` | 21 | Agent evidence helpers remain broad. |

## Findings

### P0: Stabilize The Worktree Before Major Refactors

The current branch has broad modified and untracked state, including new
product files under `src/patchsmith/agent_*.py`, new evaluation files, deleted
legacy runtime files, documentation rewrites, and generated artifacts. This is
acceptable during R&D, but not as a base for a large refactor.

Risk: a product refactor could accidentally mix feature work, deletions,
documentation updates, and architecture cleanup into one unreviewable change.

Plan:

- Cut a checkpoint commit or branch for the current agent work before refactoring.
- Split mechanical moves from behavior changes.
- Keep generated artifacts and local live-run directories out of product commits.
- Preserve `.patchsmith/secrets/` as ignored local state only.

### P1: Split The Chat Shell Into Product Boundaries

`agent_chat.py` is doing too much. It owns the REPL loop, natural-language
routing, slash-command dispatch, command handlers, hooks, preflight, run
execution, apply policy, checkpointing, transcript writes, resume hydration,
formatting, and helper parsing.

Evidence:

- `run_chat_session` owns lifecycle, hook startup, natural command routing, plan
  mode, and task execution dispatch in one loop.
- `_handle_slash_command` is a long if-chain for every command.
- The same file also owns execution-heavy flows such as `_handle_task`,
  `_handle_apply`, `_apply_guard`, checkpoint restore, transcript hydration, and
  output formatting.

Target shape:

- `patchsmith.chat.controller`: REPL/session controller.
- `patchsmith.chat.commands`: command registry and command protocol.
- `patchsmith.chat.handlers.*`: one module per command family, for example
  `context`, `memory`, `plan`, `apply`, `diff`, `profile`, `session`.
- `patchsmith.chat.routing`: slash parser and natural-language command routing.
- `patchsmith.chat.state`: runtime state dataclasses and state mutation helpers.
- `patchsmith.chat.formatting`: terminal output only.

Acceptance criteria:

- Adding a command requires registering a handler, not editing a 3000-line if-chain.
- Command handlers can be unit-tested without constructing a full chat session.
- Apply policy stays in one module and is not mixed with terminal output.

### P1: Make Transcript Events Typed

`agent_session.py` reads JSONL rows as generic dictionaries, then implements
metrics, gates, timeline summaries, recommendations, Markdown export, and config
replay with stringly typed event names.

Risk: every new event requires manual edits across metrics, timeline rendering,
strategy-update detection, gate logic, resume hydration, and reports. Missing
one of those locations silently weakens evidence discipline.

Target shape:

- `patchsmith.session.events`: typed event dataclasses or discriminated Pydantic
  models.
- `patchsmith.session.store`: append/read JSONL and migration-safe decoding.
- `patchsmith.session.metrics`: metrics reducers over typed events.
- `patchsmith.session.gates`: gate profiles and checks.
- `patchsmith.session.recommendations`: `/next` policy.
- `patchsmith.session.report`: Markdown export.

Acceptance criteria:

- New event types have one declared schema.
- Metrics and reports consume typed events instead of open dicts.
- Unknown historical events are preserved but isolated behind compatibility
  adapters.

### P1: Extract Complex Benchmark Into A Package

`evaluation/runners/complex.py` is the highest-risk file. It contains suite
spec models, threshold parsing, input validation, result extraction, selection,
summary aggregation, gate evaluation, follow-up generation, Markdown rendering,
trace parsing, model usage extraction, and formatting helpers.

The threshold surface is especially fragile: the same threshold fields appear in
`ComplexBenchmarkSuiteGate`, `ComplexBenchmarkSuiteThresholds`,
`ComplexBenchmarkSuiteSpec`, resolver functions, validation functions, CLI
arguments, gate checks, report rendering, and tests.

Target shape:

- `patchsmith.evaluation.complex.models`
- `patchsmith.evaluation.complex.spec`
- `patchsmith.evaluation.complex.extract`
- `patchsmith.evaluation.complex.selection`
- `patchsmith.evaluation.complex.summary`
- `patchsmith.evaluation.complex.gates`
- `patchsmith.evaluation.complex.followups`
- `patchsmith.evaluation.complex.render`
- `patchsmith.evaluation.complex.trace_readers`

Acceptance criteria:

- A new threshold is declared once and rendered/validated through a registry.
- Trace readers are pure functions with fixture-based tests.
- Report rendering does not import selection or extraction internals.

### P1: Introduce A DeepAgents Run Interface Builder

`deepagents_planner.py` constructs effective config, localization candidates,
context selection, virtual files, context-budget metadata, repo maps, repo
instructions, source hints, target history, acceptance rubrics, subagent routing,
repair interface manifests, contract metadata, model invocation, output parsing,
target-policy checks, and final plan validation.

Risk: every prompt, manifest, routing, or budget change touches the planner and
can affect live-model behavior. This is the most expensive kind of coupling.

Target shape:

- `deepagents.context_selection`: select and rank retrieved context.
- `deepagents.run_interface`: build all virtual files and manifests.
- `deepagents.routing`: subagent mode and budget policy.
- `deepagents.invoke`: provider invocation and metadata capture.
- `deepagents.plan_validation`: structured output and target-policy validation.
- `deepagents.planner`: orchestration only.

Acceptance criteria:

- `DeepAgentsRepairPlanner._plan_with_repo_path` becomes an orchestration flow,
  not a manifest-building function.
- Live-model metadata and contract metadata are produced by explicit builders.
- Budget policy has standalone tests independent of model invocation.

### P1: Replace Manifest Argument Explosion With A Registry

`deepagents_files.py` and `deepagents_repair_interface.py` still pass many
optional manifests into virtual-file and required-read assembly. This worked for
R&D, but the product will keep adding manifests: repair interface, rubric, repo
map, source hints, target history, feedback, context budget, repo instructions,
and likely more.

Target shape:

- `VirtualFile` dataclass with path, content, encoding, timestamps, and kind.
- `ManifestSpec` dataclass with path, content, required-read policy, budget
  critical policy, and metadata key.
- A registry that builds `agent_files`, required-read lines, and contract
  metadata from the same manifest specs.

Acceptance criteria:

- Adding a new manifest does not require editing three separate parameter lists.
- Required-read behavior is table-driven and tested per manifest.

### P2: Split CLI Registration From Command Execution

`cli/commands/run.py` now registers only legacy `run`, while the standalone
agent command, model preflight, direct repository commands, chat command/offline
session actions, shared agent argument/config helpers, and shared run-result
output live in dedicated modules.

Target shape:

- `cli/commands/agent.py`: one-shot and interactive agent command.
- `cli/commands/chat.py`: chat command and offline session actions.
- `cli/commands/run.py`: legacy issue-to-report lifecycle only.
- `cli/commands/model_preflight.py`
- `cli/commands/repository.py`: direct index and retrieve commands.
- Shared `cli/agent_args.py` for common agent flags.

Acceptance criteria:

- `patchsmith chat --help` and `patchsmith agent --help` remain unchanged.
- Argument validation is shared through typed config builders, not copied if
  branches.

### P2: Normalize Data Models Around Domains

The benchmark dataclasses have grown from simple result records into large bags
of optional fields. That makes serialization easy but domain reasoning hard.

Target shape:

- `ModelUsage`
- `PatchOutcome`
- `TraceEvidence`
- `ProcessQuality`
- `ContextEvidence`
- `RubricEvidence`
- `CostEvidence`
- `RepairAttemptResult`

Acceptance criteria:

- Reports and gates compose domain objects instead of reading dozens of optional
  fields from one flat dataclass.
- JSON output remains backward-compatible through `to_dict` adapters.

### P2: Reorganize Tests By Product Boundary

The test suite is strong, but its largest files mirror the production
monoliths. That makes refactors scary because unrelated behavior is asserted in
long scenario tests.

Target shape:

- `tests/chat/test_commands_*.py`
- `tests/chat/test_apply_policy.py`
- `tests/chat/test_session_resume.py`
- `tests/session/test_metrics.py`
- `tests/session/test_recommendations.py`
- `tests/evaluation/complex/test_spec.py`
- `tests/evaluation/complex/test_gates.py`
- `tests/evaluation/complex/test_trace_readers.py`
- `tests/deepagents/test_run_interface.py`
- `tests/deepagents/test_budget_routing.py`

Acceptance criteria:

- Each extracted production package has a matching focused test package.
- Existing scenario tests stay as smoke coverage, but most assertions move to
  focused unit tests.

### P2: Raise Type Strictness Gradually

`pyproject.toml` currently has broad mypy coverage, but `check_untyped_defs` is
off globally and strict options only apply to a few modules. This is reasonable
for R&D but weak for a product expected to evolve safely.

Plan:

- Enable stricter mypy per newly extracted package.
- Start with pure modules: instruction loading, session gates, patch quality,
  diff/apply helpers, benchmark spec parsing.
- Keep provider SDK and dynamic DeepAgents calls behind typed adapter protocols.

Acceptance criteria:

- New packages require typed public functions.
- Dynamic SDK boundaries are explicitly isolated instead of leaking `Any`
  through domain logic.

## Refactor Sequence

Progress:

- 2026-06-15: Phase 1 slice started. Natural-language command routing and
  slash-command parsing moved into `patchsmith.chat.routing`, with focused
  tests under `tests/chat/test_routing.py`. `agent_chat.py` still owns command
  dispatch and handlers.
- 2026-06-15: Phase 1 command-boundary slice added `patchsmith.chat.state`,
  `patchsmith.chat.commands`, and `patchsmith.chat.handlers.memory`. The
  `/instructions` and `/memory` command family now goes through the command
  registry, with focused tests under `tests/chat/test_memory_commands.py`.
- 2026-06-15: The `/context` command family moved into
  `patchsmith.chat.handlers.context` and is also registered through
  `patchsmith.chat.commands`, with focused tests under
  `tests/chat/test_context_commands.py`.
- 2026-06-15: The `/model` and `/budget` command family moved into
  `patchsmith.chat.handlers.model_budget`; `/status` now reuses that module's
  model and budget labels. Focused tests live under
  `tests/chat/test_model_budget_commands.py`.
- 2026-06-15: The `/plan`, `/feedback`, `/note`, and `/notes` command family
  moved into `patchsmith.chat.handlers.session_plan`, with focused tests under
  `tests/chat/test_session_plan_commands.py`.
- 2026-06-15: The `/diff`, `/apply`, `/approve apply`, `/reject apply`,
  `/rewind`, and `/undo` command family moved into
  `patchsmith.chat.handlers.diff_apply`, with focused tests under
  `tests/chat/test_diff_apply_commands.py`.
- 2026-06-15: The `/run`, `/preflight`, and `/verify` command family moved into
  `patchsmith.chat.handlers.execution`, with callbacks initially preserving the
  existing repair-loop, preflight, and verify implementation in `agent_chat.py`.
  Focused tests live under `tests/chat/test_execution_commands.py`.
- 2026-06-16: The `/cost`, `/metrics`, `/timeline`, `/next`, `/gate`, `/trace`,
  `/evidence`, and `/export` command family moved into
  `patchsmith.chat.handlers.session_evidence`, preserving transcript events
  through the command context recorder. `agent_chat.py` is now 2010 lines, with
  coverage through `tests/test_agent_chat.py`.
- 2026-06-16: The `/sessions`, `/commands`, `/hooks`, `/agents`, `/profiles`,
  `/agent`, `/profile`, and `/permissions` command family moved into
  `patchsmith.chat.handlers.project` and
  `patchsmith.chat.handlers.permissions`. Focused tests live under
  `tests/chat/test_project_commands.py` and
  `tests/chat/test_permission_commands.py`; `agent_chat.py` is now 1704 lines.
- 2026-06-16: The `/status`, `/history`, `/mode`, `/cancel`, `/clear`, and
  `/compact` command family moved into
  `patchsmith.chat.handlers.session_state`, with direct coverage in
  `tests/chat/test_session_state_commands.py`; `agent_chat.py` is now
  1490 lines.
- 2026-06-16: The `/checkpoint`, `/checkpoints`, and `/restore` command family
  moved into `patchsmith.chat.handlers.checkpoints`. Shared config and
  checkpoint replay payload helpers moved into
  `patchsmith.chat.session_payloads`, so checkpoint restore and transcript
  resume use the same decoders. Focused tests live under
  `tests/chat/test_checkpoint_commands.py`; `agent_chat.py` is now 950 lines
  and 27 top-level definitions.
- 2026-06-16: The `/help` and `/doctor` command family moved into
  `patchsmith.chat.handlers.system`, with focused tests under
  `tests/chat/test_system_commands.py`. `agent_chat.py` is now 851 lines and
  25 top-level definitions; slash dispatch now has registered command handling,
  exit/quit session termination, and project custom-command fallback.
- 2026-06-16: `/preflight` and `/verify` are now fully implemented in
  `patchsmith.chat.handlers.execution`; `patchsmith.chat.preflight` carries the
  shared preflight payload builder used by both `/preflight` and the pre-run
  guard. Focused execution tests now assert transcript payloads and sandbox
  summaries directly. `agent_chat.py` is now 734 lines and 18 top-level
  definitions.
- 2026-06-16: The repair-loop task lifecycle moved into
  `patchsmith.chat.task_runner`: submit/pre-run hooks, plan and feedback context
  injection, run preflight, optional model preflight, `run_agent_once`, result
  recording, auto-apply deferral, and post-run hooks. Focused tests live under
  `tests/chat/test_task_runner.py`; `agent_chat.py` is now 526 lines and 13
  top-level definitions.
- 2026-06-16: Transcript resume hydration moved into
  `patchsmith.chat.session_resume`, with focused tests under
  `tests/chat/test_session_resume.py`. `agent_chat.py` is now 403 lines and 12
  top-level definitions; the controller no longer owns replaying transcript
  rows into runtime state.
- 2026-06-16: The chat session controller moved into
  `patchsmith.chat.controller`, while `patchsmith.agent_chat` remains a
  five-line compatibility wrapper for existing imports. Focused chat regression
  coverage still imports the compatibility path; apply/check monkeypatches now
  target the controller module that owns command context construction.
- 2026-06-16: Chat command-family registration moved into
  `patchsmith.chat.registry`, with focused coverage under
  `tests/chat/test_registry.py`. `patchsmith.chat.controller` is now 375 lines
  and no longer imports each handler family just to assemble slash commands.
- 2026-06-16: Terminal line output moved into
  `patchsmith.chat.formatting.write_line`, replacing duplicated local
  `_write_line` helpers across the chat controller, task runner, preflight, and
  command handlers. Focused coverage lives under
  `tests/chat/test_formatting.py`; `patchsmith.chat.controller` is now 371
  lines.
- 2026-06-16: Transcript recording and project hook execution moved into
  `patchsmith.chat.transcript` and `patchsmith.chat.hooks`, with focused
  coverage under `tests/chat/test_transcript.py` and
  `tests/chat/test_hooks.py`. `patchsmith.chat.controller` is now 333 lines and
  no longer imports `agent_hooks` or the session transcript store directly.
- 2026-06-16: Project custom slash-command fallback moved into
  `patchsmith.chat.custom_commands`, with focused coverage under
  `tests/chat/test_custom_commands.py`. `patchsmith.chat.controller` is now 280
  lines and no longer imports `patchsmith.agent_commands` directly.
- 2026-06-15: Phase 1 typed-transcript slice added `patchsmith.session.events`
  and `patchsmith.session.store`. Existing transcript writes and
  `agent_session.transcript_rows` now use the store compatibility layer, with
  focused tests under `tests/session/test_store.py`.
- 2026-06-15: Session metrics moved into `patchsmith.session.metrics` while
  `agent_session` keeps compatibility exports. Focused reducer tests live under
  `tests/session/test_session_metrics.py`.
- 2026-06-15: Session gate config/evaluation moved into
  `patchsmith.session.gates` while `agent_session` keeps compatibility exports.
  Focused gate tests live under `tests/session/test_session_gates.py`.
- 2026-06-15: Saved-session summaries and timelines moved into
  `patchsmith.session.summaries` and `patchsmith.session.timeline` while
  `agent_session` keeps compatibility exports. Focused tests live under
  `tests/session/test_session_summaries.py` and
  `tests/session/test_session_timeline.py`.
- 2026-06-15: `/next` recommendation policy moved into
  `patchsmith.session.recommendations` while `agent_session` keeps
  compatibility exports. Focused tests live under
  `tests/session/test_session_recommendations.py`.
- 2026-06-15: Session Markdown export moved into `patchsmith.session.report`
  while `agent_session` is now a small compatibility facade over the session
  package. Focused report tests live under
  `tests/session/test_session_report.py`.
- 2026-06-15: Phase 2 started by moving DeepAgents subagent routing and
  resource-budget policy into `patchsmith.deepagents_routing`. Planner behavior
  is preserved through compatibility imports, with focused tests in
  `tests/test_deepagents_routing.py`.
- 2026-06-15: DeepAgents structured-output parsing and target-policy validation
  moved into `patchsmith.deepagents_plan_validation`, leaving the planner to
  orchestrate invocation and metadata updates. Focused tests live in
  `tests/test_deepagents_plan_validation.py`.
- 2026-06-15: DeepAgents repair-interface and agent-file assembly moved into
  `patchsmith.deepagents_run_interface`, giving Phase 2 a first
  RunInterfaceBuilder-style boundary. Focused tests live in
  `tests/test_deepagents_run_interface.py`.
- 2026-06-15: DeepAgents context selection, target-context auto-capping,
  retry-aware preferred patch paths, and preferred symbol focus moved into
  `patchsmith.deepagents_context_selection`. The planner now delegates that
  policy and is down to 636 lines, with focused tests in
  `tests/test_deepagents_context_selection.py`.
- 2026-06-15: DeepAgents provider invocation, prompt payload assembly, success
  metadata, structured-output failure metadata, and resource-budget-exceeded
  accounting moved into `patchsmith.deepagents_invoke`. The planner is now down
  to 521 lines, with focused tests in `tests/test_deepagents_invoke.py`.
- 2026-06-16: DeepAgents virtual-file records and manifest definitions moved into
  `patchsmith.deepagents_manifests`. `patchsmith.deepagents_files.agent_files`
  and repair-interface required reads now consume that registry while preserving
  the existing planner/run-interface API. Focused coverage lives in
  `tests/test_deepagents_manifests.py`; `deepagents_files.py` is now 1271 lines.
- 2026-06-16: Scoped AGENTS.md-style repository instruction manifest rendering
  moved into `patchsmith.deepagents_repo_instructions`, with the legacy
  `deepagents_files` alias preserved. Focused coverage in
  `tests/test_deepagents_rubric.py` now exercises the dedicated module directly;
  `deepagents_files.py` is now 1138 lines.
- 2026-06-16: DeepAgents context-budget manifest and metadata rendering moved
  into `patchsmith.deepagents_context_budget`, and shared context rendering
  helpers moved into `patchsmith.deepagents_context_utils`. The legacy
  `deepagents_files` aliases remain intact, with focused coverage in
  `tests/test_deepagents_context_budget.py`; `deepagents_files.py` is now 1031
  lines.
- 2026-06-16: DeepAgents retrieved repo-map manifest rendering moved into
  `patchsmith.deepagents_repo_map`, including definition-signature extraction
  for mounted and omitted files. The legacy `deepagents_files` alias remains
  intact, with focused coverage in `tests/test_deepagents_repo_map.py`;
  `deepagents_files.py` is now 900 lines.
- 2026-06-16: DeepAgents reviewed source-hint manifest rendering moved into
  `patchsmith.deepagents_source_hints`. The legacy `deepagents_files` alias
  remains intact, with focused coverage in
  `tests/test_deepagents_source_hints.py`; `deepagents_files.py` is now 849
  lines.
- 2026-06-16: DeepAgents target-history manifest rendering moved into
  `patchsmith.deepagents_target_history`, including retry target reason priority
  ordering. The legacy `deepagents_files` alias remains intact, with focused
  coverage in `tests/test_deepagents_target_history.py`; `deepagents_files.py`
  is now 736 lines.
- 2026-06-16: DeepAgents repair-interface manifest assembly moved into
  `patchsmith.deepagents_repair_interface`, including budget-critical required
  reads and fast patch packet rendering. The legacy `deepagents_files` alias
  remains intact, with focused coverage in
  `tests/test_deepagents_repair_interface.py`; `deepagents_files.py` is now 384
  lines.
- 2026-06-16: DeepAgents mounted source-file shaping moved into
  `patchsmith.deepagents_context_files`, including repo-backed reads, focused
  source spans, timestamps, and excerpt fallback behavior. The legacy
  `deepagents_files` exports remain intact, with focused coverage in
  `tests/test_deepagents_context_files.py`; `deepagents_files.py` is now 172
  lines.
- 2026-06-16: DeepAgents manifest content mounting now flows through
  `patchsmith.deepagents_manifests.ManifestContents`, so the run-interface
  builder can pass one registry-backed bundle into repair-interface rendering
  and virtual-file assembly. Focused coverage in
  `tests/test_deepagents_manifests.py` pins bundle specs, required reads, and
  `agent_files` mounting; `deepagents_files.py` is now 175 lines.
- 2026-06-16: DeepAgents contract metadata and invoke prompt path selection now
  consume the same `ManifestContents` bundle returned by the run-interface
  builder. Legacy boolean/string arguments remain compatible, while focused
  coverage in `tests/test_deepagents_contract.py` and
  `tests/test_deepagents_invoke.py` pins registry-backed manifest paths,
  allowed reads, and budget-critical read policy.
- 2026-06-16: The standalone `openai-model-preflight` CLI command moved into
  `patchsmith.cli.commands.model_preflight`, while the agent runtime keeps its
  internal model-preflight helper in `run.py`. Focused coverage in
  `tests/test_cli_model_preflight.py` pins command routing through the dedicated
  module; `cli/commands/run.py` is now 1094 lines.
- 2026-06-16: Direct repository `index` and `retrieve` CLI commands moved into
  `patchsmith.cli.commands.repository`, preserving shared repo and issue
  argument helpers while removing clone/index/retriever execution from
  `run.py`. Focused coverage in `tests/test_cli_repository_commands.py` pins
  command routing and argument handoff; `cli/commands/run.py` is now 1039 lines.
- 2026-06-16: Shared agent/chat parser options, initial prompt loading, issue
  text loading, agent config construction, and project profile merging moved
  into `patchsmith.cli.agent_args`. Focused coverage in
  `tests/test_cli_agent_args.py` pins defaults, profile merge behavior, missing
  profile errors, and issue-file loading; `cli/commands/run.py` is now 738
  lines and 22 top-level definitions.
- 2026-06-16: The `chat` CLI command, scripted chat startup, saved-session
  offline actions, project command/hook/profile/instruction listing, and
  session gate/export helpers moved into `patchsmith.cli.commands.chat`.
  `agent --interactive` now reuses that boundary for chat startup and offline
  session actions. Focused coverage in `tests/test_cli_chat_command.py` pins
  direct chat command registration and offline-action validation;
  `cli/commands/run.py` is now 326 lines and 7 top-level definitions.
- 2026-06-16: The `agent` CLI command moved into
  `patchsmith.cli.commands.agent`, while shared human-readable run output moved
  into `patchsmith.cli.result_output` for reuse by agent and legacy run flows.
  Focused coverage in `tests/test_cli_agent_command.py` pins direct agent
  command registration, one-shot run dispatch, and interactive/preflight
  validation; `cli/commands/run.py` is now 99 lines and 2 top-level
  definitions.
- 2026-06-16: `ComplexBenchmarkResult` gained typed domain views for model
  usage, patch outcome, trace evidence, process quality, DeepAgents context
  evidence, rubric evidence, cost/resource-budget evidence, and composite repair
  attempts. The existing flat `to_dict()` schema remains backward-compatible,
  with focused coverage in `tests/evaluation/complex/test_models.py`.
- 2026-06-16: Complex benchmark summary aggregation now composes those domain
  views instead of reading the flat result bag directly. Focused coverage in
  `tests/evaluation/complex/test_summary.py` preserves selected-attempt cost,
  token, target-coverage, context-budget, resource-budget, retry, and process
  quality metrics.
- 2026-06-16: Complex benchmark Markdown report rendering now uses the domain
  views for per-result rows and helper summaries instead of the flat benchmark
  result fields. Existing render coverage in
  `tests/evaluation/complex/test_render.py` preserves report output and claim
  boundary text.
- 2026-06-16: Complex benchmark attempt selection now ranks attempts and builds
  selection reasons from the domain views while preserving the flat
  `ComplexBenchmarkSelection` output schema. Focused coverage in
  `tests/evaluation/complex/test_selection.py` preserves strict-validation,
  cost, context-budget, resource-budget, and selected-result behavior.
- 2026-06-16: Complex benchmark follow-up candidate policy now derives rerun
  actions, profiles, verifier-threshold reasons, priorities, and candidate rows
  from the domain views while preserving the flat follow-up candidate schema.
  Focused coverage in `tests/evaluation/complex/test_followups.py` preserves
  budget-critical reruns and acceptance-rubric verifier reruns.
- 2026-06-16: The extracted `patchsmith.evaluation.complex.*` package now has a
  scoped mypy override with `check_untyped_defs` and `disallow_untyped_defs`
  enabled. This starts the gradual type-strictness track on the benchmark
  package without changing global typing policy.
- 2026-06-15: Phase 3 started by moving complex benchmark suite models,
  threshold/config resolution, spec loading, and suite input preflight into
  `patchsmith.evaluation.complex.models` and
  `patchsmith.evaluation.complex.spec`. Legacy imports from
  `patchsmith.evaluation.runners.complex` remain compatible, with direct tests
  in `tests/evaluation/complex/test_spec.py`.
- 2026-06-15: Complex benchmark trace readers moved into
  `patchsmith.evaluation.complex.trace_readers`, covering trace metrics,
  model usage, DeepAgents context-budget metadata, patch quality, target
  alignment, and retry-feedback artifacts. Fixture-style coverage lives in
  `tests/evaluation/complex/test_trace_readers.py`; the complex runner is now
  2998 lines.
- 2026-06-16: Complex benchmark attempt grouping, selected-result lookup,
  ranking, and selection-reason generation moved into
  `patchsmith.evaluation.complex.selection`. Focused tests live in
  `tests/evaluation/complex/test_selection.py`; the complex runner is now
  2870 lines.
- 2026-06-16: Complex benchmark suite gate evaluation moved into
  `patchsmith.evaluation.complex.gates`, and
  `ComplexBenchmarkSuiteThresholds.gate()` now calls that package boundary
  instead of importing from the runner. Focused tests live in
  `tests/evaluation/complex/test_gates.py`; the complex runner is now
  2481 lines.
- 2026-06-16: Complex benchmark follow-up candidate generation moved into
  `patchsmith.evaluation.complex.followups`, covering budget-critical reruns,
  verifier-threshold reruns, retry/context/quality profiles, and generated
  command contracts. Focused tests live in
  `tests/evaluation/complex/test_followups.py`; the complex runner is now
  1916 lines.
- 2026-06-16: Complex benchmark Markdown report and follow-up runbook rendering
  moved into `patchsmith.evaluation.complex.render`, preserving the runner's
  legacy render exports while giving the package direct focused tests in
  `tests/evaluation/complex/test_render.py`; the complex runner is now
  1359 lines.
- 2026-06-16: Complex benchmark summary aggregation moved into
  `patchsmith.evaluation.complex.summary`, including pass@N, selected-attempt
  accounting, context-target coverage, and resource-budget metrics. Focused
  tests live in `tests/evaluation/complex/test_summary.py`; the complex runner
  is now 741 lines.
- 2026-06-16: Saved repair-attempt result extraction moved into
  `patchsmith.evaluation.complex.extract`, covering result-row parsing,
  progress/failure classification, preflight-gate classification, live-cost
  budget parsing, and trace-reader composition. Focused tests live in
  `tests/evaluation/complex/test_extract.py`; the complex runner is now
  249 lines.
- 2026-06-16: Complex benchmark artifact writing moved into
  `patchsmith.evaluation.complex.outputs`, preserving JSON, CSV, report, suite
  report, and follow-up runbook outputs. Focused tests live in
  `tests/evaluation/complex/test_outputs.py`; the complex runner is now
  159 lines.
- 2026-06-16: Complex benchmark suite thresholds moved into
  `patchsmith.evaluation.complex.thresholds`, centralizing threshold names,
  validation kinds, and CLI help. Spec parsing, threshold resolution, model
  threshold counts, gate result metadata, and `eval-complex-suite` flag
  registration now consume the registry, with drift coverage in
  `tests/evaluation/complex/test_spec.py`.

### Phase 0: Stabilize

1. Split the current worktree into reviewable commits:
   - public docs/readme changes;
   - chat/agent product changes;
   - DeepAgents runtime/evaluation changes;
   - generated artifacts and local live evidence excluded or moved under
     explicit fixture/sample paths.
2. Add focused tests for any newly introduced command behavior that currently
   only has smoke coverage, especially memory persistence.
3. Confirm `ruff`, `mypy`, and full `pytest` from a clean checkout.

### Phase 1: Chat And Session Product Core

1. Extract `chat.routing` with slash parsing and natural-command routing.
2. Extract `chat.commands` with a small `ChatCommand` protocol:
   - name;
   - aliases;
   - usage;
   - handler.
3. Move command families one at a time:
   - `memory` and `instructions`;
   - `context`;
   - `model` and `budget`;
   - `plan` and `feedback`;
   - `diff` and `apply`;
   - `run` and `preflight`.
4. Extract transcript storage and typed events before adding more metrics.
5. Keep `run_chat_session` as the public compatibility API until the new
   controller is stable.

### Phase 2: DeepAgents Runtime Boundary

1. Extract a `RunInterfaceBuilder` that returns:
   - selected contexts;
   - virtual files;
   - manifests;
   - required reads;
   - contract metadata.
2. Extract budget/subagent routing as pure policy.
3. Extract plan validation and target-policy checks.
4. Keep the planner as a thin orchestrator calling those components.
5. Re-run the existing complex live-smoke fixtures before changing default
   runtime behavior.

### Phase 3: Complex Benchmark Package

1. Move dataclasses and spec parsing first with no behavior change.
2. Extract gate threshold registry. Done 2026-06-16.
3. Extract trace readers and prove parity with saved artifact fixtures.
4. Extract summary and report rendering.
5. Only after parity, simplify CLI handlers around the new package.

### Phase 4: Product Hardening

1. Define compatibility policy for transcript JSONL and benchmark JSON outputs.
2. Add migration tests for older transcript/event rows.
3. Add a release gate that runs:
   - unit tests;
   - selected smoke scripts;
   - package build;
   - CLI help snapshot;
   - sample transcript export;
   - saved benchmark suite validation.
4. Add ownership docs for each product boundary.

## Non-Goals

- Do not rewrite the runtime from scratch.
- Do not change DeepAgents default behavior while extracting modules.
- Do not collapse benchmark evidence into a single score.
- Do not weaken apply, diff-review, hook, or sandbox gates to simplify code.

## Recommended First PR

Start with `agent_chat.py`, but only the safest slice:

1. Move natural command routing and slash parsing into `patchsmith.chat.routing`.
2. Add tests for the routing table, including memory, apply, diff, plan, and
   preflight phrases.
3. Keep `_handle_slash_command` intact for the first PR.
4. Run `ruff`, `mypy`, and full `pytest`.

This gives immediate readability improvement without touching model execution,
apply policy, or transcript semantics.
