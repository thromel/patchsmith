# PatchSmith

[![CI](https://github.com/thromel/patchsmith/actions/workflows/ci.yml/badge.svg)](https://github.com/thromel/patchsmith/actions/workflows/ci.yml)

PatchSmith is a research platform for evaluating AI software-maintenance agents.

Give it a repository, an issue, and a test command. PatchSmith retrieves likely
context, lets an agent propose a bounded patch, runs validation in a sandbox,
and writes down the evidence: diffs, traces, stdout, stderr, timing, reports,
and model-cost metadata when a live model is used.

The goal is not to pretend every passing test means "the agent fixed it."
PatchSmith is built to answer the more useful question: what happened, why did
it happen, and can someone audit the repair attempt later?

## Status

PatchSmith is active R&D code.

The seeded benchmark lane is the stable development path. It is useful for
testing retrieval, scaffold behavior, sandbox execution, reporting, and release
gates. The public GitHub issue lane exists, but it is still calibration work.
Treat public-issue repair results as experimental unless they come with a saved
artifact directory that includes the repository state, issue spec, reproduction
command, patch, validation output, and model metadata.

Current public status is `ready_with_caveats`: the offline seeded-suite demo is
coherent, and live LLM calibration evidence exists for saved DeepAgents
`gpt-5.4-mini` runs in that benchmark lane only. Do not generalize those results
to public-issue repair quality without matching reproduction and validation
artifacts.

## What It Does

- Clones or copies target repositories into controlled workspaces.
- Indexes files, symbols, and issue text for context retrieval.
- Supports native keyword, hybrid, graph, and `ctxhelm` context providers.
- Runs repair attempts through deterministic baselines and the `deepagents`
  runtime adapter.
- Includes a native DeepAgents planner with file reads, todo state, a
  skills-backed repair contract, structured patch output, a patch-review
  subagent, and sandbox-feedback retries.
- Applies model output through PatchSmith's own bounded text-replacement gate.
- Runs local or Docker sandbox validation with command-policy checks.
- Produces Markdown, JSON, HTML, trace, diff, stdout, stderr, timing, and cost
  artifacts.
- Ships local quality gates for tests, static checks, package build, release
  hygiene, demo readiness, and artifact indexing.

## Why This Exists

Most coding-agent demos compress the whole story into one number: did the final
test pass?

That is too coarse for repair research. A run can fail because retrieval missed
the right file, the prompt scaffold asked the wrong thing, the model produced an
unsafe edit, the reproduction command was weak, the sandbox was misconfigured,
or the issue was never reproducible in the first place.

PatchSmith keeps those pieces separate. It is meant for comparing repair systems
without hiding setup failures, weak validation, or lucky patches.

## What PatchSmith Is Not

- It is not an autonomous GitHub issue fixer.
- It is not a hosted repair service.
- It is not proof that a focused test pass equals upstream acceptance.
- It is not a leaderboard claim against SWE-agent, OpenHands, or coding models.
- It is not a replacement for human review.

The model gets to propose. PatchSmith owns the mutation.

## How It Works

```text
issue + repository + test command
  -> clone or copy repository
  -> index files and symbols
  -> retrieve candidate context
  -> run a repair runtime
  -> apply one bounded patch
  -> run policy-checked validation
  -> write reports, traces, logs, diffs, and metrics
```

PatchSmith does not let a model write freely into the repository. A runtime can
inspect context and propose an edit. PatchSmith applies the final patch through
its own gate and records the result.

## Install

```bash
git clone https://github.com/thromel/patchsmith.git
cd patchsmith

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

For native DeepAgents experiments:

```bash
python -m pip install -e ".[dev,deepagents]"
```

## Quickstart

Run the test suite:

```bash
PYTHONPATH=src python -m pytest -q
```

Run PatchSmith as a terminal coding agent against the current repository:

```bash
patchsmith agent "Fix the failing parser test" \
  --test-command "python -m pytest tests/test_parser.py -q"
```

Run the canonical five-minute demo:

```bash
patchsmith demo seeded-logic-bug
```

Then inspect the generated run directory:

```bash
patchsmith inspect artifacts/demo/seeded_logic_bug/runs/<run_id>
```

The demo writes `report.md`, `final.diff`, `traces.jsonl`, validation logs,
`metadata.json`, and `context/selected_files.json`. A static preview lives in
[`docs/sample_artifacts/seeded_logic_bug/`](docs/sample_artifacts/seeded_logic_bug/).

Preflight the same command before spending on a model call:

```bash
patchsmith agent "Fix the failing parser test" \
  --test-command "python -m pytest tests/test_parser.py -q" \
  --preflight \
  --json
```

Preflight mode validates the task text, selected context/provider settings,
DeepAgents response/token budget, native DeepAgents prompt/tool token headroom,
reasoning-model token headroom, optional apply target, and whether
`OPENAI_API_KEY` is set in the environment. It does not call a model.

Start an interactive agent session:

```bash
patchsmith chat \
  --test-command "python -m pytest tests/test_parser.py -q"
```

`patchsmith agent --interactive` starts the same session shell. Inside chat,
plain text is treated as a repair task in act mode, while `/mode plan` makes
plain text run `/preflight` only until the pending planned task is approved
with `go ahead` or `/run`, discarded with `cancel plan`, or until `/mode act` is
selected again. Slash commands keep the session keyboard-first. Obvious control
phrases such as `what next?`, `show status`, `review diff`, `apply check`,
`go ahead`, `cancel plan`, and `apply it` route to their matching slash
commands instead of starting the wrong operation:

Actual `patchsmith chat`, `patchsmith agent --interactive`, and one-shot
`patchsmith agent` runs perform a live OpenAI model availability/auth preflight
before starting DeepAgents. `/preflight` remains a no-model-call local
diagnostic. Use `--skip-model-preflight` only for offline harnesses or deliberate
provider experiments.

- `/preflight <task>` validates config without a model call.
- `/mode [act|plan]` switches plain-text behavior between repair runs and
  preflight-only planning.
- `/run` executes the pending plan-mode task; `/run <task>` executes an
  explicit task immediately.
- `/cancel [plan]` discards the pending plan-mode task without clearing the
  rest of the session.
- `/context add <path[#symbol]>` pins a repo-relative file or symbol hint for
  later runs.
- `/context show`, `/context remove <path>`, and `/context clear` inspect or
  update those forced context hints.
- `/model [id|clear]` shows, sets, or clears the DeepAgents model override for
  later runs in the session.
- `/budget [responses <n>|tokens <n>|set <responses> <tokens>|clear]` shows or
  changes the session response/token caps. Use `-1` to disable a cap.
- `/doctor` checks local DeepAgents dependencies, API-key presence, model
  selection, budget caps, native DeepAgents prompt/tool token headroom,
  reasoning-model token headroom, and apply readiness before a run.
- `/cost` summarizes tasks, runs, validation count, run errors, model calls,
  responses, tokens, and estimated session cost from the transcript.
- `/metrics` summarizes transcript-derived process metrics: manual preflights,
  automatic run preflights, runs, validation rate, apply success rate, custom
  command count, context/model/budget/permission updates, verify runs, diff
  views/reviews, instruction and memory views, feedback views/updates, run
  evidence views, timeline views, next recommendations, apply approvals/rejections/blocks,
  checkpoints/restores, model tokens, and cost per validated run.
- `/gate [validated|clean|reviewed|applied|cost <usd>]` evaluates the current
  transcript against built-in evidence gates. `reviewed` requires a validated
  clean run, deterministic diff review, no high-risk diff review, and a ready
  `/apply check`.
- `/trace` or `/evidence` summarizes the last run's report, trace, diff,
  changed files, model usage, and cost without leaving chat.
- `/verify [command]` reruns the configured or explicit allowed test command
  through PatchSmith's sandbox command policy and records the result.
- `/run <task>` records the same readiness checks as `/preflight`, runs the
  live model preflight supplied by the CLI, then starts the DeepAgents repair
  loop.
- `/status` shows session, model, budget, context, and last-run artifact state.
- `/history` lists tasks from the current session.
- `/timeline [n]` shows the recent transcript event trail for task, run, gate,
  trace, checkpoint, feedback, hook, and config activity.
- `/next` recommends the next evidence-backed action from the transcript, such
  as approving or cancelling a pending plan-mode task, trace review, gating,
  apply, checkpoint, export, breaking a repeated failure loop, or turning a
  rejected apply decision into feedback before retrying.
- `/sessions` lists resumable chat transcripts under the current artifacts
  directory with usage, validation, error, and cost summaries.
- `/commands` lists project custom slash commands loaded from
  `.patchsmith/commands/*.md`.
- `/hooks` lists project lifecycle hooks loaded from `.patchsmith/hooks.json`.
- `/agents` lists project agent profiles loaded from `.patchsmith/agents/*.md`.
- `/agent [name|clear]` shows, selects, or clears the active project agent
  profile for later runs.
- `/instructions [show|reload|clear]` shows, reloads, or disables
  AGENTS.md/CLAUDE.md-style project instructions for later runs.
- `/memory [show|reload|clear]` shows the same loaded project memory through a
  Claude Code-style command and records separate memory-view transcript
  evidence.
- `/plan [show|set|add|start|done|block|skip|pending|clear]` manages a
  transcripted session plan. Active plan items are included as context for
  later runs.
- `/feedback <text>`, `/feedback show`, and `/feedback clear` capture
  human-in-the-loop guidance for later runs without changing the base task.
- `/checkpoint [label]`, `/checkpoints`, and `/restore <id|label>` save, list,
  and restore chat state without rewriting the transcript.
- `/permissions [show|apply auto|apply manual|dirty allow|dirty deny]` shows
  or changes apply intent and whether dirty worktrees are accepted by apply
  operations. In interactive chat, `apply auto` is artifact-first: after a run,
  PatchSmith records `apply_auto_deferred` and requires `/diff review`,
  `/apply check`, and `/apply` instead of mutating immediately.
- `/approve apply <reason>` records an explicit human approval for the current
  reviewed diff after `/apply check`; it is required before applying high-risk
  reviewed diffs.
- `/reject apply <reason>` records an explicit human denial for the current
  reviewed diff after `/apply check`; `/apply` stays blocked until a newer
  approval supersedes it, and `/next` recommends feeding the denial back into a
  retry instead of applying against the transcript.
- `/compact [note]` records a deterministic transcript summary and clears the
  in-memory task history while preserving last-run artifact pointers.
- `/clear` clears in-memory task, run, and apply state while retaining the
  transcript for audit and resume.
- `/export [path]` writes a Markdown session report from the JSONL transcript.
- `/diff` shows the last generated diff path, `/diff stat` summarizes files
  and line counts, `/diff show [lines]` prints a bounded diff preview, and
  `/diff review` runs deterministic patch-risk checks before apply.
- `/apply check` runs the same local repo, dirty-worktree, empty-diff, and
  `git apply --check` safeguards without mutating the working tree.
- `/apply` applies the last generated diff only after the current transcript has
  a non-high-risk `/diff review` and a ready `/apply check`; it then runs the
  same safe `git apply` checks used by `patchsmith agent --apply`. High-risk
  reviews require an explicit `/approve apply <reason>` event after the ready
  apply check before mutation is allowed; a newer `/reject apply <reason>`
  blocks mutation until superseded by a newer approval.
- `/rewind` or `/undo` reverses the last generated diff through
  `git apply --reverse --check` and then `git apply --reverse`.
- `/exit` or `/quit` ends the session.

Project custom commands are Markdown prompt templates under
`.patchsmith/commands/`. The filename becomes the slash command name, and
subdirectories become namespaces: `.patchsmith/commands/review.md` maps to
`/review`, while `.patchsmith/commands/bench/live.md` maps to `/bench:live`.
Optional frontmatter fields such as `description` and `argument_hint` appear in
`/commands` and `--list-commands --json`. PatchSmith substitutes `$ARGUMENTS`,
`{{arguments}}`, or `{{ args }}` with the text after the slash command, records
the command source in the transcript, and then runs the rendered prompt through
the same DeepAgents runner, trace, diff, cost, and apply machinery as `/run`.

Project agent profiles are Markdown specialist definitions under
`.patchsmith/agents/`. They are PatchSmith's lightweight version of file-based
subagents: the profile can set model/budget/context defaults and prepend
specialist instructions to the next bounded repair prompt, but it still runs
through the same safe runner and transcript path.

```markdown
---
description: Verification-focused repair mode
model: gpt-5-mini
subagents: inline
max_context_files: 3
max_model_responses: 4
max_model_tokens: 90000
test_command: pytest tests/test_parser.py -q
context_paths: |
  - src/parser.py#parse
  - tests/test_parser.py
---

Localize the failure before editing.
Reject broad rewrites.
```

Use `/agents` to list profiles and `/agent verifier` to select one inside
chat. One-shot runs can apply the same profile with `--agent-profile verifier`.
Selecting a profile is transcripted, replayed on resume, included in runtime
metadata, and counted in `/metrics`.

PatchSmith automatically loads concise project instruction files from the repo
root before a chat or one-shot agent run:

- `AGENTS.md`
- `CLAUDE.md`
- `CODEX.md`
- `GEMINI.md`
- `.cursorrules`
- `.patchsmith/instructions.md`

The loaded instruction context is size-capped, listed by `/instructions`, stored
in the session transcript, and included in runtime metadata. Extra repo-relative
files can be added with `--instruction-path`, and automatic instruction loading
can be disabled with `--no-agent-instructions`. These files guide the repair
prompt, but they do not override PatchSmith's safe runner, patch safety checks,
hooks, validation, or apply policy.

Session plans are lightweight task lists for complex work:

```text
/plan set inspect parser; write focused test; run validation
/plan start 1
/run Fix the parser edge case
/plan done 1
/plan show
```

Plans use explicit statuses: `pending`, `in_progress`, `completed`, `blocked`,
and `skipped`. PatchSmith stores plan changes in the transcript, restores them
on resume, includes active plan state in the next repair prompt, and counts plan
views/updates in `/metrics`.

Rewind is PatchSmith's lightweight checkpoint path for applied agent patches.
It is intentionally diff-scoped: `/rewind` reverses the last generated diff
instead of resetting the whole repository. That preserves unrelated worktree
state while still giving the user a quick way to back out a bad applied patch.
Rewind attempts and successes are transcripted and included in `/metrics`.

Session gates let you check whether an interactive session is ready to promote
without leaving the shell:

```text
/gate validated
/gate clean
/gate reviewed
/gate applied
/gate cost 0.05
```

`validated` requires at least one validated run. `clean` additionally requires
100% validation rate and zero run errors. `reviewed` adds deterministic diff
risk-review evidence, no high-risk diff reviews, and a ready non-mutating apply
check. `applied` requires successful apply attempts. `cost <usd>` caps cost per
validated run. Gate results are recorded in the transcript and counted in
`/metrics`; saved sessions can still be gated offline with
`patchsmith chat --session-gate`.

Project hooks are deterministic shell commands configured in
`.patchsmith/hooks.json`. PatchSmith passes a JSON envelope on stdin and records
hook outcomes in the chat transcript. Blocking hooks fail closed before
expensive or risky actions such as model runs and patch application:

```json
{
  "hooks": {
    "PreRun": [
      {
        "name": "budget-guard",
        "matcher": "benchmark|live",
        "command": "python scripts/check_budget.py",
        "timeout_seconds": 10
      }
    ],
    "PreApply": [
      {
        "name": "review-before-apply",
        "command": "python scripts/check_diff_policy.py"
      }
    ]
  }
}
```

Hook commands can print `{"decision": "block", "reason": "..."}` to stdout or
exit non-zero to stop the lifecycle event. Supported chat lifecycle events are
`SessionStart`, `SessionEnd`, `UserPromptSubmit`, `UserPromptExpansion`,
`PreRun`, `PostRun`, `PreApply`, and `PostApply`. `PreRun` and `PreApply` are
the main safety gates; post-event hooks are recorded as evidence but cannot
undo completed work.

Chat sessions write JSONL transcripts under `artifacts/chat_sessions/` so runs,
manual preflights, automatic run preflights, context changes, usage/cost
fields, apply decisions, and follow-up tasks remain auditable.

Resume a saved chat transcript by session id:

```bash
patchsmith chat --resume 20260614T195042Z-4be8450e
```

List saved chat sessions without starting the shell:

```bash
patchsmith chat --list-sessions
```

List project custom commands without starting the shell:

```bash
patchsmith chat --list-commands
patchsmith chat --list-commands --json
```

List project agent profiles without starting the shell:

```bash
patchsmith chat --list-agents
patchsmith chat --list-agents --json
```

List project instruction files without starting the shell:

```bash
patchsmith chat --list-instructions
patchsmith chat --list-instructions --json
```

List project hooks without starting the shell:

```bash
patchsmith chat --list-hooks
patchsmith chat --list-hooks --json
```

Print saved session metrics without starting the shell:

```bash
patchsmith chat --session-metrics 20260614T195042Z-4be8450e --json
```

Print the deterministic next recommendation for a saved session:

```bash
patchsmith chat --session-next 20260614T195042Z-4be8450e --json
```

Gate a saved session for CI or benchmark promotion:

```bash
patchsmith chat \
  --session-gate 20260614T195042Z-4be8450e \
  --require-validated-run \
  --min-validation-rate 1.0 \
  --require-diff-review \
  --max-high-risk-diff-reviews 0 \
  --require-ready-apply-check \
  --max-cost-per-validated-run-usd 0.05 \
  --max-run-errors 0
```

Export a saved transcript without resuming the shell:

```bash
patchsmith chat \
  --export-session 20260614T195042Z-4be8450e \
  --export-path artifacts/chat_sessions/20260614T195042Z-4be8450e.md
```

Run a scripted chat session:

```bash
patchsmith chat --script scripts/live-smoke.patchsmith
```

The script file contains the same lines you would type interactively, such as
`/doctor`, `/model gpt-5-mini`, `/budget set 4 60000`, `/review target`, or
`/exit`. This is useful for repeatable smoke runs and CI-friendly dry runs;
commands in the script still use the same chat transcript, preflight, runner,
trace, diff, cost, and apply boundaries.

The `agent` command defaults to:

- `--repo .`
- `--runtime deepagents`
- `--planner deepagents`
- `--context-provider native_hybrid`
- `--deepagents-subagents auto`
- `--max-model-responses 12`
- `--max-model-tokens 200000`

It writes the proposed patch, trace, validation output, and report under
`artifacts/runs/<run_id>/`. This is intentionally artifact-first: the current
CLI does not mutate the user's working tree unless asked.

To apply the generated diff back to a clean local Git worktree:

```bash
patchsmith agent "Fix the failing parser test" \
  --test-command "python -m pytest tests/test_parser.py -q" \
  --apply
```

`--apply` is intentionally explicit. It requires `--repo` to be a local Git
repository, rejects dirty worktrees by default, checks the generated diff with
`git apply --check`, and then applies it with `git apply`. Inside interactive
chat, `/apply` is stricter: it first requires the session to record
non-high-risk `/diff review` evidence and a ready `/apply check`. Pass
`--allow-dirty-apply` only when you intentionally want to apply into a worktree
that already has uncommitted changes.

Run a deterministic repair on a seeded bug:

```bash
PYTHONPATH=src python -m patchsmith.cli run \
  --repo evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo \
  --issue-file evals/tasks/seeded_bugs_v1/task_001_logic_bug/issue.md \
  --test-command "python3 -m pytest" \
  --runtime heuristic \
  --context-provider native_hybrid \
  --artifacts-dir artifacts \
  --json
```

Expected behavior: PatchSmith edits the seeded task repository, runs the pytest
command, and writes a run report under `artifacts/runs/<run_id>/`.

If you already know a likely file, force it into the context:

```bash
PYTHONPATH=src python -m patchsmith.cli run \
  --repo path/to/repo \
  --issue-file path/to/issue.md \
  --context-provider native_hybrid \
  --context-path "src/package/module.py#suspected_symbol" \
  --json
```

`--context-path` can be repeated. PatchSmith strips the optional `#symbol`
suffix before reading the file, but keeps the full hint in the issue text for
repair flows that provide reviewed hints.

## DeepAgents

PatchSmith has two DeepAgents modes:

- `runtime=deepagents, planner=heuristic`: adapter and scaffold compatibility.
- `runtime=deepagents, planner=deepagents`: native DeepAgents planning with a
  live OpenAI-compatible chat model.

The native planner seeds DeepAgents with a state-backed virtual filesystem,
read-only file permissions, a compact `/.patchsmith/repair-interface.md`
run manifest, a `/.patchsmith/acceptance-rubric.md` verifier checklist, a
`/.patchsmith/repo-instructions.md` scoped repository-instruction manifest, a
PatchSmith repair skill, a durable memory file, structured `PatchPlan` output,
a `failure-localizer` subagent, and a `patch-reviewer` subagent for ambiguous
or feedback-driven repairs. The repair interface is the
agent-computer interface for a run: it lists required manifests, mounted source
paths, subagent routing mode, and output constraints before the model explores
source files. The acceptance rubric is generated from the issue, mounted files,
preferred targets, validation fixtures, and unsafe-patch exclusions; it gives
the model a task-local checklist to verify the selected path, old span,
validation claim, and patch shape before final output. Repo instructions are
discovered only from AGENTS.md-style files at the repository root and ancestors
of mounted context paths, capped before mounting, and framed as scoped
constraints rather than permission for broad exploration. Native
DeepAgents plans must also include compact localization fields that name the
failing runtime mechanism and justify why the selected file/span controls it.
For cost experiments, `PATCHSMITH_DEEPAGENTS_SUBAGENTS=inline` disables the
DeepAgents subagents and requires the main planner to do localization and review
inline. Keep this mode experimental until saved live artifacts show lower
response count, token use, and cost without reducing validation.
`PATCHSMITH_DEEPAGENTS_SUBAGENTS=auto` is the safer ablation: it keeps
subagents for retries, reviewed source hints, validation fixtures, and
multi-context repairs, but disables them for simple single-control-point runs.
The default remains `full`.

PatchSmith only requests `reasoning.encrypted_content` for OpenAI model ids that
are expected to support reasoning items, such as `gpt-5*`, `o1*`, `o3*`, and
`o4*`. Non-reasoning models such as `gpt-4.1-mini` still use the Responses API
without that include flag, avoiding provider-side compatibility failures. Set
`PATCHSMITH_DEEPAGENTS_ENCRYPTED_REASONING=enabled` or
`PATCHSMITH_DEEPAGENTS_ENCRYPTED_REASONING=off` only for explicit provider
capability experiments; the default `auto` mode is recorded in DeepAgents
contract metadata.

Preflight a model before spending money:

```bash
OPENAI_API_KEY=... \
PYTHONPATH=src python -m patchsmith.cli openai-model-preflight \
  --model <model> \
  --json
```

Run the native DeepAgents planner on the seeded benchmark:

```bash
OPENAI_API_KEY=... \
PATCHSMITH_DEEPAGENTS_MODEL=<model> \
PYTHONPATH=src python -m patchsmith.cli eval-repair \
  --dataset evals/tasks/seeded_bugs_v1 \
  --runtime deepagents \
  --planner deepagents \
  --max-retries 1 \
  --max-tasks 10 \
  --context-provider native_hybrid \
  --output artifacts/experiments/deepagents_native_repair_eval_v1 \
  --json
```

Do not cite model performance from a README command. Use the saved artifact
directory for the exact run: model name, account, prompt, dataset, commit, diff,
logs, and validation output all matter.
Keep `--max-tasks` set on live runs unless you are intentionally expanding the
benchmark and budget.

Optional context-budget experiments:

```bash
PATCHSMITH_DEEPAGENTS_CONTEXT_MODE=span \
PATCHSMITH_DEEPAGENTS_CONTEXT_WINDOW_LINES=80 \
PATCHSMITH_DEEPAGENTS_SUBAGENTS=auto \
PYTHONPATH=src python -m patchsmith.cli execute-public-issue-repairs \
  --deepagents-max-context-files 2 ...
```

`--deepagents-max-context-files` limits the number of repository files mounted
into the DeepAgents virtual filesystem while preserving reviewed source hints,
validation fixtures, and strong target-localization signals such as
symbol-qualified control points first. The default `0` keeps the full retrieved
context because smaller mounts can make the model ask for more reasoning tokens;
use this knob only when the saved trace and suite gate prove a net improvement.
`PATCHSMITH_DEEPAGENTS_CONTEXT_MODE=span` is a separate first-attempt
compression lane: mounted repository paths stay stable, but each mounted source
file is narrowed to a focused line window around matched symbols, runtime-cache
cues, or reviewed source hints. Keep it opt-in until a saved live suite shows
lower tokens without losing target alignment or validation.
Complex benchmark
reports include DeepAgents virtual-file count, context-cap usage, tokens, and
cost so these experiments can be compared from saved artifacts. They also
report repair-interface and acceptance-rubric manifest tasks plus read-first
rates, and repo-instructions manifest tasks plus read-first rate, so
interface/verifier/context changes are visible in benchmark summaries instead
of requiring manual trace inspection. Trajectory reports keep the legacy agent
trajectory score stable and expose contextual-verifier coverage as a separate
rate, so verifier adoption can be compared without silently moving older score
thresholds. Use `min_contextual_verifier_rate` or
`--min-contextual-verifier-rate` when a complex suite must prove verifier
coverage from saved traces; `refresh-evidence` exposes the same gate as
`--complex-suite-min-contextual-verifier-rate`. Use
`min_repo_instructions_manifest_rate` and
`min_repo_instructions_read_first_rate` when a context-policy lane must prove
scoped AGENTS.md-style repository guidance was mounted and read before source
edits. Use
`evals/issue_corpora/public_issue_smoke_v1/complex_suite_verifier.template.json`
for the next rubric-enabled live lane; the older `complex_suite.template.json`
remains the historical pre-rubric baseline.
Public issue repair summaries and rows also record actual model calls, tokens,
and estimated cost; rows that exceed configured post-run live-cost,
response-count, or token-count caps after execution are not counted as
validated claims.
Use `--max-actual-model-responses` and `--max-actual-model-tokens` on live
public-issue runs when a benchmark lane needs hard claim limits for DeepAgents'
internal call volume. PatchSmith mounts those limits into
`/.patchsmith/repair-interface.md` as a resource budget so the agent sees the
claim boundary before exploring source, and the native DeepAgents planner now
installs an active response-budget callback that blocks the next model call once
the configured response count is exhausted. Token caps are still checked from
recorded provider usage after each response, so token overages remain failed
claims even when the final patch passes tests. Reasoning-model runs can spend
tens of thousands of tokens before producing visible output, so calibrate
initial token caps from a small preflight lane before treating low caps as
product defaults. For response ceilings of six or
fewer, PatchSmith also switches the repair interface into budget-critical mode:
generic memory/skill reads are no longer required, the first preferred
source/symbol is mounted as a compact Fast Patch Packet, and the prompt asks the
agent to return a structured `PatchPlan` as soon as the controlling branch is
clear. Add `--deepagents-subagents auto` for budgeted calibration lanes; it
keeps retries eligible for subagents but uses compact inline
localization/review on the first attempt.
The subagent mode is reported in the DeepAgents contract as `subagent_mode`
with a `subagent_routing` reason list. The same contract records
`repair_interface_manifest_path` and `repair_interface_manifest_read_first` so
saved artifacts prove which run interface the model received. Use `auto` or
`inline` only for side-by-side calibration runs, not as default performance
claims.

## Evaluation Commands

Validate the seeded dataset:

```bash
PYTHONPATH=src python -m patchsmith.cli validate-dataset \
  --dataset evals/tasks/seeded_bugs_v1 \
  --output artifacts/experiments/seeded_dataset_validation_v1 \
  --json
```

Compare retrieval providers:

```bash
PYTHONPATH=src python -m patchsmith.cli eval-retrieval \
  --dataset evals/tasks/seeded_bugs_v1 \
  --context-provider native \
  --context-provider native_hybrid \
  --context-provider native_graph \
  --context-provider ctxhelm_cli \
  --output artifacts/experiments/retrieval_eval_v1 \
  --json
```

Run a DeepAgents compatibility repair benchmark:

```bash
PYTHONPATH=src python -m patchsmith.cli eval-repair \
  --dataset evals/tasks/seeded_bugs_v1 \
  --runtime deepagents \
  --planner heuristic \
  --context-provider native_hybrid \
  --output artifacts/experiments/deepagents_compatibility_repair_eval_v1 \
  --json
```

Compare scaffold variants:

```bash
PYTHONPATH=src python -m patchsmith.cli eval-scaffold \
  --dataset evals/tasks/seeded_bugs_v1 \
  --variant agentless \
  --variant heuristic \
  --variant deepagents \
  --context-provider native_hybrid \
  --output artifacts/experiments/scaffold_comparison_v1 \
  --json
```

Summarize a completed public-issue repair lane as a complex benchmark:

```bash
PYTHONPATH=src python -m patchsmith.cli eval-complex \
  --attempt-dir artifacts/experiments/public_issue_corpus_v1 \
  --benchmark public_issue_smoke_v1_latest_all \
  --output artifacts/experiments/complex_deepagents_public_issue_smoke_v1_latest_all \
  --json
```

`eval-complex` reads saved repair-attempt artifacts, traces, and reports. It
does not run repositories, execute tests, or call a model provider.

Aggregate multiple saved public-issue repair lanes into a gated complex suite:

```bash
PYTHONPATH=src python -m patchsmith.cli eval-complex-suite \
  --suite-spec evals/issue_corpora/public_issue_smoke_v1/complex_suite.template.json \
  --validate-only \
  --json

PYTHONPATH=src python -m patchsmith.cli eval-complex-suite \
  --suite-spec evals/issue_corpora/public_issue_smoke_v1/complex_suite.template.json \
  --json
```

The suite spec contains the saved attempt directories, output directory, and
gate thresholds. Selected cost/token/response caps measure the chosen best
attempt per task; attempted cost/token/response caps measure total spend across
all evaluated attempts, so exploratory changes that validate but waste model
budget or internal DeepAgents calls still trip the suite gate. Max
attempted/selected task caps catch single-task cost, token, or response-count
outliers that an aggregate average can hide. Suites can also set
`min_target_alignment_rate` to require final patches to stay inside paths
localized by explicit target candidates or by DeepAgents' structured
failure-localization rationale for the selected patch plan. Complex summaries
also report selected-attempt context-efficiency proxies: virtual files, virtual
files per validated task, tokens per virtual file, and responses per virtual
file. They also report selected context-target recall and precision whenever
the saved trace includes both localized target paths and DeepAgents mounted
source paths. Suite gates can cap the proxy metrics with
`max_selected_virtual_files_per_validated_task`,
`max_selected_tokens_per_virtual_file`, and
`max_selected_responses_per_virtual_file`, and can require target/context
coverage with `min_selected_context_target_recall` and
`min_selected_context_target_precision`. Complex reports also expose a
trace-derived progress score so failed long-horizon attempts can distinguish
reproduction-only, patch-generated, target-aligned, quality-warning, and clean
validated stages. Use `min_selected_progress_score` when a suite must enforce
that retained attempts reached a minimum partial-progress floor. They also emit
deterministic failure-class counts for triage buckets such as validated,
quality-risk, preflight-blocked, reproduction-failed, no-patch,
target-misaligned, runtime/tool failure, retry-exhausted, and validation-failed;
these labels are artifact-derived benchmark signals, not human root-cause
annotations. Complex reports also aggregate a HarnessFix-style
`harness_layer` label so failed attempts can be triaged by the implicated
layer: budget, model, sandbox, preflight, reproduction, planning, context,
patch quality, retry, runtime, validation, or orchestration. DeepAgents feedback retries also carry a narrower runtime
`retry_failure_class` in the retry artifact and trace payload so the next
attempt sees whether it is handling validation failure, safety-gate rejection,
quality risk, repeated-target failure, or missing validation before editing.
Complex summaries aggregate those retry classes as `retry_failure_class_counts`
so retry-policy experiments can be compared from saved traces. They also emit
process-quality labels and flags derived from the same trace. A validated patch
can still be marked process-risky when the trace lacks verification, uses an
unclassified retry, churns through repeated failed events, or edits again after
successful verification; use `process_quality_label_counts`,
`process_quality_flag_counts`, and `process_risky_validated_tasks` when
checking for AgentLens-style lucky-pass risk.
Suites can enforce those process diagnostics with `min_process_quality_score`
and `max_process_risky_validated_tasks`.
Verifier lanes can also require the
task-local acceptance rubric to be mounted and read before final output with
`min_acceptance_rubric_manifest_rate` and
`min_acceptance_rubric_read_first_rate`. They can also require the selected
patch to satisfy deterministic rubric-alignment proxies with
`min_acceptance_rubric_alignment_rate`, which checks that the patch was rubric
backed, target-aligned, mounted-context bounded, and free of patch-quality
warnings. The `refresh-evidence` CLI exposes the
same gates as `--complex-suite-min-acceptance-rubric-manifest-rate` and
`--complex-suite-min-acceptance-rubric-read-first-rate`, plus
`--complex-suite-min-acceptance-rubric-alignment-rate`.
`refresh-evidence --complex-suite-spec ...` can regenerate the same suite report
and `complex_benchmark_suite_gate.json` from saved attempt artifacts without
spending live-model tokens. The validation-only command checks the suite
interface first: attempt directories, required result files, output path, and
gate-threshold count. When verifier or acceptance-rubric gates are requested
and older saved attempts lack that evidence, the suite also emits
`verifier_contract_rerun` follow-up candidates and a shell-ready runbook for
rubric-backed DeepAgents reruns.

Build an artifact index:

```bash
PYTHONPATH=src python -m patchsmith.cli index-artifacts \
  --artifacts-dir artifacts \
  --output artifacts/experiments/index.md \
  --json-output artifacts/experiments/index.json \
  --html-output artifacts/experiments/index.html \
  --run-detail-output-dir artifacts/experiments/run-details \
  --json
```

## Public Issue Corpus

The public issue smoke lane lives under
`evals/issue_corpora/public_issue_smoke_v1`.

It has separate gates for corpus validation, repository preflight, source-free
context preview, task materialization, focused test planning, setup validation,
reproduction evidence, repair readiness, and repair attempts.

That separation is intentional. A public issue repair should only count after
the failing behavior is reproduced, a patch is generated, and validation passes.
Passing setup checks are useful evidence, but they do not prove repair quality.

## Docker Sandbox

Build the seeded smoke image:

```bash
docker build -f docker/seeded-smoke.Dockerfile -t patchsmith-seeded-smoke:py312 .
```

Run with Docker isolation:

```bash
PYTHONPATH=src python -m patchsmith.cli run \
  --repo evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo \
  --issue-file evals/tasks/seeded_bugs_v1/task_001_logic_bug/issue.md \
  --test-command "python3 -m pytest" \
  --runtime heuristic \
  --context-provider native_hybrid \
  --sandbox-mode docker \
  --sandbox-image patchsmith-seeded-smoke:py312 \
  --artifacts-dir artifacts \
  --json
```

Docker mode disables implicit image pulls, disables network by default, drops
capabilities, mounts the repository at `/workspace`, applies resource limits,
and records the selected sandbox in the trace.

## Quality Gate

Run the local release gate:

```bash
PYTHONPATH=src python -m patchsmith.cli quality-gate \
  --project-root . \
  --artifacts-dir artifacts \
  --output artifacts/experiments/quality_gate.md \
  --json-output artifacts/experiments/quality_gate.json \
  --logs-dir artifacts/experiments/quality_gate_logs \
  --json
```

The gate runs compile checks, whitespace checks, the full pytest suite, and a
package build. CI also runs Ruff, Ruff format check, mypy, compile checks,
pytest, and package build.

## Repository Layout

```text
src/patchsmith/
  cli/                     CLI commands
  evaluation/              seeded and public-issue evaluation flows
  observability/           artifact index, failure reports, renderers
  portfolio/               readiness, release, and demo reports
  runtime/                 agent runtime adapters
  deepagents_planner.py    native DeepAgents planner
  deepagents_prompts.py    native DeepAgents prompts, memory, and skill text
  deepagents_schema.py     native DeepAgents structured output schema
  retrieval.py             native retrieval providers
  sandbox.py               local and Docker command execution

docs/                       architecture, safety, evaluation, and runbook docs
evals/                      seeded tasks and public issue corpora
adr/                        architecture decision records
experiments/                experiment plans
templates/                  report and ADR templates
```

## Good First Commands

```bash
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m patchsmith.cli demo seeded-logic-bug
PYTHONPATH=src python -m patchsmith.cli quality-gate --json
PYTHONPATH=src python -m patchsmith.cli project-status --json
PYTHONPATH=src python -m patchsmith.cli demo-readiness --json
```

## Public Evidence Docs

- [Artifact gallery](docs/artifact_gallery.md)
- [Failure taxonomy](docs/failure_taxonomy.md)
- [Benchmark manifest schema](docs/benchmark_manifest_schema.md)
- [Runtime fairness checks](docs/runtime_fairness_checks.md)
- [Comparison matrix](docs/comparison_matrix.md)
- [Changelog](CHANGELOG.md)

## Roadmap

- Calibrate live DeepAgents runs against the seeded benchmark.
- Expand public-issue reproduction coverage without treating setup success as
  repair success.
- Add more model/provider cost accounting.
- Improve artifact comparison for retrieval, patch quality, retries, and
  validation strength.
- Keep the runtime adapters small enough to read and test.

## License

MIT. See [LICENSE](LICENSE).
