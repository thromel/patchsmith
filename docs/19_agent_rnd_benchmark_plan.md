# Agent R&D and Benchmark Plan

## Status

Draft v0.1, current as of 2026-06-14.

This document turns current coding-agent research into PatchSmith engineering
work. It is intentionally evidence-gated: a feature only graduates when saved
artifacts show better validation, target alignment, cost, or debuggability than
the current DeepAgents baseline.

## Source Signals

### 2025/2026 SoTA scan

Recent papers and primary engineering reports point to a sharper direction than
the older "more agents everywhere" story:

- [Live-SWE-agent](https://arxiv.org/abs/2511.13646) treats the scaffold itself
  as something the agent can adapt during runtime. The actionable PatchSmith
  version is not self-modifying code yet; it is traceable policy adaptation:
  switch context, retry, and subagent behavior based on saved progress signals.
- [SWE-RL](https://arxiv.org/html/2502.18449v1) shows that software-evolution
  data can train stronger reasoning for real issue repair. PatchSmith should
  keep exporting structured trajectories, target choices, patch-quality
  labels, and validation outcomes so future model or policy training has clean
  reward signals.
- [SWE-CI](https://arxiv.org/html/2603.03823v1) argues that one-shot repair is
  too weak as an evaluation target; long-term maintainability and future
  changes matter. PatchSmith's patch-quality and target-alignment telemetry
  should become gate inputs, not just report decoration.
- [SWE-Bench Pro](https://labs.scale.com/leaderboard/swe_bench_pro_public)
  expands evaluation toward long-horizon, professional codebases with stricter
  environments and human augmentation. PatchSmith should grow from a 3-task
  smoke lane to difficulty-labeled public tasks with cost and setup-failure
  accounting.
- Anthropic's 2025 context-engineering guidance frames context as a finite
  resource with diminishing returns. PatchSmith's mounted manifests, context
  caps, target history, and repair interface are aligned with this, but retry
  attempts must see remaining budget, not only the original cap.
- Anthropic's multi-agent research-system write-up is a warning as much as an
  inspiration: subagents improve breadth-heavy search but can use far more
  tokens, and coding tasks are often less parallelizable than research tasks.
  PatchSmith should escalate subagents only when the task evidence and
  remaining budget justify it.
- [ContextBench](https://arxiv.org/abs/2602.05892) and
  [LoCoBench-Agent](https://arxiv.org/abs/2511.13998) make the next evaluation
  target more precise: final validation is necessary but insufficient. The
  benchmark output should expose whether an agent explored and used context
  efficiently across multi-turn workflows.
- [SWE-Cycle](https://arxiv.org/abs/2605.13139) pushes beyond isolated patching
  by separating environment reconstruction, implementation, verification-test
  generation, and full-cycle execution. PatchSmith should keep its current
  public-issue lane narrow while adding lifecycle sub-lanes over time.

Immediate integration:

- pass used and remaining model response/token budget into DeepAgents retries,
- keep first budgeted attempts compact,
- on retries, allow subagents when budget headroom is healthy but route inline
  when the saved attempt already consumed most of the response/token budget,
- report that routing decision in the DeepAgents contract so live artifacts can
  prove whether budget pressure changed behavior,
- add an opt-in span-mounted context mode for first attempts, so source paths
  remain stable but large files are narrowed to line windows around matched
  symbols, runtime-cache cues, and reviewed source hints.
- report selected-attempt context-efficiency proxies in complex summaries:
  selected virtual files, virtual files per validated task, tokens per virtual
  file, and responses per virtual file.
- report selected context-target recall and precision from saved traces when
  DeepAgents mounted source paths can be compared with localized target paths.
- mount AGENTS.md-style repository instructions only as a scoped, capped
  `/.patchsmith/repo-instructions.md` artifact for the root and ancestors of
  mounted context paths, then report manifest coverage and read-first rate
  instead of treating broad repo guidance as free context.
- gate those proxies with `max_selected_virtual_files_per_validated_task`,
  `max_selected_tokens_per_virtual_file`, and
  `max_selected_responses_per_virtual_file` before promoting a context policy.
- gate trace-derived context coverage with `min_selected_context_target_recall`
  and `min_selected_context_target_precision` so broad mounted-context policies
  cannot pass only because the correct file was included somewhere.
- gate verifier quality with `min_acceptance_rubric_alignment_rate`, a
  deterministic proxy that requires rubric read-first coverage, a generated
  patch, a mounted patch target, target-aligned localization, and no
  patch-quality warning before a rubric-backed attempt counts as aligned.
- report a trace-derived progress score for selected attempts so long-horizon
  and failed tasks can still expose reproduced input, patch generation,
  target-aligned patches, quality-warning test passes, and clean validation.

### DeepAgents harness design

LangChain's Deep Agents documentation frames a deep agent as a harness around a
tool-calling loop with planning, virtual filesystems, subagents, permissions,
memory, context management, sandbox execution, event streaming, and reusable
skills.

PatchSmith already uses this direction through:

- todo-required planning,
- a state-backed virtual filesystem,
- read permissions scoped to retrieved files and PatchSmith manifests,
- a `patchsmith-repair` skill,
- `failure-localizer` and `patch-reviewer` subagents,
- structured `PatchPlan` output,
- trace events and cost metadata.

Next useful integration:

- expose DeepAgents event streaming as first-class PatchSmith trace events,
- add optional human approval before high-risk file writes or retry escalation,
- persist accepted repair lessons as gated skills only after benchmark proof.

### Conversational coding CLI design

Current Claude Code, Codex CLI, OpenCode, and Aider UX converges on the same
product shape: a one-shot automation mode for scripts plus an interactive
terminal session for iterative work. The useful shared primitives are not the
visual TUI itself; they are session-local slash commands, explicit permission
boundaries, model/config status, history, resumability, and lightweight context
control.

PatchSmith's first integration keeps this narrower and evidence-first:

- `patchsmith chat` and `patchsmith agent --interactive` reuse the same
  DeepAgents runner, preflight, trace, diff, and apply machinery as the
  one-shot command.
- plain text maps to a bounded repair run in act mode, while `/mode plan`
  makes plain text run `/preflight` only and store a pending planned task.
  `go ahead` or `/run` executes that pending task through the normal runner;
  `cancel plan` or `/cancel plan` discards it without clearing the session;
  `/mode act` returns plain text to immediate repair runs. `/preflight`,
  `/context`, `/model`, `/budget`, `/doctor`, `/cost`, `/compact`, `/clear`,
  `/export`, `/sessions`, `/commands`, `/hooks`, `/agents`, `/agent`,
  `/instructions`, `/run`, `/status`, `/history`, `/diff`, `/apply`, and
  `/exit` provide the initial slash-command surface.
- obvious conversational control phrases such as `what next?`, `show status`,
  `review diff`, `apply check`, `go ahead`, `cancel plan`, and `apply it` now
  route to slash commands before the plain-text repair path, so control intent
  does not accidentally spend a model call or apply the wrong operation.
- session transcripts are persisted as JSONL under `artifacts/chat_sessions/`
  with run paths, test exit code, retrieved files, model responses, tokens, and
  estimated cost so interactive runs remain auditable benchmark material.
- `/apply` is explicit and uses the same local Git, dirty-worktree, and
  `git apply --check` safeguards as `patchsmith agent --apply`.
- `/context add|show|remove|clear` mutates forced context hints inside the
  session and records those mutations in the transcript before the next run.
- `/model` and `/budget` mutate the same runtime config used by one-shot
  `patchsmith agent`, so live chat experiments can switch model ids and
  response/token caps without leaving the transcript.
- `/doctor` exposes the same local readiness checks as preflight without
  needing a task prompt, including optional DeepAgents dependencies, API-key
  presence, model selection, budget caps, and apply-target readiness.
- `/run` records an automatic `run_preflight` event before model work begins.
  CLI-backed sessions then run a live OpenAI model availability/auth preflight
  before starting DeepAgents, while `/preflight` remains a no-model-call local
  diagnostic. The run preflight reuses the same readiness payload as
  `/preflight`, but keeps manual preflight metrics separate from the checks
  that happened immediately before a repair attempt.
- `/cost` turns the event-sourced chat transcript into lightweight process and
  usage telemetry: tasks, runs, validated runs, run errors, model calls,
  responses, tokens, and estimated session spend.
- `/metrics` derives process evidence from the same transcript: preflight
  count, preflight-to-run rate, validation rate, apply success rate, custom
  command count, hook runs/blocks, context/model/budget/permission changes,
  verify runs, diff views, feedback views/updates, run evidence views,
  timeline views, next recommendations, checkpoints/restores, model tokens,
  and cost per validated run. This keeps interactive sessions compatible with
  the benchmark direction that treats trajectory quality as more than final
  pass/fail.
- `/gate` brings the saved-session gate into the live chat loop. Built-in
  profiles (`validated`, `clean`, `applied`, and `cost <usd>`) evaluate the
  transcript before promotion, record the gate result, and count gate failures
  as process evidence.
- `/trace` and `/evidence` summarize the last run's `report.md`,
  `traces.jsonl`, and `final.diff` in chat: artifact presence, trace
  statuses/nodes, changed files, diff line counts, model usage, and estimated
  cost. This makes the trace-review loop visible before a session is exported
  or promoted into a benchmark lane.
- `/verify` reruns the configured or explicit allowlisted test command through
  PatchSmith's sandbox command policy. The result is transcripted separately
  from model-driven runs, so users can verify the applied working tree without
  spending tokens or mutating the original repair evidence.
- `/diff stat` and `/diff show [lines]` make generated patch review a
  transcripted step before apply: users can inspect changed files, line counts,
  and a bounded preview without opening raw artifact files.
- `/diff review` adds a deterministic security-analyzer-style patch-risk
  review over the generated diff. It reuses PatchSmith's existing
  `assess_diff_quality()` rules, records risk/decision/findings in the
  transcript, reports high-risk counts in metrics, and lets `/next` stop before
  apply when the patch edits risky paths or shapes.
- `/apply check` adds a non-mutating approval gate after diff review. It runs
  the same local-repo, dirty-worktree, empty-diff, and `git apply --check`
  safeguards as `/apply`, records a separate transcript event, and keeps apply
  attempts distinct from dry-run readiness evidence.
- `/gate reviewed` turns the approval trail into an enforceable promotion gate:
  it requires a validated clean run, at least one deterministic diff review, no
  high-risk diff review findings, and a ready `/apply check`. The same evidence
  thresholds are exposed for saved transcripts with `--require-diff-review`,
  `--max-high-risk-diff-reviews`, and `--require-ready-apply-check`.
- `/apply` now fails closed in chat unless the current diff has non-high-risk
  `/diff review` evidence and a ready `/apply check` recorded after the latest
  run. Blocked mutation attempts are transcripted as `apply_blocked` instead of
  being silently ignored or falling through to `git apply`.
- `/approve apply <reason>` records explicit human approval for the current
  reviewed diff after a ready `/apply check`. High-risk reviewed diffs can only
  proceed to `/apply` when this approval exists after the check, and approvals
  are reported separately from apply attempts so benchmark gates can keep
  risk-accepted work distinct from clean promotion evidence.
- `/reject apply <reason>` records the denial side of the same confirmation
  flow. Rejections are scoped to the current diff, block later `/apply`, and can
  only be superseded by a newer `/approve apply <reason>` event for that diff.
- `/next` now treats that denial as first-class trajectory state: after a
  ready apply check, a newer rejection makes the deterministic recommendation
  capture rejection feedback and rerun instead of suggesting mutation.
- `/checkpoint`, `/checkpoints`, and `/restore` add an append-only
  backtracking surface for interactive work: config, context hints, plan
  items, history, last-run artifacts, and apply/rewind state can be restored
  without deleting the intervening transcript evidence.
- `/feedback` adds a staged human-in-the-loop correction channel. Users can
  capture follow-up guidance between runs, replay it after resume, and inject
  it into the next bounded DeepAgents prompt without editing the original task
  or losing the transcript evidence.
- `/timeline` renders the JSONL transcript as a compact status trail, so users
  can inspect recent task, run, gate, trace, checkpoint, feedback, hook, and
  config events without opening raw artifacts.
- `/next` turns the transcript into a deterministic next-action recommendation:
  if a run is missing, blocked, unreviewed, ungated, unapplied, or
  uncheckpointed, or if the current apply decision has been rejected, the chat
  loop surfaces the next evidence-backed command without calling another model.
  Pending plan-mode tasks now stay visible in that same recommendation surface:
  after a successful plan preflight, `/next` asks for `/run` or `/cancel plan`,
  and after a blocked preflight it asks the user to fix readiness or cancel
  before spending model tokens.
- DeepAgents model configuration now records encrypted-reasoning policy in the
  planning contract. Auto mode requests `reasoning.encrypted_content` for
  reasoning-capable OpenAI model ids and omits it for non-reasoning ids, which
  keeps provider compatibility failures visible as configuration problems
  rather than failed repair attempts.
- `/preflight` and `/doctor` now surface reasoning-model token headroom before
  a run. Low caps stay non-blocking for budget experiments, but the transcript
  records a structured warning so later live-smoke failures can be separated
  from patch-quality failures.
- `/agents` discovers project-local Markdown specialist profiles from
  `.patchsmith/agents/`. `/agent <name>` applies one to later runs by setting
  model/budget/context defaults and prepending profile instructions to the
  bounded task prompt. This mirrors file-based subagent definitions without
  creating a separate unmeasured execution path.
- `/instructions` exposes AGENTS.md/CLAUDE.md-style project instruction files
  loaded into the bounded prompt. The content is size-capped, transcripted,
  and inspectable, so PatchSmith gains Claude/Codex-style persistent project
  context without turning instructions into enforcement. Safety-sensitive rules
  still belong in hooks or apply policy.
- `/plan` exposes Claude-style todo/task tracking as explicit session state:
  users can set, add, start, complete, block, skip, and clear plan items. The
  active plan is transcripted, restored on resume, included in the next bounded
  repair prompt, and measured through plan view/update counts.
- `/commands` discovers project-local Markdown prompt templates from
  `.patchsmith/commands/`, with namespaced commands such as `/bench:live`
  mapped from subdirectories. Custom commands render arguments into the prompt
  and still execute through the same bounded DeepAgents run path, so reusable
  workflows remain auditable instead of becoming hidden shell automation.
  Commands can expose lightweight frontmatter metadata such as `description`
  and `argument_hint`; command discovery renders those fields for humans and
  returns them through `--list-commands --json` for SDK-style clients.
- `/hooks` discovers project-local lifecycle hooks from `.patchsmith/hooks.json`.
  Hook commands receive structured JSON on stdin and can block `PreRun` or
  `PreApply` by exiting non-zero or printing `{"decision": "block"}`. This
  mirrors the deterministic-control pattern in modern coding CLIs while keeping
  PatchSmith's expensive model calls and worktree mutation behind explicit,
  transcripted gates.
- `/permissions` exposes PatchSmith's action-confirmation boundary inside the
  chat session: future runs can remain manual-apply only, request auto-apply,
  or explicitly allow dirty-worktree apply operations. In chat, auto-apply is
  now artifact-first: PatchSmith records `apply_auto_deferred` and requires the
  reviewed `/apply` flow instead of mutating during `/run`. Permission changes
  are transcripted and replayed on resume, and they do not bypass `git apply`
  validation or dirty-worktree checks.
- `/rewind` / `/undo` gives the session a Claude-style recovery path without
  adopting broad repository resets. It reverses the last generated diff through
  `git apply --reverse --check`, records the result in the transcript, and
  reports rewind attempts/successes in session metrics.
- `patchsmith chat --list-commands` and
  `patchsmith agent --interactive --list-commands` expose the same project
  command discovery without starting a shell, which makes command availability
  scriptable for SDK-style integrations.
- `patchsmith chat --list-hooks` and
  `patchsmith agent --interactive --list-hooks` expose lifecycle hook metadata
  without starting a shell, with `--json` available for scripted smoke lanes.
- `patchsmith chat --list-agents` and
  `patchsmith agent --interactive --list-agents` expose project agent-profile
  metadata without starting a shell, and `patchsmith agent --agent-profile`
  applies the same profile to one-shot runs.
- `patchsmith chat --list-instructions` and
  `patchsmith agent --interactive --list-instructions` expose the exact
  project instruction files PatchSmith would load. `--instruction-path` adds
  extra repo-local files, and `--no-agent-instructions` keeps the run free of
  persistent instruction context.
- `patchsmith chat --session-metrics <session-id>` and
  `patchsmith agent --interactive --session-metrics <session-id>` compute the
  same process metrics from saved transcripts without reopening the chat loop;
  `--json` makes the metrics directly consumable by benchmark scripts.
- `patchsmith chat --session-gate <session-id>` and
  `patchsmith agent --interactive --session-gate <session-id>` turn saved
  transcript metrics into pass/fail criteria for CI and benchmark promotion:
  require validated runs, set validation/preflight/apply-rate floors, cap cost
  per validated run, and cap run errors.
- `patchsmith chat --export-session <session-id>` and
  `patchsmith agent --interactive --export-session <session-id>` render saved
  transcripts into Markdown reports without replaying the session, so
  interactive work can be promoted into review artifacts after the fact.
- `patchsmith chat --script <file>` and
  `patchsmith agent --interactive --script <file>` read newline-delimited chat
  input from a file. Scripts can issue normal slash commands and plain-text
  repair tasks, but they still append to the same transcript and cannot bypass
  PatchSmith's preflight, runner, trace, diff, cost, or apply boundaries.
- `/compact` records a deterministic transcript summary of current usage,
  recent tasks, context hints, model/budget state, and last-run artifacts before
  clearing in-memory task history. `/clear` resets volatile task/run/apply state
  while retaining the append-only transcript for audit and resume.
- `/export` renders the JSONL transcript into a Markdown session report with
  config, usage, run artifacts, run errors, tasks, context/config changes, and
  latest state so interactive work can be reviewed like benchmark output.
- `/sessions` and `patchsmith chat --list-sessions` summarize resumable
  transcripts with task/run counts, validation count, run errors, cost, and
  last-run state so operators can pick a follow-up session without opening raw
  JSONL files.
- `patchsmith chat --resume <session-id>` and
  `patchsmith agent --interactive --resume <session-id>` replay the transcript
  enough to restore context hints, model override, budget caps, task history,
  and last-run artifact pointers.

Next useful integration:

- add reusable profile and hook examples for cost-capped live runs,
  protected-file checks, verifier-first repair, and post-run report indexing,
  then validate them in a bounded live-model smoke.

### Agent-computer interface design

The SWE-agent paper argues that coding agents need interfaces designed for
their abilities, not just raw shells. Its agent-computer interface emphasizes
repository navigation, file editing, and test execution feedback.

PatchSmith's equivalent ACI should stay narrow and inspectable:

- retrieve and mount only reviewed repository context,
- force exact bounded replacements instead of unconstrained file writes,
- make sandbox failures compact and action-oriented,
- preserve target history so retries move to a new control point when needed,
- surface patch quality diagnostics before a patch is treated as validated.

Current gap:

- retry feedback is useful but still text-only. We need structured retry labels
  that can be aggregated across artifacts: `same_target_retry`,
  `moved_control_point`, `quality_retry`, `test_failure_retry`,
  `old_span_repair`, and `target_history_override`.

### Repo-map context routing

Aider's repo-map design is the strongest lightweight signal for PatchSmith's
context layer: give the model a compact symbol/signature view of the relevant
codebase instead of forcing it to infer structure only from full file reads.

PatchSmith's implementation stays stricter than a free-form coding assistant:

- `/.patchsmith/repo-map.md` is generated from retrieved context only,
- mounted files and omitted retrieved files are separated explicitly,
- matched symbols, matched terms, rank, score, method, and definition
  signatures are recorded per path,
- the DeepAgents contract records `repo_map_manifest_path` and
  `repo_map_manifest_read_first`,
- complex benchmark summaries report `repo_map_manifest_tasks`.
- after the 3-task smoke-lane ablation, repo-map is gated behind
  `PATCHSMITH_DEEPAGENTS_REPO_MAP=1` and is not a default behavior.

Current decision:

- repo-map is useful observability but failed the existing live smoke-lane gate.
  Keep it experimental until it improves the full gate, not only single-task
  Requests calibrations.

### Scoped repository instructions

The 2026 AGENTS.md evaluations are a useful warning: repository context files
can increase exploration and cost when they contain unnecessary requirements.
PatchSmith should therefore avoid dumping broad instruction files into every
run. The current integration is narrower:

- discover `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, and `.cursorrules` only at
  the repository root and ancestors of mounted source paths,
- cap the number and size of instruction files before mounting,
- mount them as `/.patchsmith/repo-instructions.md`,
- mark them as scoped constraints in `/.patchsmith/repair-interface.md`,
- record `repo_instructions_manifest_path` and
  `repo_instructions_manifest_read_first` in the DeepAgents contract,
- report repo-instructions manifest tasks and read-first rate in complex
  summaries,
- optionally gate those fields with `min_repo_instructions_manifest_rate` and
  `min_repo_instructions_read_first_rate` in context-policy suites.

Do not promote this to a hard suite gate until a fresh verifier lane shows that
it preserves validation and target alignment without increasing cost.

### Verified benchmark discipline

SWE-bench Verified shows why public issue benchmarks need human-reviewed issue
quality and test validity. PatchSmith should not claim broad repair quality from
raw public issues, setup success, or a single passing targeted test.

PatchSmith's benchmark rules:

- every public issue task needs a reviewed reproduction command,
- expected failure signals must be explicit before repair,
- final validation must run in a saved repair artifact,
- live-provider claims require provider, model, token, and cost metadata,
- aggregate pass rates must be paired with per-task cost and token outlier caps.

Current gap:

- the 3-task live suite is a credible smoke lane, not a general benchmark.
  The next public benchmark should add at least 10 reviewed tasks with task
  family labels and difficulty labels.
- context efficiency is now visible and enforceable through saved-artifact
  proxy metrics, and complex reports compute trace-derived target/context
  recall and precision when localized targets and mounted source paths are
  present. This is still not a full gold-context evaluation. To reach
  ContextBench-style evidence, each reviewed public issue needs annotated
  must-use context and distractor context so PatchSmith can compare against
  human labels, not only target-localization traces.

## Current Evidence

Saved DeepAgents evidence:

- canonical complex suite: 3/3 validated,
- target alignment: 1.0,
- live-provider tasks: 3,
- selected cost per validated task: about USD 0.059,
- selected tokens per validated task: about 89k,
- max selected task cost: about USD 0.0965,
- max selected task tokens: 123,860.

Fresh single-task live calibration:

- `requests_7223_chardet_extra` validated on the first live DeepAgents attempt
  with `gpt-5.4-mini`, local sandbox execution, 5 virtual context files, and no
  retries.
- Complex summary: 89,515 total tokens, estimated USD 0.07011, target
  alignment 1.0, quality warning rate 0.0, and selected validation rate 1.0.
- Artifact:
  `artifacts/experiments/public_issue_corpus_v1/requests_7223_live_current_20260614_complex_summary`.
- Interpretation: this widens current live evidence beyond the repeated
  `requests_7341` calibration, but it is still a one-task calibration, not a
  benchmark claim.

Fresh repo-map live calibration:

- `requests_7341_chunked_encoding_docs` validated on the first live DeepAgents
  attempt after adding `/.patchsmith/repo-map.md`.
- Complex summary: repo-map manifest tasks 1, 50,294 total tokens, estimated
  USD 0.039618, target alignment 1.0, quality warning rate 0.0, and selected
  validation rate 1.0.
- Artifact:
  `artifacts/experiments/public_issue_corpus_v1/requests_7341_live_repomap_20260614_complex_summary`.
- Interpretation: the repo map preserved validation and made the context layer
  visible in benchmark reports. It has not yet proven cost reduction.

Repo-map smoke-lane ablation:

- Suite spec:
  `evals/issue_corpora/public_issue_smoke_v1/complex_suite_repomap_20260614.json`.
- Suite artifact:
  `artifacts/experiments/complex_live_deepagents_public_issue_suite_repomap_20260614`.
- Result: 2/3 validated, validation rate 0.67, repo-map manifest tasks 3,
  total tokens 274,625, estimated USD 0.21685875, selected cost per validated
  task USD 0.108429375, selected tokens per validated task 137,312.5.
- Gate result: failed. Failures included validation rate below 1.0, cost per
  validated task above USD 0.07, tokens per validated task above 90k, and max
  selected task cost above USD 0.10.
- `requests_7223_chardet_extra` validated with repo-map but cost increased to
  USD 0.07472775 and 95,412 tokens.
- `pytest_14552_moved_file_filename` failed with repo-map. The model localized
  `src/_pytest/pathlib.py`, but PatchSmith's safety gate rejected the patch for
  introducing an unbound helper name `_is_same`.
- A guarded prompt/contract retry added `avoid_unbound_helper_names`, reduced
  the pytest run to 128,919 tokens and USD 0.102513, but still repeated the
  `_is_same` helper error and failed validation.
- Decision: keep repo-map experimental and default-off. The next improvement
  should be safety-gate retry feedback for rejected patches, not broader
  always-on context.

Safety-gate retry feedback calibration:

- `pytest_14552_moved_file_filename` validated with repo-map enabled after one
  safety-gate feedback retry.
- First attempt localized `src/_pytest/pathlib.py`, but PatchSmith rejected the
  edit because the replacement changed only comments or whitespace. The retry
  feedback artifact explicitly carried the safety rejection, stale-path sandbox
  cues, and `safety_gate=yes` attempt history.
- Second attempt moved to `src/_pytest/assertion/rewrite.py` and validated.
- Complex summary: validation rate 1.0, retry feedback rate 1.0, retry label
  counts `old_span_repair=1`, `safety_gate_retry=1`, `test_failure_retry=1`,
  repo-map manifest tasks 1, target alignment 1.0, quality warning rate 0.0,
  agent trajectory score 1.0, 553,483 total tokens, estimated USD 0.4252785,
  selected cost per validated task USD 0.4252785, live cost-budgeted tasks 1,
  live cost budget overage tasks 1, and max live cost budget overage USD
  0.1052785.
- Artifacts:
  `artifacts/experiments/public_issue_corpus_v1/pytest_14552_live_repomap_safety_retry_20260614`
  and
  `artifacts/experiments/public_issue_corpus_v1/pytest_14552_live_repomap_safety_retry_20260614_complex_summary`.
- Decision: safety-gate feedback is a real correctness improvement, but the
  run is a cost outlier. Keep it as an exploratory retry feature until
  PatchSmith has a cheaper retry context and stricter promotion gates for
  post-run cost overages.
- Promotion gate check: running the saved safety-retry artifact through
  `eval-complex-suite --max-live-cost-budget-overage-tasks 0` fails with
  `live cost budget overage tasks 1 exceeds 0`, as intended.
- Complex suite response-count gates now cap attempted and selected responses
  per validated task, plus max attempted and selected task responses. The
  baseline 3-task live suite passes with 18 responses total, 6.0 responses per
  validated task, and max task response count 7 under an 8-response cap.
- The repomap 3-task suite fails the response-count gate as negative evidence:
  validation rate 0.67, attempted/selected responses per validated task 8.5
  above the 6.0 cap, and cost/token gates also fail. This keeps repo-map
  evidence exploratory instead of promotable.

Negative R&D evidence:

- `PATCHSMITH_DEEPAGENTS_MAX_CONTEXT_FILES=3` on the pytest moved-file task
  failed validation and increased token use.
- The failed patch tried to mutate code-object filename metadata behind broad
  exception swallowing and best-effort fallback behavior.
- `/.patchsmith/repo-map.md` improved trace visibility but did not improve the
  full 3-task smoke lane; it caused or coincided with a pytest safety rejection
  and higher cost on `requests_7223`.
- Resulting decision: do not adopt a simple file-count cap as a default. Prefer
  better target manifests, safety-gate retry feedback, quality retry guidance,
  and response/cost/token gates.

## Near-Term Experiments

### E1: Retry quality remediation

Question:

Does explicit quality retry guidance reduce repeated high-risk mechanisms?

Implementation:

- run the pytest moved-file task with one feedback retry,
- keep the same model and context provider as the canonical live run,
- compare first attempt and retry for patch quality codes, target movement, and
  final validation.

Gate:

- no `broad_exception_swallow`,
- no `source_text_recompile`,
- no direct `co_filename` metadata rewrite unless justified by a passing full
  validation lane,
- validation passes,
- selected task cost remains below USD 0.10 or is recorded as an outlier.

Kill criterion:

- if the retry repeats the same high-risk mechanism or increases cost without
  validation, do not expand retries until feedback becomes more structured.

### E2: Structured retry labels

Question:

Can PatchSmith explain retry behavior across saved artifacts without manual
trace reading?

Current implementation:

- `feedback_retry` trace events now carry machine-readable retry labels.
- `eval-complex` and `eval-complex-suite` aggregate retry label counts from
  saved traces.
- Standard `eval-repair` and `eval-scaffold` outputs now carry the same retry
  labels and aggregate counts in JSON, CSV, and Markdown reports.
- Older retry traces without labels are counted as `unclassified_retry` rather
  than discarded.
- Safety-gate rejections now feed retry guidance and labels, so a rejected
  bounded edit can become a plan-repair retry instead of a generic no-patch
  failure.
- Complex benchmark summaries now flag actual live-cost budget overages by
  comparing saved trace cost with the configured preflight `max_live_cost_usd`.
- Complex benchmark suite gates can now fail when
  `max_live_cost_budget_overage_tasks` is exceeded. Public smoke suites require
  zero post-run budget overages.
- Public repair attempts can now set `--max-actual-model-responses` and
  `--max-actual-model-tokens`. A passing validation that exceeds either cap, or
  fails to record the capped value, is saved as `failed` rather than
  `validated`.
- Those actual-usage caps are also mounted into `/.patchsmith/repair-interface.md`
  as a DeepAgents resource budget and persisted in the DeepAgents planning
  contract. Budgeted runs default from `full` to `auto` subagent routing unless
  the caller explicitly sets a mode, so first attempts stay compact while
  feedback retries can still use subagents.

Implementation:

- add retry classification fields to repair-attempt summaries,
- include retry labels in `eval-complex` and `eval-complex-suite`,
- report rates for quality retries, same-target retries, and moved-control-point
  retries.

Gate:

- focused tests cover each label,
- existing 3-task suite remains green,
- reports can identify whether a retry learned from feedback.
- public repair summaries persist configured actual response/token caps beside
  observed model usage.
- resource budgets are visible in both the mounted repair-interface manifest
  and saved DeepAgents contract metadata.

Kill criterion:

- if labels cannot be computed from saved artifacts without brittle string
  parsing, keep them as trace-only until the runtime emits structured events.

### E3: Context budget alternatives

Question:

Can context be reduced without harming localization?

Current implementation:

- A hard file-count cap remains experimental because the first pytest
  moved-file cap run failed validation and increased token use.
- Capped DeepAgents runs now receive a `/.patchsmith/context-budget.md`
  manifest with mounted files, omitted retrieved files, ranked scores, symbols,
  matched terms, and compact excerpts.
- The manifest is explicitly included in the DeepAgents contract and allowed
  read policy, so package-backed runs can read it and reports can explain when
  the cap influenced the agent-computer interface.
- Complex benchmark reports now expose context-budget manifest tasks, omitted
  file counts, manifest path, context cap, and selected-attempt budget basis, so
  context experiments can be reviewed without opening raw traces.
- Context-cap selection now routes before spending tokens: capped DeepAgents
  runs preserve validation fixtures and structurally localized source targets
  such as symbol-qualified import-cache or stale-path control points before
  lower-signal retrieved files. This is intended to make future capped pytest
  moved-file reruns safer, but still needs live validation before promotion.
- Public-issue repair runs can now set this cap with
  `--deepagents-max-context-files`, so benchmark artifacts record the configured
  cap in attempt evidence instead of depending on shell-only state.
- Feedback retry attempts now pass a per-task DeepAgents `max_context_files`
  override equal to the original request `top_k`. Retry retrieval can still
  expand by three files for routing, but only the original context budget is
  mounted; omitted refreshed files are preserved in `/.patchsmith/context-budget.md`.

Fresh live result:

- On `requests_7341_chunked_encoding_docs`, uncapped current DeepAgents
  validated with 5 mounted files, 47,389 tokens, and estimated USD 0.037308.
- The same task with `PATCHSMITH_DEEPAGENTS_MAX_CONTEXT_FILES=2` also
  validated and the trace recorded `/.patchsmith/context-budget.md`, but token
  use increased to 53,642 and estimated cost increased to USD 0.04257525.
- After adding structured budget metadata, the same capped task validated again
  with 51,158 tokens and estimated USD 0.0403635. The trace recorded 5
  retrieved files, 2 mounted files, and 3 omitted files.
- On `pytest_14552_moved_file_filename`, a fresh one-task live workflow run
  after the retry-context change validated on the first attempt with repo-map
  enabled: 8 DeepAgents/OpenAI responses, 153,987 tokens, estimated USD
  0.11961525, target alignment 1.0, and zero live budget-overage tasks.
  Because the first attempt passed, this run
  proves the current agent still works on the task but does not exercise the
  retry-only mounted-context cap. Artifact:
  `artifacts/experiments/public_issue_corpus_v1/pytest_14552_retry_context_cap_live_20260614_114324`.
- A forced live retry-planner probe supplied 8 retry contexts and set the
  per-task runtime cap to 5. The real DeepAgents/OpenAI call returned a bounded
  plan, and the contract recorded 5 mounted files, 3 omitted files, and
  `/.patchsmith/context-budget.md`. It used 12 DeepAgents/OpenAI responses,
  224,906 tokens, and estimated USD 0.17267325, so the cap contract works in a
  live retry-shaped invocation, but DeepAgents' multi-step internal call
  pattern remains a cost pressure.
  Artifact:
  `artifacts/experiments/public_issue_corpus_v1/pytest_14552_forced_retry_context_cap_probe_20260614_114555`.
- After fixing the Python patch-safety gate to recognize helpers defined in
  both branches of a top-level `if/else`, the same pytest moved-file task
  validated with `--deepagents-max-context-files 4` and one feedback retry. The
  first attempt edited `src/_pytest/pathlib.py` and failed the focused test; the
  retry selected `src/_pytest/assertion/rewrite.py#_read_pyc`, added a stale
  `co_filename` guard, passed the focused test, and stayed low patch-quality
  risk. The run used 2 model calls, 18 DeepAgents/OpenAI responses, 388,496
  tokens, and estimated USD 0.29884575 under a USD 0.45 configured cap.
  Artifact:
  `artifacts/experiments/public_issue_corpus_v1/pytest_14552_safetyfix_cap4_retry1_live_20260614_140044`.
- A follow-up run with the new post-run actual-usage guardrails solved the same
  task again, but was intentionally saved as `failed` because actual model usage
  exceeded the configured claim caps. It used 2 model calls, 17
  DeepAgents/OpenAI responses, 355,708 tokens, and estimated USD 0.27443475
  against `--max-actual-model-responses 12` and
  `--max-actual-model-tokens 200000`. The final diff still passed the focused
  validation command with low patch-quality risk, so this is positive
  correctness evidence but negative budget-compliant benchmark evidence.
  Artifact:
  `artifacts/experiments/public_issue_corpus_v1/pytest_14552_usage_caps_live_allow_warnings_20260614_142810`.
- After mounting the same caps into the DeepAgents repair-interface resource
  budget and running with `--deepagents-subagents auto`, the task validated
  under both caps. Attempt 1 used compact inline routing and failed on the
  `src/_pytest/pathlib.py` target; the feedback retry enabled subagents,
  selected `src/_pytest/assertion/rewrite.py#_read_pyc`, and passed the focused
  validation command. Usage dropped to 2 model calls, 10 DeepAgents/OpenAI
  responses, 198,007 tokens, and estimated USD 0.1551465. The saved contract
  records `resource_budget: {max_model_responses: 12, max_model_tokens: 200000}`
  and `resource_budget_read_first: true`.
  Artifact:
  `artifacts/experiments/public_issue_corpus_v1/pytest_14552_resource_budget_auto_live_20260614_143925`.
- The same resource-budget auto mode was then run across the three-task public
  smoke lane. The lane validated 2 of 3 tasks with target alignment 1.0, no
  live cost-budget overage, 25 DeepAgents/OpenAI responses, 452,832 total
  tokens, and estimated USD 0.350964. Both Requests tasks validated under the
  per-task response/token caps; the pytest task passed the focused validation
  command but was saved as failed because it exceeded the claim caps in that
  suite run with 15 responses and 308,863 tokens. Complex benchmark reporting
  now exposes planning-time resource-budget observability separately from
  post-run spend evidence: `resource_budgeted_tasks=3`,
  `resource_budget_read_first_rate=1.0`,
  `avg_resource_budget_max_model_responses=12.0`, and
  `avg_resource_budget_max_model_tokens=200000.0`.
  Artifact:
  `artifacts/experiments/public_issue_corpus_v1/three_task_resource_budget_auto_live_20260614_144451`;
  report:
  `artifacts/experiments/public_issue_corpus_v1/complex_three_task_resource_budget_auto_live_20260614_144451`.
- A remaining-budget retry experiment then passed cumulative used/remaining
  response and token counts into DeepAgents retry attempts. The first live
  calibration proved the routing fired on retry (`remaining_response_budget`
  exhausted, subagents disabled) and still produced a passing patch, but the
  first attempt had already exceeded both caps, so the run remained failed:
  2 model calls, 18 responses, 345,261 tokens, estimated USD 0.265482.
  Artifact:
  `artifacts/experiments/public_issue_corpus_v1/pytest_14552_remaining_budget_retry_live_20260614_150151`.
- PatchSmith now blocks feedback retries when the declared response/token
  budget is already exhausted or too low for another budget-compliant retry.
  In the next live calibration, the gate skipped the second call after a failed
  first patch because only 1 response and 0 tokens remained. This reduced spend
  to 1 model call, 11 responses, 204,219 tokens, and estimated USD 0.156453,
  but the artifact still failed because the first call was 4,219 tokens over
  the configured cap. Artifact:
  `artifacts/experiments/public_issue_corpus_v1/pytest_14552_retry_budget_block_live_20260614_150406`.
- A tighter `PATCHSMITH_DEEPAGENTS_MAX_FILE_CHARS=12000` calibration reduced
  first-attempt usage to 8 responses and 147,725 tokens, but the retry consumed
  another 6 responses and 147,529 tokens. The final patch validated, but the
  artifact failed the response/token caps at 14 responses and 295,254 tokens.
  This supports the retry-block threshold: with only 4 responses and 52,275
  tokens remaining, another live retry is unlikely to produce a budget-compliant
  result. Artifact:
  `artifacts/experiments/public_issue_corpus_v1/pytest_14552_filechars12k_budget_live_20260614_150508`.
- The first span-mounted context calibration used
  `PATCHSMITH_DEEPAGENTS_CONTEXT_MODE=span`,
  `PATCHSMITH_DEEPAGENTS_CONTEXT_WINDOW_LINES=80`, and
  `PATCHSMITH_DEEPAGENTS_MAX_FILE_CHARS=8000`. It kept the first attempt under
  both claim caps at 1 model call, 9 responses, 146,913 tokens, and estimated
  USD 0.11340975. The run still failed validation because the first patch
  targeted `src/_pytest/pathlib.py#import_path`; the retry gate correctly
  blocked another attempt with only 3 responses and 53,087 tokens remaining.
  This is positive first-call compression evidence, but negative solve-rate
  evidence. Next bottleneck: first-attempt target selection must prefer the
  `_read_pyc` control point before spending a retry. Artifact:
  `artifacts/experiments/public_issue_corpus_v1/pytest_14552_span_context_budget_live_20260614_151426`.
- A later one-task live workflow run on the same pytest task, with the default
  DeepAgents context path and local sandbox execution because Docker was not
  running, also validated on the first attempt. The patch was a targeted guard
  in `src/_pytest/assertion/rewrite.py#_read_pyc`, target alignment stayed 1.0,
  and patch quality stayed low risk. It used 8 DeepAgents/OpenAI responses,
  159,183 tokens, and estimated USD 0.12625725. The correctness signal is
  positive, but the saved suite gate intentionally fails this artifact on
  attempted/selected cost per validated task, tokens per validated task,
  responses per validated task, max task cost, and max task tokens. Artifact:
  `artifacts/experiments/public_issue_corpus_v1/pytest_14552_live_deepagents_local_response_gate_20260614_121541`.
- Decision: the budget manifest and retry context pinning are useful
  observability/correctness tools and can preserve validation under a file cap,
  but file-count caps still are not a default cost optimization until a broader
  suite shows net token reduction.

### E3b: Inline subagent calibration

Question:

Can PatchSmith reduce DeepAgents internal response count without removing the
bounded patch contract?

Current implementation:

- `PATCHSMITH_DEEPAGENTS_SUBAGENTS=inline` disables the DeepAgents
  `failure-localizer` and `patch-reviewer` subagents for a run.
- `PATCHSMITH_DEEPAGENTS_SUBAGENTS=auto` keeps subagents enabled for retries,
  reviewed source hints, validation fixtures, and multi-context repairs, but
  disables them for simple single-control-point runs.
- The system prompt, mounted `/.patchsmith/AGENTS.md`, and mounted
  `patchsmith-repair` skill switch to inline localization and inline patch
  review instructions when subagents are disabled.
- The saved DeepAgents contract records `subagent_mode`, the empty `subagents`
  list, inline planning-policy flags, and a `subagent_routing` reason list so
  benchmark reports can distinguish this mode from the default full-subagent
  mode.
- PatchSmith now also mounts `/.patchsmith/repair-interface.md` for native
  DeepAgents runs. This is the compact agent-computer interface for the run:
  it lists required manifest reads, mounted source paths, subagent routing mode,
  preferred next patch paths when present, and the bounded `PatchPlan` output
  contract. The DeepAgents contract records `repair_interface_manifest_path`
  and `repair_interface_manifest_read_first`; treat this as an observability and
  interface-quality improvement until a live comparison shows a token or
  validation benefit.

Fresh live result:

- On `pytest_14552_moved_file_filename`, inline mode failed validation. The
  first attempt returned a no-op replacement that PatchSmith rejected, then the
  feedback retry moved to `src/_pytest/pathlib.py` and was rejected for an
  unbound helper name. The run used 16 DeepAgents/OpenAI responses, 321,449
  tokens, and estimated USD 0.247548, which is worse than the default
  full-subagent run. Artifact:
  `artifacts/experiments/public_issue_corpus_v1/pytest_14552_live_deepagents_inline_subagents_20260614_122634`.
- Decision: do not promote inline mode for validation-fixture or
  retry-sensitive public issues. Keep it only as an ablation until a simpler
  task family shows lower response count without reducing validation. Use
  `auto` as the next candidate because it should preserve subagents on the
  pytest moved-file task while allowing simpler tasks to skip delegation.

Gate:

- compare against the same task, model, context provider, sandbox, and retry
  budget,
- validation remains 1.0 on the task family under test,
- response count per validated task drops below the current 6-response suite
  cap or shows a clear reduction from the default run,
- selected cost and token use do not exceed the default full-subagent run,
- target alignment remains 1.0 and patch quality stays low risk.

Kill criterion:

- if inline mode lowers cost by skipping necessary localization and produces a
  wrong or high-risk patch, keep it as a task-family-specific ablation instead
  of a default.

Implementation:

- compare uncapped context, file-count cap, source-hint-first cap, and
  symbol-span cap on the same public tasks,
- compare hard caps against the retry-only mounted-context cap before trying
  another live pytest moved-file run,
- do not use the cap as default until it improves both validation and cost.

Gate:

- validation rate is not lower than uncapped,
- target alignment remains 1.0,
- selected tokens per validated task decreases by at least 20%,
- no increase in quality warning rate.

Kill criterion:

- any cap that fails validation or increases token use on the pytest outlier is
  labeled task-family-specific, not global.

### E4: Verified public issue expansion

Question:

Does PatchSmith generalize beyond the current 3-task smoke lane?

Implementation:

- add at least 10 reviewed public issue tasks,
- label each task by repository, failure family, source-hint quality, and
  expected fix difficulty,
- require reproduction and repair readiness before live spend.

Gate:

- validation rate reported with cost, tokens, target alignment, quality warning
  rate, and per-task outliers,
- failed tasks retain final diff, report, trace, and reproduction logs.

Kill criterion:

- if task specs are underspecified or tests admit too many valid solutions,
  exclude them from benchmark claims and keep them as exploratory cases.

## Product Rules From R&D

1. Keep DeepAgents as the primary live planning layer until another scaffold
   beats it on the same artifacts under the same model.
2. Treat context reduction as an experiment, not a default optimization.
3. Treat repo-map as experimental until it passes the full smoke-lane gate with
   better or equal validation and cost.
4. A passing targeted test is not enough when patch quality is high-risk.
5. Saved artifact gates are the source of truth for public claims.
6. Rubric presence is not enough. Verifier lanes should report manifest
   coverage, read-first rate, and deterministic rubric-alignment rate before a
   fresh live result is promoted.
7. Every new agent feature needs a benchmark metric, a cost bound, and a kill
   criterion before it becomes default behavior.
8. Safety-gate retry feedback can stay enabled for bounded experiments, but it
   needs a post-run cost outlier promotion gate before wider live-model use.
9. `--max-live-cost-usd` is a preflight estimate guard, not a hard post-spend
   ceiling. Benchmark reports now flag actual post-run overages, and release
   claims should treat those overages as failures unless explicitly waived. The
   public smoke-suite specs enforce this with
   `max_live_cost_budget_overage_tasks: 0`.
10. Retry attempts may reduce mounted DeepAgents files to the original `top_k`
   while preserving expanded refreshed retrieval in the context-budget manifest.
   Treat this as a retry-cost experiment until a live calibration proves token
   reduction without reducing validation.
11. Actual response and token ceilings are benchmark claim guardrails. Native
    DeepAgents now uses the configured response ceiling as an active callback
    tripwire, blocking the next model call once the cap is exhausted. Token caps
    still depend on provider usage arriving after a response, so a token overage
    can remain useful R&D evidence, but it should not count as
    benchmark-validated until the cap is raised deliberately or the agent is
    made cheaper.
12. When usage caps are configured, pass the same caps into the DeepAgents
    repair interface and use `auto` subagent routing unless a comparison lane
    explicitly requires `full` or `inline`. This turns the benchmark gate into a
    visible agent constraint instead of only a report-time rejection.
13. For response ceilings of six or fewer, use budget-critical mode: skip
    generic memory/skill required reads, mount the first preferred source/symbol
    as a Fast Patch Packet, and ask for the structured patch as soon as the
    controlling branch is clear. The local gate now verifies this path; the next
    live lane still needs to prove it under real model calls.
14. Complex benchmark reports now include selected-attempt progress score and
    partial-progress failed tasks. Treat this as the first SWE-EVO/SWE-Cycle
    style partial-progress metric, not a replacement for clean validation.
    live pytest outlier rerun should test whether it converts the current
    six-response no-patch stop into a validated repair.
15. Complex benchmark outputs now include
    `complex_benchmark_followup_candidates.json`, a deterministic ranked list
    of saved attempts worth rerunning or inspecting before the next live A/B
    lane. This is the first local analogue of RHO/SWE-Replay-style trajectory
    reuse: failed strict status, harness-layer attribution, process risk, retry
    failure classes, target misalignment, and spend outliers drive the ranking.
    Each candidate also carries a rule-based `action` and `suggested_profile`
    so the next run can be planned as a cost, context, retry, quality, runtime,
    or process-quality experiment instead of a generic rerun. `eval-complex-suite
    --json` returns the same candidates in `followup_candidates`, making the
    next-run planner scriptable. Candidates now also include
    `recommended_command` and `recommended_env`; for the current cost outlier,
    that command uses `--deepagents-max-context-files 4`,
    `--max-actual-model-responses 6`, `--max-actual-model-tokens 90000`, and a
    `$0.07` live-cost cap. Candidates also carry `validation_command` and
    `success_criteria`, so a live follow-up can be gated as a one-task complex
    suite immediately after it runs. The same ranked candidates are now rendered
    as `complex_benchmark_followup_runbook.md`, giving operators a shell-ready
    live command, validation command, environment requirements, and success
    criteria without scraping JSON. Verifier-gated suites now add
    `verifier_contract_rerun` candidates when selected validated attempts lack
    contextual-verifier or acceptance-rubric evidence, so historical passing
    artifacts turn into targeted rubric-backed rerun commands instead of a
    dead-end gate failure.
16. PatchSmith now has a product-facing `patchsmith agent` CLI entrypoint. It
    defaults to the current repo, DeepAgents, native hybrid context, auto
    subagent routing, one feedback retry, and explicit response/token budgets.
    This is the first Claude Code-style terminal surface. It remains
    artifact-first by default: proposed patches, traces, and reports are written
    under `artifacts/runs/<run_id>/`. Direct worktree mutation is available only
    through explicit `--apply`; the apply path requires a local Git repository,
    rejects dirty worktrees by default, runs `git apply --check`, and records
    the apply result in JSON output. The CLI also supports `--preflight`, which
    validates prompt loading, `OPENAI_API_KEY` presence, runtime budgets,
    context/apply settings, and target worktree state without starting
    DeepAgents or spending tokens.
    `patchsmith chat` and `patchsmith agent --interactive` add session-local
    `/model`, `/budget`, and `/context` mutations plus transcript resume by
    session id, so daily interactive runs preserve the model, budget, context,
    last-run artifacts, and task history needed for later benchmark analysis.

Rationale: Anthropic's agent guidance separates predictable workflows from
open-ended agents, OpenAI's Agents SDK models guardrails as explicit checks,
LangChain Deep Agents exposes filesystem/subagent context as part of the agent
interface, and SWE-agent-style work treats trajectories as evaluation evidence.
PatchSmith maps those patterns to saved benchmark gates: context contracts,
retry labels, patch-quality checks, and now actual response/token claim caps.

## References

- LangChain Deep Agents overview:
  https://docs.langchain.com/oss/python/deepagents/overview
- Anthropic Building Effective Agents:
  https://www.anthropic.com/engineering/building-effective-agents
- OpenAI Agents SDK guardrails:
  https://openai.github.io/openai-agents-python/guardrails/
- SWE-agent paper:
  https://arxiv.org/abs/2405.15793
- Aider repo-map documentation:
  https://aider.chat/docs/repomap.html
- SWE-bench Verified:
  https://openai.com/index/introducing-swe-bench-verified/
- ACON:
  https://arxiv.org/abs/2510.00615
- Evaluating AGENTS.md:
  https://arxiv.org/abs/2602.11988
- OpenHands Software Agent SDK:
  https://arxiv.org/abs/2511.03690
- SWE-Compass:
  https://arxiv.org/abs/2511.05459
- SWE-EVO:
  https://arxiv.org/abs/2512.18470
- SWE-CI:
  https://arxiv.org/abs/2603.03823
- RoadmapBench:
  https://arxiv.org/abs/2605.15846
- SlopCodeBench:
  https://arxiv.org/abs/2603.24755
