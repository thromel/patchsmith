from __future__ import annotations

from collections.abc import Iterable, Mapping

PATCHSMITH_DEEPAGENTS_MEMORY_PATH = "/.patchsmith/AGENTS.md"
PATCHSMITH_DEEPAGENTS_SKILL_DIR = "/.patchsmith/skills/"
PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH = (
    f"{PATCHSMITH_DEEPAGENTS_SKILL_DIR}patchsmith-repair/SKILL.md"
)
PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH = "/.patchsmith/source-hints.md"
PATCHSMITH_DEEPAGENTS_RETRY_FEEDBACK_PATH = "/.patchsmith/retry-feedback.md"
PATCHSMITH_DEEPAGENTS_TARGET_HISTORY_PATH = "/.patchsmith/target-history.md"
PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH = "/.patchsmith/context-budget.md"
PATCHSMITH_DEEPAGENTS_REPO_MAP_PATH = "/.patchsmith/repo-map.md"
PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH = "/.patchsmith/repo-instructions.md"
PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH = "/.patchsmith/repair-interface.md"
PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH = "/.patchsmith/acceptance-rubric.md"


def deepagents_patch_quality_policy_md() -> str:
    return (
        "## Patch Quality Policy\n"
        "- Prefer the smallest source-behavior change at the controlling mechanism.\n"
        "- Avoid broad `except Exception`, bare `except:`, silent `pass`, catch-and-return "
        "fallbacks, or best-effort fallback behavior unless the issue specifically requires "
        "a defensive boundary. Prefer an explicit precondition check at the controlling "
        "branch over wrapping the repair in broad exception handling. If a defensive "
        "boundary is unavoidable, catch the specific expected exception and `target_rationale` "
        "must name why lower-risk control points are insufficient and what broader validation "
        "is required.\n"
        "- Avoid mutating function `__code__`, manually rebuilding `types.CodeType`, "
        "rewriting code-object metadata such as `co_filename`, or assigning module "
        "`__file__` metadata unless the defect is specifically in metadata construction "
        "and no earlier import, cache, compile, or dispatch site can fix the root cause.\n"
        "- Avoid bypassing a bytecode/module cache by directly recompiling source text "
        "with patterns like `compile(source.read_text(...), ...)`. For stale-cache "
        "failures, prefer rejecting or invalidating the stale cached entry before it is "
        "returned, using a full source-path check rather than a basename-only guard.\n"
        "- Avoid naked cache side-effect patches such as only adding "
        "`importlib.invalidate_caches()`; cache fixes must change the stale read, return, "
        "recompile, or invalidation branch that directly controls the failing value.\n"
        "- Do not introduce calls to helper functions, variables, or methods that are not "
        "already bound in the selected file or included in the returned replacement span. "
        "If a helper is necessary, include its definition in the bounded replacement and "
        "`target_rationale` must name why the larger span is still the smallest safe "
        "control-point edit.\n"
        "- Python replacement spans must be syntactically complete. Do not let `old` "
        "end on a compound statement header such as `if ...:`, `try:`, `with ...:`, "
        "`def ...:`, or `class ...:` unless `new` is only replacing that header "
        "with another header that keeps the existing body. Include the complete "
        "block when changing the body.\n"
        "- The `new` span must make a concrete source-behavior change. Never return "
        "an identical span, a comment-only change, or whitespace-only change as the "
        "repair. If you select the right symbol but cannot identify the edit, return "
        "the smallest behavior-changing branch in that symbol rather than a no-op.\n"
        "- Avoid test, fixture, docs, examples, and report-only targets unless the issue "
        "explicitly asks to change that surface.\n"
        "- Do not expand a tiny old span into a large implementation block without a "
        "concrete target_rationale and validation scope.\n"
    )


