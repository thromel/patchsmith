"""Public issue delivery audit requirement checks."""

from __future__ import annotations

from typing import Any

from patchsmith.portfolio._helpers import _payload_int
from patchsmith.portfolio.delivery_audit_support import _delivery_item
from patchsmith.portfolio.models import DeliveryAuditItem


def _delivery_public_reproduction_plan_item(
    payload: dict[str, Any] | None,
) -> DeliveryAuditItem:
    source = (
        "artifacts/experiments/public_issue_corpus_v1/public_issue_reproduction_plan_summary.json"
    )
    if payload is None:
        return _delivery_item(
            requirement="Public issue reproduction criteria are planned.",
            status="missing",
            evidence="Public reproduction-plan summary artifact is missing.",
            source=source,
            next_action="Run `plan-public-issue-reproductions` from materialized tasks.",
        )
    blocked = _payload_int(payload, "blocked_tasks")
    warning = _payload_int(payload, "warning_tasks")
    planned = _payload_int(payload, "planned_tasks")
    manual_specs = _payload_int(payload, "manual_spec_required_tasks")
    commands = _payload_int(payload, "command_count")
    if blocked:
        status = "blocked"
        next_action = "Resolve blocked reproduction-plan prerequisites."
    elif warning or manual_specs:
        status = "warning"
        next_action = "Encode expected failing signals before claiming issue reproduction."
    else:
        status = "passed"
        next_action = "Execute reproduction commands and save failing evidence."
    return _delivery_item(
        requirement="Public issue reproduction criteria are planned.",
        status=status,
        evidence=(
            f"planned_tasks={planned}, warning_tasks={warning}, blocked_tasks={blocked}, "
            f"manual_spec_required_tasks={manual_specs}, command_count={commands}"
        ),
        source=source,
        next_action=next_action,
    )


def _delivery_public_failure_signal_discovery_item(
    payload: dict[str, Any] | None,
) -> DeliveryAuditItem:
    source = (
        "artifacts/experiments/public_issue_corpus_v1/"
        "public_issue_failure_signal_discovery_summary.json"
    )
    if payload is None:
        return _delivery_item(
            requirement="Public issue failure-signal discovery is available.",
            status="missing",
            evidence="Public failure-signal discovery summary artifact is missing.",
            source=source,
            next_action=(
                "Run `discover-public-issue-failure-signals` after reproduction planning."
            ),
        )
    dry_run = _payload_int(payload, "dry_run_tasks")
    attempted = _payload_int(payload, "attempted_tasks")
    observed = _payload_int(payload, "observed_failure_tasks")
    passed = _payload_int(payload, "passed_tasks")
    timed_out = _payload_int(payload, "timed_out_tasks")
    blocked = _payload_int(payload, "blocked_tasks")
    candidate_signals = _payload_int(payload, "candidate_signal_tasks")
    if timed_out or blocked:
        status = "blocked"
        next_action = "Resolve discovery blockers or inspect timed-out command logs."
    elif candidate_signals:
        status = "passed"
        next_action = "Review candidate signals and copy exact issue-specific lines into specs."
    else:
        status = "warning"
        next_action = (
            "Execute discovery or author a more specific reproduction command to obtain "
            "failure-signal candidates."
        )
    return _delivery_item(
        requirement="Public issue failure-signal discovery is available.",
        status=status,
        evidence=(
            f"dry_run_tasks={dry_run}, attempted_tasks={attempted}, "
            f"observed_failure_tasks={observed}, passed_tasks={passed}, "
            f"blocked_tasks={blocked}, candidate_signal_tasks={candidate_signals}"
        ),
        source=source,
        next_action=next_action,
    )


def _delivery_public_reproduction_spec_validation_item(
    payload: dict[str, Any] | None,
) -> DeliveryAuditItem:
    source = (
        "artifacts/experiments/public_issue_corpus_v1/"
        "public_issue_reproduction_spec_validation_summary.json"
    )
    if payload is None:
        return _delivery_item(
            requirement="Public issue reproduction specs are validated.",
            status="missing",
            evidence="Public reproduction-spec validation summary artifact is missing.",
            source=source,
            next_action=(
                "Run `validate-public-issue-reproduction-specs` after reproduction planning."
            ),
        )
    ready = _payload_int(payload, "ready_tasks")
    warning = _payload_int(payload, "warning_tasks")
    blocked = _payload_int(payload, "blocked_tasks")
    missing_specs = _payload_int(payload, "missing_spec_tasks")
    empty_signals = _payload_int(payload, "empty_signal_tasks")
    policy_blocked = _payload_int(payload, "policy_blocked_tasks")
    extra_specs = _payload_int(payload, "extra_spec_tasks")
    if blocked or missing_specs or empty_signals or policy_blocked or extra_specs:
        status = "blocked"
        next_action = (
            "Fill reviewed expected failure signals and resolve spec validation blockers "
            "before reproduction execution."
        )
    elif warning:
        status = "warning"
        next_action = "Review warnings before executing reproduction commands."
    else:
        status = "passed"
        next_action = "Use validated specs to regenerate the reproduction plan."
    return _delivery_item(
        requirement="Public issue reproduction specs are validated.",
        status=status,
        evidence=(
            f"ready_tasks={ready}, warning_tasks={warning}, blocked_tasks={blocked}, "
            f"missing_spec_tasks={missing_specs}, empty_signal_tasks={empty_signals}, "
            f"policy_blocked_tasks={policy_blocked}, extra_spec_tasks={extra_specs}"
        ),
        source=source,
        next_action=next_action,
    )


