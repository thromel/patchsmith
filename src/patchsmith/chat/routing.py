from __future__ import annotations

import re


def parse_slash_command(raw: str) -> tuple[str, str]:
    command_text = raw[1:].strip()
    if not command_text:
        return "help", ""
    command, _, argument = command_text.partition(" ")
    return command.strip().lower(), argument.strip()


def route_natural_command(raw: str) -> str | None:
    normalized = normalized_natural_command(raw)
    exact_routes = {
        "help": "/help",
        "show help": "/help",
        "what can you do": "/help",
        "exit": "/exit",
        "quit": "/exit",
        "bye": "/exit",
        "goodbye": "/exit",
        "status": "/status",
        "show status": "/status",
        "session status": "/status",
        "where are we": "/status",
        "mode": "/mode",
        "show mode": "/mode",
        "approve plan": "/run",
        "approve planned task": "/run",
        "go ahead": "/run",
        "run it": "/run",
        "execute plan": "/run",
        "execute planned task": "/run",
        "cancel plan": "/cancel plan",
        "cancel planned task": "/cancel plan",
        "discard plan": "/cancel plan",
        "reject plan": "/cancel plan",
        "do not run it": "/cancel plan",
        "don't run it": "/cancel plan",
        "never mind": "/cancel plan",
        "nevermind": "/cancel plan",
        "act mode": "/mode act",
        "run mode": "/mode act",
        "edit mode": "/mode act",
        "exit plan mode": "/mode act",
        "leave plan mode": "/mode act",
        "plan mode": "/mode plan",
        "planning mode": "/mode plan",
        "enter plan mode": "/mode plan",
        "switch to plan mode": "/mode plan",
        "what next": "/next",
        "next": "/next",
        "recommend next step": "/next",
        "recommend next action": "/next",
        "what should i do next": "/next",
        "what should we do next": "/next",
        "show history": "/history",
        "history": "/history",
        "show timeline": "/timeline",
        "timeline": "/timeline",
        "show metrics": "/metrics",
        "metrics": "/metrics",
        "show cost": "/cost",
        "cost": "/cost",
        "show evidence": "/evidence",
        "evidence": "/evidence",
        "show trace": "/trace",
        "trace": "/trace",
        "show diff": "/diff show",
        "diff": "/diff",
        "diff stat": "/diff stat",
        "review diff": "/diff review",
        "diff review": "/diff review",
        "apply check": "/apply check",
        "check apply": "/apply check",
        "dry run apply": "/apply check",
        "dry-run apply": "/apply check",
        "apply it": "/apply",
        "apply patch": "/apply",
        "apply the patch": "/apply",
        "undo": "/rewind",
        "undo patch": "/rewind",
        "rewind": "/rewind",
        "show context": "/context show",
        "context": "/context show",
        "show plan": "/plan show",
        "plan": "/plan show",
        "show feedback": "/feedback show",
        "feedback": "/feedback show",
        "show permissions": "/permissions show",
        "permissions": "/permissions show",
        "show agents": "/agents",
        "show profiles": "/agents",
        "show commands": "/commands",
        "show hooks": "/hooks",
        "show instructions": "/instructions show",
        "memory": "/memory show",
        "show memory": "/memory show",
        "project memory": "/memory show",
        "show project memory": "/memory show",
        "reload memory": "/memory reload",
        "clear memory": "/memory clear",
    }
    if normalized in exact_routes:
        return exact_routes[normalized]
    memory_note = memory_note_from_natural_command(raw)
    if memory_note:
        return f"/memory add {memory_note}"
    if normalized.startswith("preflight "):
        task = raw.strip()[len("preflight ") :].strip()
        if task:
            return f"/preflight {task}"
    return None


def memory_note_from_natural_command(raw: str) -> str | None:
    text = raw.strip()
    lowered = text.lower()
    for prefix in (
        "remember that ",
        "remember to ",
        "remember ",
        "add memory ",
        "add project memory ",
    ):
        if lowered.startswith(prefix):
            note = text[len(prefix) :].strip()
            return note or None
    return None


def normalized_natural_command(raw: str) -> str:
    text = raw.strip().lower()
    text = re.sub(r"[?!.]+$", "", text)
    return re.sub(r"\s+", " ", text)