def deepagents_system_prompt(*, subagents_enabled: bool = True) -> str:
    subagent_instruction = (
        "When source hints span multiple mechanisms, ask the failure-localizer subagent "
        "to identify the controlling code path before drafting the edit.\n"
        "When a fix is multi-file or ambiguous, ask the patch-reviewer subagent to review "
        "the intended bounded edit; skip that subagent for obvious one-line fixes.\n"
        if subagents_enabled
        else "Subagents are disabled for this calibration run. Do failure localization "
        "and patch review inline, keep the reasoning compact, and return one bounded "
        "replacement only after rereading the selected file.\n"
    )
    return (
        "You are PatchSmith's native DeepAgents repair planner.\n"
        "Use DeepAgents planning deliberately: create and update todos before reading files.\n"
        "Use the state-backed filesystem tools to inspect the provided files.\n"
        "If a PatchSmith repair-interface manifest is provided, read it first; "
        "it is the compact agent-computer interface for this run and summarizes "
        "the available files, required manifests, routing mode, and output contract.\n"
        "When that repair interface contains Budget-Critical Mode, its required-read "
        "list overrides the generic read order below.\n"
        f"If `{PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH}` is provided, read it "
        "before final patch output and use it as the codebase-grounded verifier "
        "checklist for the chosen path, old span, and validation claim.\n"
        "If validation fixture files are provided, read them first and identify the "
        "runtime mechanism they exercise before choosing a patch target.\n"
        "If a PatchSmith source-hints manifest is provided, read it before broad "
        "source exploration and treat symbol-qualified hints as prioritized evidence.\n"
        "If a PatchSmith repo-map manifest is provided, read it before target selection; "
        "it summarizes mounted and omitted retrieved files, key symbols, and definition "
        "signatures for routing without expanding every source file.\n"
        "If a PatchSmith repo-instructions manifest is provided, read it after the "
        "repair interface and before source edits. Apply only the scoped constraints "
        "that match mounted files; do not broaden exploration because of generic "
        "repository guidance.\n"
        "If a PatchSmith retry-feedback manifest is provided, read it before planning "
        "and use it to avoid repeating a rejected old span or failed diff.\n"
        "If a PatchSmith target-history manifest is provided, read it before choosing "
        "a patch path; PatchSmith rejects listed paths unless target_rationale names "
        "distinct new branch or call-site evidence and cites an identifier from the old span.\n"
        "If a PatchSmith context-budget manifest is provided, read it before final target "
        "selection. It lists retrieved files that were not mounted under the current context "
        "budget; treat omitted files as routing evidence, not readable source files.\n"
        "When target-history lists Preferred Untried Source Targets, choose one of those "
        "paths for the next patch unless a historical path has explicit old-span evidence "
        "for a different control point. When it lists Revived Historical Control Points, "
        "those paths are allowed only with fresh old-span evidence and a rationale that "
        "names the distinct control point.\n"
        "Anchor the edit in the failing runtime mechanism before returning a patch; "
        "do not patch only path normalization or comments unless the validation output "
        "makes that the direct defect.\n"
        "Do not return an import-only patch for a behavioral failure unless the sandbox "
        "failure is ImportError, ModuleNotFoundError, or NameError and the imported name "
        "directly fixes that failure. Never add duplicate imports or an import that already "
        "exists in the file.\n"
        f"{subagent_instruction}"
        f"{deepagents_patch_quality_policy_md()}\n"
        "Return the structured patch plan with string fields: path, old, new, summary, "
        "failure_mechanism, and target_rationale.\n"
        "Set failure_mechanism to the concise runtime mechanism causing the observed "
        "failure. Set target_rationale to why the selected file and old span control "
        "that mechanism; on retry, include why the prior failed target or old span was "
        "insufficient.\n"
        "The path must be one of the provided repository paths. The old field must be "
        "an exact text span from that file, without line-number display prefixes. "
        "Copy the old span verbatim after rereading the selected file; preserve existing "
        "indentation, receiver qualifiers such as `self.`, and argument names. Do not "
        "reconstruct source from memory or invent in-scope variable names in the new span. "
        "For Python, choose a syntactically complete old/new span; do not stop `old` "
        "on an `if`, `try`, `with`, `def`, or `class` header without its body. "
        "Do not return markdown or extra prose."
    )