def _delivery_public_reproduction_execution_item(
    payload: dict[str, Any] | None,
) -> DeliveryAuditItem:
    source = (
        "artifacts/experiments/public_issue_corpus_v1/"
        "public_issue_reproduction_execution_summary.json"
    )
    if payload is None:
        return _delivery_item(
            requirement="Public issue reproduction execution is safely gated.",
            status="missing",
            evidence="Public reproduction-execution summary artifact is missing.",
            source=source,
            next_action="Run `execute-public-issue-reproductions` after reproduction planning.",
        )
    reproduced = _payload_int(payload, "reproduced_tasks")
    dry_run = _payload_int(payload, "dry_run_tasks")
    attempted = _payload_int(payload, "attempted_tasks")
    blocked = _payload_int(payload, "blocked_tasks")
    manual_specs = _payload_int(payload, "manual_spec_required_tasks")
    failed = _payload_int(payload, "failed_tasks")
    timed_out = _payload_int(payload, "timed_out_tasks")
    not_reproduced = _payload_int(payload, "not_reproduced_tasks")
    if failed or timed_out:
        status = "blocked"
        next_action = "Inspect reproduction logs before using public issue repair evidence."
    elif reproduced:
        status = "passed"
        next_action = "Use saved failing logs as pre-repair reproduction evidence."
    elif dry_run or (blocked and blocked == manual_specs):
        status = "warning"
        next_action = "Execute only after expected failing signals are encoded and reviewed."
    elif blocked:
        status = "blocked"
        next_action = "Resolve reproduction execution blockers."
    elif attempted and not_reproduced:
        status = "warning"
        next_action = (
            "Confirm whether selected public issues are already fixed or adjust reproductions."
        )
    else:
        status = "warning"
        next_action = "Run reproduction execution after reviewing planned commands."
    return _delivery_item(
        requirement="Public issue reproduction execution is safely gated.",
        status=status,
        evidence=(
            f"reproduced_tasks={reproduced}, dry_run_tasks={dry_run}, "
            f"attempted_tasks={attempted}, blocked_tasks={blocked}, "
            f"manual_spec_required_tasks={manual_specs}, failed_tasks={failed}, "
            f"timed_out_tasks={timed_out}"
        ),
        source=source,
        next_action=next_action,
    )


def _delivery_public_repair_readiness_item(
    payload: dict[str, Any] | None,
) -> DeliveryAuditItem:
    source = (
        "artifacts/experiments/public_issue_corpus_v1/public_issue_repair_readiness_summary.json"
    )
    if payload is None:
        return _delivery_item(
            requirement="Public issue repair attempts are readiness-gated.",
            status="missing",
            evidence="Public repair-readiness summary artifact is missing.",
            source=source,
            next_action="Run `check-public-issue-repair-readiness` after setup validation.",
        )
    blocked = _payload_int(payload, "blocked_tasks")
    warning = _payload_int(payload, "warning_tasks")
    ready = _payload_int(payload, "ready_tasks")
    repair_commands = _payload_int(payload, "repair_command_tasks")
    missing_reproduction = _payload_int(payload, "missing_reproduction_tasks")
    if blocked:
        status = "blocked"
        next_action = "Resolve blocked public repair-readiness prerequisites."
    elif warning:
        status = "warning"
        next_action = (
            "Review warning-class setup and sandbox caveats before claiming public repair quality."
            if missing_reproduction == 0
            else "Capture failing reproduction evidence before claiming public repair quality."
        )
    else:
        status = "passed"
        next_action = "Run bounded public issue repair attempts and save run artifacts."
    return _delivery_item(
        requirement="Public issue repair attempts are readiness-gated.",
        status=status,
        evidence=(
            f"ready_tasks={ready}, warning_tasks={warning}, blocked_tasks={blocked}, "
            f"repair_command_tasks={repair_commands}, "
            f"missing_reproduction_tasks={missing_reproduction}"
        ),
        source=source,
        next_action=next_action,
    )


def _delivery_public_repair_attempt_item(
    payload: dict[str, Any] | None,
) -> DeliveryAuditItem:
    source = "artifacts/experiments/public_issue_corpus_v1/public_issue_repair_attempt_summary.json"
    if payload is None:
        return _delivery_item(
            requirement="Public issue repair attempts are safely gated.",
            status="missing",
            evidence="Public repair-attempt summary artifact is missing.",
            source=source,
            next_action="Run `execute-public-issue-repairs` after repair readiness.",
        )
    validated = _payload_int(payload, "validated_tasks")
    attempted = _payload_int(payload, "attempted_tasks")
    blocked = _payload_int(payload, "blocked_tasks")
    failed = _payload_int(payload, "failed_tasks")
    dry_run = _payload_int(payload, "dry_run_tasks")
    reproduced_inputs = _payload_int(payload, "reproduced_input_tasks")
    if failed:
        status = "blocked"
        next_action = "Inspect failed public repair run artifacts."
    elif validated:
        status = "passed"
        next_action = "Review final diffs and broaden validation before claims."
    elif blocked and not reproduced_inputs:
        status = "warning"
        next_action = "Capture reproduced failing evidence before executing repairs."
    elif dry_run:
        status = "warning"
        next_action = "Use --execute only after reviewing dry-run evidence."
    elif blocked:
        status = "blocked"
        next_action = "Resolve repair-attempt blockers before execution."
    elif attempted:
        status = "warning"
        next_action = "Review attempted repair artifacts."
    else:
        status = "warning"
        next_action = "Run repair-attempt dry-run after readiness is available."
    return _delivery_item(
        requirement="Public issue repair attempts are safely gated.",
        status=status,
        evidence=(
            f"validated_tasks={validated}, attempted_tasks={attempted}, "
            f"blocked_tasks={blocked}, failed_tasks={failed}, "
            f"dry_run_tasks={dry_run}, reproduced_input_tasks={reproduced_inputs}"
        ),
        source=source,
        next_action=next_action,
    )
