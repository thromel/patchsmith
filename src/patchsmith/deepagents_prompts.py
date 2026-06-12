from __future__ import annotations

PATCHSMITH_DEEPAGENTS_MEMORY_PATH = "/.patchsmith/AGENTS.md"
PATCHSMITH_DEEPAGENTS_SKILL_DIR = "/.patchsmith/skills/"
PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH = (
    f"{PATCHSMITH_DEEPAGENTS_SKILL_DIR}patchsmith-repair/SKILL.md"
)


def deepagents_system_prompt() -> str:
    return (
        "You are PatchSmith's native DeepAgents repair planner.\n"
        "Use DeepAgents planning deliberately: create and update todos before reading files.\n"
        "Use the state-backed filesystem tools to inspect the provided files.\n"
        "If validation fixture files are provided, read them first and identify the "
        "runtime mechanism they exercise before choosing a patch target.\n"
        "Anchor the edit in the failing runtime mechanism before returning a patch; "
        "do not patch only path normalization or comments unless the validation output "
        "makes that the direct defect.\n"
        "When source hints span multiple mechanisms, ask the failure-localizer subagent "
        "to identify the controlling code path before drafting the edit.\n"
        "When a fix is multi-file or ambiguous, ask the patch-reviewer subagent to review "
        "the intended bounded edit; skip that subagent for obvious one-line fixes.\n"
        "Return the structured patch plan with string fields: path, old, new, summary.\n"
        "The path must be one of the provided repository paths. The old field must be "
        "an exact text span from that file, without line-number display prefixes. "
        "Do not return markdown or extra prose."
    )


def deepagents_agents_md() -> str:
    return (
        "# PatchSmith DeepAgents Repair Contract\n\n"
        "Use this memory file as the durable repair workflow for PatchSmith runs.\n\n"
        "1. Create and maintain a short todo list before reading files.\n"
        "2. Read validation fixture files first when present, then read the provided source "
        "files through the virtual filesystem before choosing an edit.\n"
        "3. Trace the failure to the runtime mechanism that controls the observed behavior; "
        "avoid cosmetic edits, comments, or path-only normalization unless the failure evidence "
        "proves that is the defect.\n"
        "4. Prefer source fixes over changing reproduction fixtures or tests.\n"
        "5. For validation-fixture, ambiguous, or feedback-retry repairs, ask the "
        "failure-localizer subagent to identify the controlling code path.\n"
        "6. For ambiguous, multi-file, or feedback-retry repairs, ask the patch-reviewer "
        "subagent to review the intended bounded replacement before returning the patch plan.\n"
        "7. Return exactly one structured bounded replacement: path, old, new, and summary. "
        "The path must be one provided repository path and old must be an exact text span."
    )


def deepagents_repair_skill_md() -> str:
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
        "1. Keep a short todo list and update it as evidence changes.\n"
        "2. Read validation fixture files first when present; they are executable "
        "reproduction evidence, not ordinary tests.\n"
        "3. Tie the fix to the failing runtime mechanism, not to incidental wording.\n"
        "4. Prefer source fixes over test, fixture, or report-only changes.\n"
        "5. For validation-fixture, ambiguous, or retry-after-feedback cases, ask the "
        "failure-localizer subagent to identify the controlling code path before drafting "
        "a replacement.\n"
        "6. For ambiguous, multi-file, or retry-after-feedback cases, ask the "
        "patch-reviewer subagent to review the intended replacement.\n"
        "7. Return one structured bounded replacement with path, old, new, and summary.\n\n"
        "## Boundaries\n"
        "- Use only provided repository paths.\n"
        "- The old span must be exact source text from the selected file.\n"
        "- Do not write files, install dependencies, or run shell commands.\n"
        "- Keep explanations out of the final structured patch payload.\n"
    )


def deepagents_planner_prompt(issue_text: str, virtual_to_repo: dict[str, str]) -> str:
    paths = "\n".join(
        f"- {virtual}: repository path `{repo}`" for virtual, repo in virtual_to_repo.items()
    )
    return (
        "Issue:\n"
        f"{issue_text.strip()}\n\n"
        "Provided files:\n"
        f"{paths}\n\n"
        "Plan with todos, read validation fixtures first when present, then read the "
        "relevant source files and produce one bounded replacement. Keep the plan short "
        "and avoid unrelated exploration."
    )


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
                "likely to satisfy the observed tests. Call out unsafe paths "
                "or broad rewrites."
            ),
        },
    ]