def deepagents_agents_md(*, subagents_enabled: bool = True) -> str:
    subagent_steps = (
        "14. For validation-fixture, ambiguous, or feedback-retry repairs, ask the "
        "failure-localizer subagent to identify the controlling code path.\n"
        "15. For ambiguous, multi-file, or feedback-retry repairs, ask the patch-reviewer "
        "subagent to review the intended bounded replacement before returning the patch plan.\n"
        if subagents_enabled
        else "14. Subagents are disabled for this run. Perform failure localization inline "
        "by naming the controlling code path before drafting the edit.\n"
        "15. Perform patch review inline before returning the patch plan: check that the "
        "replacement is minimal, retrieval-bound, and avoids high-risk patch shapes.\n"
    )
    return (
        "# PatchSmith DeepAgents Repair Contract\n\n"
        "Use this memory file as the durable repair workflow for PatchSmith runs.\n\n"
        "1. Read `/.patchsmith/repair-interface.md` first when present; it is the "
        "compact run interface and lists required reads, mounted source paths, "
        "routing mode, and output constraints.\n"
        "2. Create and maintain a short todo list before reading files.\n"
        "3. Read validation fixture files first when present, then read the provided source "
        "files through the virtual filesystem before choosing an edit.\n"
        "4. Read `/.patchsmith/source-hints.md` when present; symbol-qualified hints are "
        "reviewed reproduction evidence and should be inspected before broad edits.\n"
        "5. Read `/.patchsmith/repo-map.md` when present; it summarizes retrieved files, "
        "mounted/omitted status, key symbols, and definition signatures so target "
        "selection starts from a compact codebase map.\n"
        "6. Read `/.patchsmith/repo-instructions.md` when present; it contains "
        "scoped repository instruction files such as AGENTS.md for mounted paths. "
        "Apply only the listed constraints that match this run, and do not use them "
        "as a reason for unrelated exploration.\n"
        "7. Read `/.patchsmith/acceptance-rubric.md` when present; it is the "
        "codebase-grounded verifier checklist for the selected target, bounded old "
        "span, validation claim, and unsafe-patch exclusions.\n"
        "8. Read `/.patchsmith/retry-feedback.md` when present; it summarizes the "
        "previous failed attempt, sandbox signals, and patch diagnostics.\n"
        "9. Read `/.patchsmith/target-history.md` when present; it lists targets that "
        "were already selected or marked ineffective. PatchSmith rejects these paths "
        "unless target_rationale names a distinct new branch or call-site rationale "
        "and cites an identifier from the proposed old span. If it lists Preferred "
        "Untried Source Targets, choose one of those paths before returning to a "
        "historical target. If it lists Revived Historical Control Points, those paths "
        "are eligible only with fresh old-span evidence.\n"
        "10. Read `/.patchsmith/context-budget.md` when present; it lists retrieved files "
        "that were omitted from the mounted filesystem by the context budget. Use it as "
        "routing evidence and do not return an omitted path unless it is also available "
        "as a mounted provided file.\n"
        "11. Trace the failure to the runtime mechanism that controls the observed behavior; "
        "avoid cosmetic edits, comments, or path-only normalization unless the failure evidence "
        "proves that is the defect.\n"
        "12. Avoid import-only patches for behavioral failures unless the sandbox failure is "
        "ImportError, ModuleNotFoundError, or NameError and the imported name directly fixes "
        "that failure; do not add duplicate imports.\n"
        "13. Prefer source fixes over changing reproduction fixtures or tests.\n"
        f"{subagent_steps}"
        "16. Check the acceptance rubric before final output; if the intended patch "
        "cannot satisfy it, choose a smaller or better-grounded control point.\n"
        "17. Follow the Patch Quality Policy before choosing a replacement.\n\n"
        f"{deepagents_patch_quality_policy_md()}\n"
        "18. Return exactly one structured bounded replacement: path, old, new, summary, "
        "failure_mechanism, and target_rationale. The path must be one provided repository "
        "path and old must be an exact text span copied verbatim after rereading the file. "
        "Preserve existing indentation, receiver qualifiers such as `self.`, and argument "
        "names unless the edit intentionally changes that binding. The localization fields "
        "must explain the controlling failure mechanism and why this target controls it."
    )


