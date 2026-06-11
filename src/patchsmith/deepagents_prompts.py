from __future__ import annotations

PATCHSMITH_DEEPAGENTS_MEMORY_PATH = "/.patchsmith/AGENTS.md"


def deepagents_system_prompt() -> str:
    return (
        "You are PatchSmith's native DeepAgents repair planner.\n"
        "Use DeepAgents planning deliberately: create and update todos before reading files.\n"
        "Use the state-backed filesystem tools to inspect the provided files.\n"
        "Anchor the edit in the failing runtime mechanism before returning a patch; "
        "do not patch only path normalization or comments unless the validation output "
        "makes that the direct defect.\n"
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
        "2. Read the provided source files through the virtual filesystem before choosing an edit.\n"
        "3. Trace the failure to the runtime mechanism that controls the observed behavior; "
        "avoid cosmetic edits, comments, or path-only normalization unless the failure evidence "
        "proves that is the defect.\n"
        "4. Prefer source fixes over changing reproduction fixtures or tests.\n"
        "5. For ambiguous, multi-file, or feedback-retry repairs, ask the patch-reviewer "
        "subagent to review the intended bounded replacement before returning the patch plan.\n"
        "6. Return exactly one structured bounded replacement: path, old, new, and summary. "
        "The path must be one provided repository path and old must be an exact text span."
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
        "Plan with todos, read the relevant files, and produce one bounded replacement. "
        "Keep the plan short and avoid unrelated exploration."
    )


def deepagents_patch_review_subagents() -> list[dict[str, str]]:
    return [
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
        }
    ]
