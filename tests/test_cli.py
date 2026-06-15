from __future__ import annotations

import json
from pathlib import Path

import pytest

from patchsmith.cli import _build_parser_and_handlers, build_parser, main
from patchsmith.portfolio.quality_gate import DEFAULT_QUALITY_GATE_TIMEOUT_SECONDS

pytestmark = pytest.mark.unit

EXPECTED_COMMANDS = {
    "demo",
    "run",
    "inspect",
    "openai-model-preflight",
    "index",
    "retrieve",
    "eval-retrieval",
    "validate-dataset",
    "eval-repair",
    "eval-scaffold",
    "eval-patch-search",
    "validate-issue-corpus",
    "preflight-issue-corpus",
    "preview-issue-corpus-context",
    "materialize-issue-corpus-tasks",
    "validate-materialized-issue-tasks",
    "check-materialized-run-readiness",
    "plan-materialized-focused-tests",
    "run-materialized-focused-tests",
    "diagnose-focused-test-runs",
    "plan-focused-test-setups",
    "check-focused-test-setup-readiness",
    "execute-focused-test-setups",
    "validate-focused-test-setups",
    "plan-public-issue-reproductions",
    "validate-public-issue-reproduction-specs",
    "discover-public-issue-failure-signals",
    "execute-public-issue-reproductions",
    "check-public-issue-repair-readiness",
    "execute-public-issue-repairs",
    "index-artifacts",
    "inspect-failures",
    "demo-readiness",
    "demo-script",
    "demo-media",
    "final-evaluation",
    "live-calibration",
    "live-calibration-plan",
    "docker-smoke",
    "environment-readiness",
    "release-hygiene",
    "launch-blockers",
    "mvp-progress",
    "delivery-audit",
    "quality-gate",
    "project-status",
    "refresh-evidence",
}


def test_every_registered_command_has_a_handler() -> None:
    parser, handlers = _build_parser_and_handlers()
    subparsers_action = next(
        action for action in parser._subparsers._group_actions if hasattr(action, "choices")
    )
    assert set(subparsers_action.choices) == set(handlers) == EXPECTED_COMMANDS
    for command, handler in handlers.items():
        assert callable(handler), command


def test_build_parser_returns_argument_parser() -> None:
    parser = build_parser()
    assert parser.prog == "patchsmith"


def test_main_without_command_prints_help_and_returns_2(capsys) -> None:
    assert main([]) == 2
    captured = capsys.readouterr()
    assert "usage: patchsmith" in captured.out


def test_main_dispatches_to_handler(monkeypatch, capsys) -> None:
    import patchsmith.cli.commands.run as run_commands

    calls: list[str] = []

    def fake_handler(args) -> int:
        calls.append(args.command)
        return 0

    monkeypatch.setitem(run_commands.register.__globals__, "_index_command", fake_handler)
    # Re-registering picks up the patched handler through the module dict.
    parser, handlers = _build_parser_and_handlers()
    args = parser.parse_args(["index", "--repo", "."])
    assert handlers["index"](args) == 0
    assert calls == ["index"]


def test_unknown_command_is_rejected() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["no-such-command"])


def test_demo_command_runs_seeded_logic_bug_and_inspect_reads_artifacts(
    tmp_path: Path,
    capsys,
) -> None:
    artifacts = tmp_path / "artifacts"

    exit_code = main(
        [
            "demo",
            "seeded-logic-bug",
            "--artifacts-dir",
            str(artifacts),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["demo"] == "seeded-logic-bug"
    assert payload["repair_verdict"] == "patch_validated"
    assert payload["claim_boundary"] == "focused_validation_only"
    assert payload["changed_files"] == ["src/simple_calc.py"]
    run_dir = Path(payload["run_dir"])
    assert (run_dir / "report.md").is_file()
    assert (run_dir / "final.diff").is_file()
    assert (run_dir / "traces.jsonl").is_file()
    assert (run_dir / "metadata.json").is_file()
    assert (run_dir / "artifact_index.md").is_file()
    assert (run_dir / "context" / "selected_files.json").is_file()

    inspect_exit_code = main(["inspect", str(run_dir), "--json"])
    inspect_payload = json.loads(capsys.readouterr().out)

    assert inspect_exit_code == 0
    assert inspect_payload["run_id"] == payload["run_id"]
    assert inspect_payload["repair_verdict"] == "patch_validated"
    assert inspect_payload["validation"] == "exit_code=0"
    assert inspect_payload["claim_boundary"] == "focused_validation_only"


def test_quality_gate_cli_defaults_use_production_timeout() -> None:
    parser = build_parser()
    quality_args = parser.parse_args(["quality-gate"])
    refresh_args = parser.parse_args(["refresh-evidence"])

    assert quality_args.timeout_seconds == DEFAULT_QUALITY_GATE_TIMEOUT_SECONDS
    assert refresh_args.quality_timeout_seconds == DEFAULT_QUALITY_GATE_TIMEOUT_SECONDS