def deepagents_repair_skill_md(*, subagents_enabled: bool = True) -> str:
    subagent_steps = (
        "14. For validation-fixture, ambiguous, or retry-after-feedback cases, ask the "
        "failure-localizer subagent to identify the controlling code path before drafting "
        "a replacement.\n"
        "15. For ambiguous, multi-file, or retry-after-feedback cases, ask the "
        "patch-reviewer subagent to review the intended replacement.\n"
        if subagents_enabled
        else "14. Subagents are disabled for this run. Perform failure localization inline "
        "before drafting the replacement.\n"
        "15. Perform patch review inline: check the replacement against the issue, "
        "retrieved source, tests, and Patch Quality Policy before final output.\n"
    )
    return (
        "---\n"
        "name: patchsmith-repair\n"
        "description: Use for PatchSmith bug repair planning when producing a bounded source "
        "patch from retrieved files, tests, or sandbox feedback.\n"
        "compatibility: deepagents>=0.6.8\n"
        "---\n\n"
        "# PatchSmith Repair Skill\n\n"
        "Use this skill when the task is to turn issue evidence, retrieved source, "
        "test output, or sandbox feedback into one bounded PatchSmith patch plan.\n\n"
        "## Workflow\n"
        "1. Read `/.patchsmith/repair-interface.md` first when present; it is the "
        "compact run interface and lists required reads, mounted source paths, "
        "routing mode, and output constraints.\n"
        "2. Keep a short todo list and update it as evidence changes.\n"
        "3. Read validation fixture files first when present; they are executable "
        "reproduction evidence, not ordinary tests.\n"
        "4. Read `/.patchsmith/source-hints.md` when present; it lists reviewed "
        "source hints and symbol-qualified functions/classes to inspect first.\n"
        "5. Read `/.patchsmith/repo-map.md` when present; it lists retrieved files, "
        "mounted/omitted status, key symbols, and definition signatures for compact "
        "routing before broad file reads.\n"
        "6. Read `/.patchsmith/repo-instructions.md` when present; it contains "
        "scoped repository instruction files such as AGENTS.md for mounted paths. "
        "Apply only constraints relevant to this run, without broadening exploration.\n"
        "7. Read `/.patchsmith/acceptance-rubric.md` when present; it is the "
        "codebase-grounded verifier checklist for the selected target, bounded old "
        "span, validation claim, and unsafe-patch exclusions.\n"
        "8. Read `/.patchsmith/retry-feedback.md` when present; it is the compact "
        "post-failure brief for the clean retry workspace.\n"
        "9. Read `/.patchsmith/target-history.md` when present; avoid listed target paths "
        "because PatchSmith rejects them unless your target_rationale names a distinct "
        "new branch or call site not tried before and cites an identifier from the old span. "
        "If Preferred Untried Source Targets are listed, choose one of those paths unless "
        "a historical target has explicit old-span evidence for a different control point. "
        "If Revived Historical Control Points are listed, treat them as eligible but still "
        "subject to that exact old-span evidence rule.\n"
        "10. Read `/.patchsmith/context-budget.md` when present; omitted files are routing "
        "evidence from retrieval and are not mounted source files in this run.\n"
        "11. Tie the fix to the failing runtime mechanism, not to incidental wording.\n"
        "12. Avoid import-only patches for behavioral failures unless the sandbox failure is "
        "ImportError, ModuleNotFoundError, or NameError and the imported name directly fixes "
        "that failure; do not add duplicate imports.\n"
        "13. Prefer source fixes over test, fixture, or report-only changes.\n"
        f"{subagent_steps}"
        "16. Check the acceptance rubric before final output; if the intended patch "
        "cannot satisfy it, choose a smaller or better-grounded control point.\n"
        "17. Follow the Patch Quality Policy before choosing a replacement.\n\n"
        f"{deepagents_patch_quality_policy_md()}\n"
        "18. Return one structured bounded replacement with path, old, new, summary, "
        "failure_mechanism, and target_rationale. The localization fields must name the "
        "controlling runtime mechanism and justify the selected file/span.\n"
        "19. Before final output, reread the selected source file and copy the `old` span "
        "exactly. Preserve receiver qualifiers such as `self.`, indentation, and argument "
        "names; do not invent variables that are not visible in the old span or nearby "
        "source.\n\n"
        "## Boundaries\n"
        "- Use only provided repository paths.\n"
        "- The old span must be exact source text from the selected file.\n"
        "- Do not write files, install dependencies, or run shell commands.\n"
        "- Keep explanations out of the final structured patch payload.\n"
    )


def deepagents_planner_prompt(
    issue_text: str,
    virtual_to_repo: dict[str, str],
    *,
    repair_interface_manifest_path: str | None = None,
    source_hint_manifest_path: str | None = None,
    repo_map_manifest_path: str | None = None,
    repo_instructions_manifest_path: str | None = None,
    acceptance_rubric_manifest_path: str | None = None,
    retry_feedback_manifest_path: str | None = None,
    target_history_manifest_path: str | None = None,
    context_budget_manifest_path: str | None = None,
    preferred_target_paths: list[str] | None = None,
    preferred_target_symbols: Mapping[str, Iterable[str]] | None = None,
    subagents_enabled: bool = True,
    budget_critical: bool = False,
) -> str:
    paths = "\n".join(
        f"- {virtual}: repository path `{repo}`" for virtual, repo in virtual_to_repo.items()
    )
    repair_interface_instruction = ""
    if repair_interface_manifest_path:
        repair_interface_instruction = (
            "\nRepair interface manifest:\n"
            f"- Read `{repair_interface_manifest_path}` first. It is the compact "
            "agent-computer interface for this run: required reads, mounted source "
            "paths, routing mode, and output constraints.\n\n"
        )
    source_hint_instruction = ""
    if source_hint_manifest_path and not budget_critical:
        source_hint_instruction = (
            "\nSource hint manifest:\n"
            f"- Read `{source_hint_manifest_path}` before choosing a patch target. "
            "It contains reviewed source hints and symbol-qualified targets from the "
            "reproduction evidence.\n\n"
        )
    repo_map_instruction = ""
    if repo_map_manifest_path:
        repo_map_instruction = (
            "\nRepo-map manifest:\n"
            f"- Read `{repo_map_manifest_path}` before target selection. It contains "
            "a compact map of retrieved repository files, mounted/omitted status, key "
            "symbols, and definition signatures. Use it to choose which mounted file "
            "to inspect deeply and to avoid selecting omitted files under a context cap.\n\n"
        )
    repo_instructions_instruction = ""
    if repo_instructions_manifest_path and not budget_critical:
        repo_instructions_instruction = (
            "\nScoped repository instructions:\n"
            f"- Read `{repo_instructions_manifest_path}` before source edits. "
            "It contains only AGENTS.md-style files scoped to mounted paths. Apply "
            "their concrete coding and validation constraints, but do not expand "
            "exploration because of generic repository guidance.\n\n"
        )
    acceptance_rubric_instruction = ""
    if acceptance_rubric_manifest_path:
        acceptance_rubric_instruction = (
            "\nAcceptance-rubric manifest:\n"
            f"- Read `{acceptance_rubric_manifest_path}` before final output. "
            "It is a codebase-grounded verifier checklist; the final bounded patch "
            "must satisfy its target, span, validation, and unsafe-patch checks.\n\n"
        )
    retry_feedback_instruction = ""
    if retry_feedback_manifest_path:
        retry_feedback_instruction = (
            "\nRetry feedback manifest:\n"
            f"- Read `{retry_feedback_manifest_path}` before planning this retry. "
            "It contains the previous failed attempt, sandbox signal, and patch "
            "diagnostics from the reverted workspace.\n\n"
        )
    target_history_instruction = ""
    if target_history_manifest_path:
        preferred_paths = [path.strip() for path in (preferred_target_paths or []) if path.strip()]
        preferred_instruction = ""
        if preferred_paths:
            preferred_instruction = (
                "\nAllowed next patch paths for this retry:\n"
                + "\n".join(f"- `{path}`" for path in preferred_paths)
                + "\nDo not set `path` to a target-history path unless "
                "`target_rationale` cites explicit old-span evidence for a different "
                "branch, cache read, dispatch site, or call path.\n"
            )
        target_history_instruction = (
            "\nTarget history manifest:\n"
            f"- Read `{target_history_manifest_path}` before choosing the patch path. "
            "It lists target paths already selected or marked ineffective. PatchSmith "
            "will reject a listed path unless target_rationale identifies a distinct "
            "new branch or call site inside that path and cites an identifier from the "
            "proposed old span. If the manifest lists Preferred Untried Source Targets, "
            "choose one of those paths for this retry unless a historical target has "
            "explicit old-span evidence for a different control point. If it lists "
            "Revived Historical Control Points, those paths are allowed only with that "
            "fresh old-span evidence.\n"
            f"{preferred_instruction}\n"
        )
    context_budget_instruction = ""
    if context_budget_manifest_path:
        context_budget_instruction = (
            "\nContext budget manifest:\n"
            f"- Read `{context_budget_manifest_path}` before final target selection. "
            "It lists retrieved files omitted from the mounted filesystem under the "
            "current context budget. Use those omitted-file summaries as routing "
            "evidence only; the final `path` must still be one of the mounted "
            "provided repository paths unless that omitted file is also listed above.\n\n"
        )
    preferred_paths = [path.strip() for path in (preferred_target_paths or []) if path.strip()]
    preferred_target_instruction = ""
    if preferred_paths and not target_history_manifest_path:
        preferred_symbol_lines = _preferred_symbol_instruction_lines(
            preferred_target_symbols,
            preferred_paths=preferred_paths,
        )
        preferred_symbol_instruction = ""
        if preferred_symbol_lines:
            preferred_symbol_instruction = (
                "\nPreferred symbols within those paths:\n"
                + "\n".join(preferred_symbol_lines)
                + "\nPatch inside the listed symbol unless the validation fixture "
                "proves an adjacent caller is the direct control point.\n"
            )
        preferred_target_instruction = (
            "\nPreferred patch paths for this constrained run:\n"
            + "\n".join(f"- `{path}`" for path in preferred_paths)
            + "\nChoose the first viable path from this ranked list unless rereading "
            "the mounted files reveals a stronger direct control point.\n"
            f"{preferred_symbol_instruction}\n"
        )
    subagent_instruction = (
        "Use subagents only when the task is ambiguous enough to need them; obvious "
        "single-control-point fixes should stay compact.\n"
        if subagents_enabled
        else "Subagents are disabled for this run. Do localization and patch review "
        "inline, and keep the route compact enough to preserve the response budget.\n"
    )
    workflow_instruction = (
        "Budget-critical mode is active. Read the repair interface first; if its "
        "Fast Patch Packet contains the preferred source/symbol and the controlling "
        "mechanism is clear, return the structured PatchPlan without creating todos "
        "or reading generic policy files. Read the mounted source only if you need "
        "to verify the exact `old` span.\n\n"
        if budget_critical
        else (
            "Plan with todos, read validation fixtures first when present, then read the "
            "relevant source files and produce one bounded replacement. Keep the plan short "
            "and avoid unrelated exploration. Before returning the structured patch plan, "
        )
    )
    return (
        "Issue:\n"
        f"{issue_text.strip()}\n\n"
        f"{repair_interface_instruction}"
        f"{source_hint_instruction}"
        f"{repo_map_instruction}"
        f"{repo_instructions_instruction}"
        f"{acceptance_rubric_instruction}"
        f"{retry_feedback_instruction}"
        f"{target_history_instruction}"
        f"{context_budget_instruction}"
        f"{preferred_target_instruction}"
        "Provided files:\n"
        f"{paths}\n\n"
        f"{workflow_instruction}"
        f"{subagent_instruction}"
        "fill failure_mechanism and target_rationale with the concrete localization "
        "claim behind the edit. Reread the chosen file immediately before final output "
        "and copy the old span exactly, including indentation, `self.` qualifiers, and "
        "argument names. Do not return an import-only patch for a behavioral failure unless "
        "the sandbox failure is ImportError, ModuleNotFoundError, or NameError and the "
        "imported name directly fixes that failure; do not add duplicate imports. The "
        "`new` span must differ from `old` with a real behavior change, not comments "
        "or whitespace only.\n\n"
        f"{deepagents_patch_quality_policy_md()}"
    )


def _preferred_symbol_instruction_lines(
    preferred_target_symbols: Mapping[str, Iterable[str]] | None,
    *,
    preferred_paths: Iterable[str],
) -> list[str]:
    if not preferred_target_symbols:
        return []
    preferred = [path.strip().lstrip("/") for path in preferred_paths if path.strip()]
    lines: list[str] = []
    for path in preferred:
        symbols = _ordered_unique_symbols(preferred_target_symbols.get(path, []))
        if symbols:
            lines.append(f"- `{path}`: " + ", ".join(f"`{symbol}`" for symbol in symbols))
    return lines


def _ordered_unique_symbols(symbols: Iterable[str]) -> list[str]:
    ordered: list[str] = []
    for symbol in symbols:
        stripped = symbol.strip()
        if stripped and stripped not in ordered:
            ordered.append(stripped)
    return ordered


def deepagents_patch_review_subagents() -> list[dict[str, str]]:
    return [
        {
            "name": "failure-localizer",
            "description": (
                "Identify the source mechanism that controls a reproduced failure "
                "before the main agent drafts a bounded patch."
            ),
            "system_prompt": (
                "You are PatchSmith's failure-localization subagent. Read the "
                "validation fixture, sandbox failure, and provided source hints. "
                "Identify the file/function that controls the observed behavior, "
                "and call out when an earlier patch target is only a symptom or "
                "incidental cache/path handling."
            ),
        },
        {
            "name": "patch-reviewer",
            "description": (
                "Review a proposed bounded text replacement against the issue, "
                "retrieved source, and tests."
            ),
            "system_prompt": (
                "You are PatchSmith's patch-review subagent. Check whether "
                "the proposed replacement is minimal, retrieval-bound, and "
                "likely to satisfy the observed tests. Call out unsafe paths, "
                "broad rewrites, broad exception swallowing, bare `except:`, "
                "catch-and-return fallbacks, function `__code__` "
                "mutation, manual `types.CodeType` rebuilds, code-object "
                "metadata rewrites such as `co_filename`, and module `__file__` "
                "metadata assignments. Reject direct source-text recompilation such as "
                "`compile(source.read_text(...), ...)` when the root issue is stale cache "
                "reuse; prefer invalidating the stale cached entry before returning it. "
                "Reject naked `importlib.invalidate_caches()` patches unless they are "
                "paired with a controlling stale-cache branch. Reject Python replacements "
                "whose old span ends on a compound statement header without including the "
                "body, unless the new span is only replacing that header with another header. "
                "Reject identical, comment-only, or whitespace-only replacement spans."
            ),
        },
    ]
