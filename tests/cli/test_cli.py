from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from patchsmith.cli import _build_parser_and_handlers, build_parser, main
from patchsmith.model_preflight import ModelPreflightResult
from patchsmith.portfolio.quality_gate import DEFAULT_QUALITY_GATE_TIMEOUT_SECONDS

pytestmark = pytest.mark.unit

EXPECTED_COMMANDS = {
    "agent",
    "chat",
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
    "eval-complex",
    "eval-complex-suite",
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
    "release-gate",
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
    import patchsmith.cli.commands.repository as repository_commands

    calls: list[str] = []

    def fake_handler(args) -> int:
        calls.append(args.command)
        return 0

    monkeypatch.setitem(repository_commands.register.__globals__, "_index_command", fake_handler)
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


def test_agent_command_defaults_to_deepagents_current_repo(monkeypatch, capsys) -> None:
    import patchsmith.cli.commands.agent as agent_commands

    captured: dict[str, object] = {}

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            captured["artifacts_dir"] = artifacts_dir

        def run(self, request):
            captured["request"] = request
            return SimpleNamespace(
                run_id="run-1",
                status="completed",
                report_path=Path("artifacts/runs/run-1/report.md"),
                trace_path=Path("artifacts/runs/run-1/traces.jsonl"),
                final_diff_path=Path("artifacts/runs/run-1/final.diff"),
                test_result=SimpleNamespace(exit_code=0),
                model_usage={
                    "call_count": 1,
                    "response_count": 3,
                    "total_tokens": 123,
                    "estimated_cost_usd": 0.004,
                },
                retrieved_context=[],
            )

    monkeypatch.setattr(agent_commands, "RepairRunner", FakeRepairRunner)

    exit_code = main(
        [
            "agent",
            "Fix the failing parser test",
            "--test-command",
            "pytest tests/test_parser.py -q",
            "--context-path",
            "src/parser.py#parse",
            "--deepagents-max-context-files",
            "4",
            "--skip-model-preflight",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["runtime"] == "deepagents"
    assert payload["planner"] == "deepagents"
    assert payload["test_exit_code"] == 0
    assert payload["model_response_count"] == 3
    assert payload["model_total_tokens"] == 123
    assert payload["estimated_cost_usd"] == 0.004
    assert captured["artifacts_dir"] == Path("artifacts")
    request = captured["request"]
    assert request.repo == "."
    assert request.issue_text == "Fix the failing parser test"
    assert request.test_command == "pytest tests/test_parser.py -q"
    assert request.runtime == "deepagents"
    assert request.planner == "deepagents"
    assert request.max_retries == 1
    assert request.context_provider == "native_hybrid"
    assert request.context_paths == ("src/parser.py#parse",)
    assert request.runtime_config == {
        "subagent_mode": "auto",
        "max_context_files": 4,
        "resource_budget": {
            "max_model_responses": 12,
            "max_model_tokens": 200000,
        },
    }


def test_agent_command_applies_project_agent_profile(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    import patchsmith.cli.commands.agent as agent_commands

    profile_dir = tmp_path / ".patchsmith" / "agents"
    profile_dir.mkdir(parents=True)
    profile_instructions = "Inspect validation evidence first."
    (profile_dir / "verifier.md").write_text(
        "---\n"
        "description: Verification-focused repair mode\n"
        "model: gpt-5-mini\n"
        "subagents: inline\n"
        "max_context_files: 2\n"
        "max_model_responses: 4\n"
        "max_model_tokens: 90000\n"
        "test_command: pytest tests/test_target.py -q\n"
        "context_paths: src/target.py#fix\n"
        "---\n"
        f"{profile_instructions}\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            captured["artifacts_dir"] = artifacts_dir

        def run(self, request):
            captured["request"] = request
            return SimpleNamespace(
                run_id="run-profile-cli",
                status="completed",
                report_path=Path("artifacts/runs/run-profile-cli/report.md"),
                trace_path=Path("artifacts/runs/run-profile-cli/traces.jsonl"),
                final_diff_path=Path("artifacts/runs/run-profile-cli/final.diff"),
                test_result=SimpleNamespace(exit_code=0),
                retrieved_context=[],
            )

    monkeypatch.setattr(agent_commands, "RepairRunner", FakeRepairRunner)

    exit_code = main(
        [
            "agent",
            "Fix the target",
            "--repo",
            str(tmp_path),
            "--agent-profile",
            "verifier",
            "--skip-model-preflight",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["run_id"] == "run-profile-cli"
    request = captured["request"]
    assert "PatchSmith agent profile /verifier" in request.issue_text
    assert profile_instructions in request.issue_text
    assert "Task:\nFix the target" in request.issue_text
    assert request.test_command == "pytest tests/test_target.py -q"
    assert request.context_paths == ("src/target.py#fix",)
    assert request.runtime_config == {
        "subagent_mode": "inline",
        "model": "gpt-5-mini",
        "max_context_files": 2,
        "resource_budget": {
            "max_model_responses": 4,
            "max_model_tokens": 90000,
        },
        "agent_profile": {
            "name": "verifier",
            "path": str(profile_dir / "verifier.md"),
            "description": "Verification-focused repair mode",
            "instruction_chars": len(profile_instructions),
        },
    }


def test_agent_command_loads_project_instructions_into_request(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    import patchsmith.cli.commands.agent as agent_commands

    (tmp_path / "AGENTS.md").write_text(
        "## Repository expectations\n- Preserve public API behavior.\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            captured["artifacts_dir"] = artifacts_dir

        def run(self, request):
            captured["request"] = request
            return SimpleNamespace(
                run_id="run-instructions-cli",
                status="completed",
                report_path=Path("artifacts/runs/run-instructions-cli/report.md"),
                trace_path=Path("artifacts/runs/run-instructions-cli/traces.jsonl"),
                final_diff_path=Path("artifacts/runs/run-instructions-cli/final.diff"),
                test_result=SimpleNamespace(exit_code=0),
                retrieved_context=[],
            )

    monkeypatch.setattr(agent_commands, "RepairRunner", FakeRepairRunner)

    exit_code = main(
        [
            "agent",
            "Fix the API regression",
            "--repo",
            str(tmp_path),
            "--skip-model-preflight",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["run_id"] == "run-instructions-cli"
    request = captured["request"]
    assert "PatchSmith project instructions" in request.issue_text
    assert "Preserve public API behavior." in request.issue_text
    assert "Task:\nFix the API regression" in request.issue_text
    assert request.runtime_config["project_instructions"]["files"] == ["AGENTS.md"]
    assert request.runtime_config["project_instructions"]["instruction_chars"] > 0


def test_agent_preflight_reports_config_without_running(
    monkeypatch,
    capsys,
) -> None:
    import patchsmith.cli.commands.agent as agent_commands

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            raise AssertionError("preflight should not start the runner")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(agent_commands, "RepairRunner", FakeRepairRunner)

    exit_code = main(
        [
            "agent",
            "Fix the failing parser test",
            "--context-path",
            "src/parser.py#parse",
            "--deepagents-max-context-files",
            "4",
            "--preflight",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["runtime"] == "deepagents"
    assert payload["planner"] == "deepagents"
    assert payload["context_provider"] == "native_hybrid"
    assert payload["context_paths"] == ["src/parser.py#parse"]
    assert payload["runtime_config"] == {
        "subagent_mode": "auto",
        "max_context_files": 4,
        "resource_budget": {
            "max_model_responses": 12,
            "max_model_tokens": 200000,
        },
    }
    assert {check["name"]: check["status"] for check in payload["checks"]} == {
        "prompt": "passed",
        "deepagents_dependency": "passed",
        "openai_api_key": "passed",
        "model_selection": "passed",
        "resource_budget": "passed",
        "deepagents_token_headroom": "passed",
        "reasoning_token_headroom": "passed",
        "apply_target": "skipped",
    }
    deepagents_headroom_check = next(
        check
        for check in payload["checks"]
        if check["name"] == "deepagents_token_headroom"
    )
    assert deepagents_headroom_check["max_model_tokens"] == 200000
    assert deepagents_headroom_check["recommended_min_tokens"] == 90000
    headroom_check = next(
        check
        for check in payload["checks"]
        if check["name"] == "reasoning_token_headroom"
    )
    assert headroom_check["reasoning_model"] is True
    assert headroom_check["max_model_tokens"] == 200000
    assert headroom_check["recommended_min_tokens"] == 25000


def test_agent_preflight_warns_for_low_reasoning_token_headroom(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    exit_code = main(
        [
            "agent",
            "Fix the failing parser test",
            "--deepagents-model",
            "gpt-5.4-nano",
            "--max-model-tokens",
            "12000",
            "--preflight",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    headroom_check = next(
        check
        for check in payload["checks"]
        if check["name"] == "reasoning_token_headroom"
    )
    assert headroom_check["status"] == "passed"
    assert headroom_check["severity"] == "warning"
    assert headroom_check["model"] == "gpt-5.4-nano"
    assert headroom_check["max_model_tokens"] == 12000
    assert "below recommended initial headroom" in headroom_check["message"]


def test_agent_preflight_skips_headroom_for_non_reasoning_model(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    exit_code = main(
        [
            "agent",
            "Fix the failing parser test",
            "--deepagents-model",
            "gpt-4.1-mini",
            "--max-model-tokens",
            "12000",
            "--preflight",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    deepagents_headroom_check = next(
        check
        for check in payload["checks"]
        if check["name"] == "deepagents_token_headroom"
    )
    assert deepagents_headroom_check["status"] == "passed"
    assert deepagents_headroom_check["severity"] == "warning"
    assert deepagents_headroom_check["max_model_tokens"] == 12000
    assert "below recommended initial headroom" in deepagents_headroom_check["message"]
    headroom_check = next(
        check
        for check in payload["checks"]
        if check["name"] == "reasoning_token_headroom"
    )
    assert headroom_check["status"] == "skipped"
    assert headroom_check["reasoning_model"] is False


def test_agent_preflight_blocks_when_openai_key_is_missing(monkeypatch, capsys) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    exit_code = main(["agent", "fix parser", "--preflight", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["status"] == "blocked"
    openai_check = next(
        check for check in payload["checks"] if check["name"] == "openai_api_key"
    )
    assert openai_check["status"] == "blocked"
    assert "not set" in openai_check["message"]


def test_agent_command_blocks_failed_model_preflight_before_runner(
    monkeypatch,
    capsys,
) -> None:
    import patchsmith.cli.commands.agent as agent_commands

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            raise AssertionError("runner must not start after failed model preflight")

    monkeypatch.setattr(agent_commands, "RepairRunner", FakeRepairRunner)
    monkeypatch.setattr(
        agent_commands,
        "openai_model_preflight_from_env",
        lambda *, model=None: ModelPreflightResult(
            provider="openai_models",
            model=model or "gpt-5.4-mini",
            endpoint="https://api.openai.com/v1/models",
            status="http_error",
            available=False,
            error="OpenAI Models API error 401: invalid or unauthorized API key.",
        ),
    )

    exit_code = main(["agent", "fix parser", "--deepagents-model", "gpt-5.4-mini"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "model preflight blocked: http_error (gpt-5.4-mini)" in captured.err
    assert "invalid or unauthorized API key" in captured.err


def test_agent_command_can_apply_generated_diff(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    import patchsmith.cli.commands.agent as agent_commands

    repo = _git_repo(tmp_path / "repo")
    artifacts = tmp_path / "artifacts"
    diff_path = artifacts / "runs" / "run-apply" / "final.diff"
    diff_path.parent.mkdir(parents=True)
    diff_path.write_text(
        "diff --git a/app.py b/app.py\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1 +1 @@\n"
        "-value = 1\n"
        "+value = 2\n",
        encoding="utf-8",
    )

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            assert request.repo == str(repo)
            return SimpleNamespace(
                run_id="run-apply",
                status="completed",
                report_path=diff_path.parent / "report.md",
                trace_path=diff_path.parent / "traces.jsonl",
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                retrieved_context=[],
            )

    monkeypatch.setattr(agent_commands, "RepairRunner", FakeRepairRunner)

    exit_code = main(
        [
            "agent",
            "fix app",
            "--repo",
            str(repo),
            "--artifacts-dir",
            str(artifacts),
            "--apply",
            "--skip-model-preflight",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["apply"]["status"] == "applied"
    assert payload["apply"]["applied"] is True
    assert (repo / "app.py").read_text(encoding="utf-8") == "value = 2\n"


def test_agent_apply_rejects_dirty_repo_before_running(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    import patchsmith.cli.commands.agent as agent_commands

    repo = _git_repo(tmp_path / "repo")
    (repo / "app.py").write_text("value = 3\n", encoding="utf-8")

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            raise AssertionError("runner should not start when apply preflight fails")

    monkeypatch.setattr(agent_commands, "RepairRunner", FakeRepairRunner)

    exit_code = main(["agent", "fix app", "--repo", str(repo), "--apply"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "uncommitted changes" in captured.err


def test_agent_command_rejects_prompt_and_issue_file(tmp_path, capsys) -> None:
    issue_file = tmp_path / "issue.md"
    issue_file.write_text("fix me", encoding="utf-8")

    assert main(["agent", "fix this too", "--issue-file", str(issue_file)]) == 2
    captured = capsys.readouterr()
    assert "pass either a prompt or --issue-file" in captured.err


def test_chat_command_starts_interactive_session(monkeypatch) -> None:
    import patchsmith.cli.commands.chat as chat_commands

    captured: dict[str, object] = {}

    def fake_run_chat_session(
        *,
        config,
        initial_prompt: str,
        input_stream,
        output_stream,
        runner_cls,
        model_preflight_checker=None,
        session_id=None,
        resume: bool = False,
    ) -> int:
        captured["config"] = config
        captured["initial_prompt"] = initial_prompt
        captured["runner_cls"] = runner_cls
        captured["model_preflight_checker"] = model_preflight_checker
        captured["session_id"] = session_id
        captured["resume"] = resume
        return 0

    monkeypatch.setattr(chat_commands, "run_chat_session", fake_run_chat_session)

    exit_code = main(
        [
            "chat",
            "Fix parser",
            "--context-path",
            "src/parser.py#parse",
            "--deepagents-max-context-files",
            "4",
            "--deepagents-model",
            "gpt-5-mini",
        ]
    )

    assert exit_code == 0
    assert captured["initial_prompt"] == "Fix parser"
    config = captured["config"]
    assert config.context_paths == ("src/parser.py#parse",)
    assert config.deepagents_max_context_files == 4
    assert config.deepagents_model == "gpt-5-mini"
    assert captured["session_id"] is None
    assert captured["resume"] is False
    assert captured["runner_cls"] is chat_commands.RepairRunner
    assert captured["model_preflight_checker"] is chat_commands._openai_model_preflight_for_config


def test_chat_command_resumes_named_session(monkeypatch) -> None:
    import patchsmith.cli.commands.chat as chat_commands

    captured: dict[str, object] = {}

    def fake_run_chat_session(
        *,
        config,
        initial_prompt: str,
        input_stream,
        output_stream,
        runner_cls,
        model_preflight_checker=None,
        session_id=None,
        resume: bool = False,
    ) -> int:
        captured["config"] = config
        captured["initial_prompt"] = initial_prompt
        captured["model_preflight_checker"] = model_preflight_checker
        captured["session_id"] = session_id
        captured["resume"] = resume
        return 0

    monkeypatch.setattr(chat_commands, "run_chat_session", fake_run_chat_session)

    exit_code = main(["chat", "--repo", ".", "--resume", "session-123"])

    assert exit_code == 0
    assert captured["initial_prompt"] == ""
    assert captured["session_id"] == "session-123"
    assert captured["resume"] is True
    assert captured["model_preflight_checker"] is chat_commands._openai_model_preflight_for_config
    assert captured["config"].repo == "."


def test_chat_command_lists_saved_sessions(tmp_path: Path, capsys) -> None:
    transcript_dir = tmp_path / "artifacts" / "chat_sessions"
    transcript_dir.mkdir(parents=True)
    (transcript_dir / "session-a.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-06-14T00:00:00+00:00",
                        "session_id": "session-a",
                        "event": "session_start",
                        "payload": {
                            "config": {
                                "repo": ".",
                                "context_paths": [],
                                "context_provider": "native_hybrid",
                                "max_model_responses": 12,
                                "max_model_tokens": 200000,
                            }
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-06-14T00:00:01+00:00",
                        "session_id": "session-a",
                        "event": "user_task",
                        "payload": {"task": "fix parser"},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "chat",
            "--artifacts-dir",
            str(tmp_path / "artifacts"),
            "--list-sessions",
        ]
    )

    assert exit_code == 0
    text = capsys.readouterr().out
    assert "Session | Updated | Tasks | Runs | Validated | Errors | Cost | Last" in text
    assert "session-a" in text
    assert "fix parser" not in text


def test_chat_command_lists_project_custom_commands(tmp_path: Path, capsys) -> None:
    command_dir = tmp_path / ".patchsmith" / "commands" / "bench"
    command_dir.mkdir(parents=True)
    (command_dir / "live.md").write_text(
        "---\n"
        "description: Run a bounded live benchmark\n"
        "argument_hint: task-id or issue slug\n"
        "---\n"
        "Plan a live benchmark for $ARGUMENTS\n",
        encoding="utf-8",
    )

    exit_code = main(["chat", "--repo", str(tmp_path), "--list-commands"])

    assert exit_code == 0
    text = capsys.readouterr().out
    assert "Project custom commands:" in text
    assert "/bench:live" in text
    assert "Run a bounded live benchmark" in text
    assert "[task-id or issue slug]" in text


def test_chat_command_lists_project_custom_commands_json(
    tmp_path: Path,
    capsys,
) -> None:
    command_dir = tmp_path / ".patchsmith" / "commands"
    command_dir.mkdir(parents=True)
    (command_dir / "review.md").write_text(
        "---\n"
        "description: >\n"
        "  Review the generated diff\n"
        "  before apply.\n"
        "argument-hint: path or run id\n"
        "---\n"
        "Review $ARGUMENTS\n",
        encoding="utf-8",
    )

    exit_code = main(["chat", "--repo", str(tmp_path), "--list-commands", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["repo"] == str(tmp_path)
    assert payload["command_root"] == ".patchsmith/commands"
    assert payload["commands"][0]["name"] == "review"
    assert payload["commands"][0]["description"] == "Review the generated diff before apply."
    assert payload["commands"][0]["argument_hint"] == "path or run id"


def test_chat_command_lists_project_hooks_json(
    tmp_path: Path,
    capsys,
) -> None:
    hook_config = tmp_path / ".patchsmith" / "hooks.json"
    hook_config.parent.mkdir(parents=True)
    hook_config.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreRun": [
                        {
                            "name": "budget-guard",
                            "matcher": "benchmark",
                            "command": "python scripts/check_budget.py",
                            "timeout": 5,
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["chat", "--repo", str(tmp_path), "--list-hooks", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["repo"] == str(tmp_path)
    assert payload["hook_config"] == ".patchsmith/hooks.json"
    assert payload["hooks"][0]["event"] == "PreRun"
    assert payload["hooks"][0]["name"] == "budget-guard"
    assert payload["hooks"][0]["matcher"] == "benchmark"
    assert payload["hooks"][0]["timeout_seconds"] == 5.0


def test_chat_command_lists_project_agent_profiles_json(
    tmp_path: Path,
    capsys,
) -> None:
    profile_dir = tmp_path / ".patchsmith" / "agents" / "review"
    profile_dir.mkdir(parents=True)
    (profile_dir / "security.md").write_text(
        "---\n"
        "description: Review security-sensitive patches\n"
        "model: gpt-5-mini\n"
        "max_model_responses: 5\n"
        "context_paths: |\n"
        "  - src/auth.py#login\n"
        "---\n"
        "Check authorization boundaries before editing.\n",
        encoding="utf-8",
    )

    exit_code = main(["chat", "--repo", str(tmp_path), "--list-agents", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["repo"] == str(tmp_path)
    assert payload["profile_root"] == ".patchsmith/agents"
    assert payload["profiles"][0]["name"] == "review:security"
    assert payload["profiles"][0]["description"] == "Review security-sensitive patches"
    assert payload["profiles"][0]["model"] == "gpt-5-mini"
    assert payload["profiles"][0]["max_model_responses"] == 5
    assert payload["profiles"][0]["context_paths"] == ["src/auth.py#login"]


def test_chat_command_lists_project_instructions_json(
    tmp_path: Path,
    capsys,
) -> None:
    (tmp_path / "AGENTS.md").write_text(
        "## Setup\n- Run pytest before release.\n",
        encoding="utf-8",
    )
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "agent.md").write_text(
        "Prefer bounded source edits.\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "chat",
            "--repo",
            str(tmp_path),
            "--instruction-path",
            "docs/agent.md",
            "--list-instructions",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    files = payload["instruction_files"]["files"]
    assert [file["repo_relative_path"] for file in files] == [
        "AGENTS.md",
        "docs/agent.md",
    ]
    assert files[0]["source"] == "root"
    assert files[1]["source"] == "explicit"
    assert payload["instruction_files"]["content_chars"] > 0


def test_chat_command_can_disable_default_project_instructions(
    tmp_path: Path,
    capsys,
) -> None:
    (tmp_path / "AGENTS.md").write_text(
        "## Setup\n- Run pytest before release.\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "chat",
            "--repo",
            str(tmp_path),
            "--no-agent-instructions",
            "--list-instructions",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["instruction_files"]["files"] == []


def test_agent_interactive_can_list_project_hooks_json(
    tmp_path: Path,
    capsys,
) -> None:
    hook_config = tmp_path / ".patchsmith" / "hooks.json"
    hook_config.parent.mkdir(parents=True)
    hook_config.write_text(
        json.dumps({"hooks": {"PreApply": ["python scripts/check_diff.py"]}}),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "agent",
            "--interactive",
            "--repo",
            str(tmp_path),
            "--list-hooks",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["hooks"][0]["event"] == "PreApply"
    assert payload["hooks"][0]["name"] == "preapply-1"
    assert payload["hooks"][0]["command"] == "python scripts/check_diff.py"


def test_agent_interactive_can_list_project_agent_profiles_json(
    tmp_path: Path,
    capsys,
) -> None:
    profile_dir = tmp_path / ".patchsmith" / "agents"
    profile_dir.mkdir(parents=True)
    (profile_dir / "verifier.md").write_text(
        "---\n"
        "description: Verify targeted fixes\n"
        "subagents: inline\n"
        "---\n"
        "Use the smallest validated edit.\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "agent",
            "--interactive",
            "--repo",
            str(tmp_path),
            "--list-agents",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["profiles"][0]["name"] == "verifier"
    assert payload["profiles"][0]["subagents"] == "inline"


def test_chat_command_prints_saved_session_metrics_text_and_json(
    tmp_path: Path,
    capsys,
) -> None:
    _write_session_metrics_transcript(tmp_path / "artifacts", "metric-session")

    exit_code = main(
        [
            "chat",
            "--artifacts-dir",
            str(tmp_path / "artifacts"),
            "--session-metrics",
            "metric-session",
        ]
    )

    assert exit_code == 0
    text = capsys.readouterr().out
    assert "Session metrics:" in text
    assert "- Validation rate: 100.00%" in text
    assert "- Model preflights: 1" in text
    assert "- Passed model preflights: 1" in text
    assert "- Cost per validated run: $0.010000" in text

    exit_code = main(
        [
            "chat",
            "--artifacts-dir",
            str(tmp_path / "artifacts"),
            "--session-metrics",
            "metric-session",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["session_id"] == "metric-session"
    assert payload["metrics"]["model_preflight_count"] == 1
    assert payload["metrics"]["model_preflight_passed_count"] == 1
    assert payload["metrics"]["model_preflight_blocked_count"] == 0
    assert payload["metrics"]["validation_rate"] == 1.0
    assert payload["metrics"]["cost_per_validated_run_usd"] == 0.01


def test_chat_command_prints_saved_session_next_text(
    tmp_path: Path,
    capsys,
) -> None:
    _write_session_metrics_transcript(tmp_path / "artifacts", "next-session")

    exit_code = main(
        [
            "chat",
            "--artifacts-dir",
            str(tmp_path / "artifacts"),
            "--session-next",
            "next-session",
        ]
    )

    assert exit_code == 0
    text = capsys.readouterr().out
    assert "Next recommendation:" in text
    assert "Inspect the latest validated run artifacts." in text
    assert "- Commands: /trace, /gate clean" in text


def test_chat_command_prints_saved_repeated_failure_next_json(
    tmp_path: Path,
    capsys,
) -> None:
    _write_repeated_failure_transcript(tmp_path / "artifacts", "stuck-session")

    exit_code = main(
        [
            "chat",
            "--artifacts-dir",
            str(tmp_path / "artifacts"),
            "--session-next",
            "stuck-session",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["session_id"] == "stuck-session"
    recommendation = payload["recommendation"]
    assert recommendation["action"] == "Break the repeated failure loop before another run."
    assert recommendation["commands"] == [
        "/trace",
        "/feedback add <what changed after reviewing the failure>",
        "/context add <path[#symbol]>",
    ]
    assert "repeat_count=2" in recommendation["evidence"]
    assert any(
        item.startswith("failure=no_patch_generated")
        for item in recommendation["evidence"]
    )


def test_chat_command_exports_saved_session(tmp_path: Path, capsys) -> None:
    _write_session_metrics_transcript(tmp_path / "artifacts", "export-session")
    report_path = tmp_path / "reports" / "export-session.md"

    exit_code = main(
        [
            "chat",
            "--artifacts-dir",
            str(tmp_path / "artifacts"),
            "--export-session",
            "export-session",
            "--export-path",
            str(report_path),
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["session_id"] == "export-session"
    assert payload["report_path"] == str(report_path)
    report = report_path.read_text(encoding="utf-8")
    assert "# PatchSmith Chat Session" in report
    assert "## Process Metrics" in report


def test_chat_command_gates_saved_session_metrics(tmp_path: Path, capsys) -> None:
    _write_session_metrics_transcript(tmp_path / "artifacts", "gate-session")

    exit_code = main(
        [
            "chat",
            "--artifacts-dir",
            str(tmp_path / "artifacts"),
            "--session-gate",
            "gate-session",
            "--require-validated-run",
            "--min-validation-rate",
            "1.0",
            "--max-cost-per-validated-run-usd",
            "0.02",
            "--require-diff-review",
            "--max-high-risk-diff-reviews",
            "0",
            "--require-ready-apply-check",
            "--max-run-errors",
            "0",
        ]
    )

    assert exit_code == 0
    text = capsys.readouterr().out
    assert "Session gate: passed" in text
    assert "validated_run: passed" in text
    assert "validation_rate: passed" in text
    assert "cost_per_validated_run_usd: passed" in text
    assert "diff_review_count: passed" in text
    assert "high_risk_diff_review_count: passed" in text
    assert "ready_apply_check_count: passed" in text


def test_chat_command_gates_saved_session_metrics_json_failure(
    tmp_path: Path,
    capsys,
) -> None:
    _write_session_metrics_transcript(tmp_path / "artifacts", "gate-fail-session")

    exit_code = main(
        [
            "chat",
            "--artifacts-dir",
            str(tmp_path / "artifacts"),
            "--session-gate",
            "gate-fail-session",
            "--max-cost-per-validated-run-usd",
            "0.001",
            "--json",
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["session_id"] == "gate-fail-session"
    assert payload["gate"]["status"] == "failed"
    checks = {check["name"]: check for check in payload["gate"]["checks"]}
    assert checks["cost_per_validated_run_usd"]["status"] == "failed"


def test_chat_command_rejects_invalid_session_gate_args(capsys) -> None:
    assert (
        main(
            [
                "chat",
                "--session-gate",
                "gate-session",
                "--min-validation-rate",
                "1.5",
            ]
        )
        == 2
    )
    assert "--min-validation-rate must be between 0.0 and 1.0" in capsys.readouterr().err

    assert (
        main(
            [
                "chat",
                "--session-gate",
                "gate-session",
                "--max-high-risk-diff-reviews",
                "-1",
            ]
        )
        == 2
    )
    assert (
        "--max-high-risk-diff-reviews must be non-negative"
        in capsys.readouterr().err
    )


def test_chat_command_rejects_missing_saved_session(tmp_path: Path, capsys) -> None:
    exit_code = main(
        [
            "chat",
            "--artifacts-dir",
            str(tmp_path / "artifacts"),
            "--session-metrics",
            "missing-session",
        ]
    )

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "chat session not found: missing-session" in captured.err


def test_chat_command_rejects_conflicting_offline_actions(
    tmp_path: Path,
    capsys,
) -> None:
    assert (
        main(
            [
                "chat",
                "--artifacts-dir",
                str(tmp_path / "artifacts"),
                "--list-sessions",
                "--session-metrics",
                "metric-session",
            ]
        )
        == 2
    )
    assert "pass only one of" in capsys.readouterr().err


def test_chat_command_rejects_export_path_without_export(capsys) -> None:
    assert main(["chat", "--export-path", "session.md"]) == 2
    assert "--export-path requires --export-session" in capsys.readouterr().err


def test_chat_command_reads_script_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import patchsmith.cli.commands.chat as chat_commands

    script_path = tmp_path / "session.patchsmith"
    script_path.write_text("/status\n/exit\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run_chat_session(
        *,
        config,
        initial_prompt: str,
        input_stream,
        output_stream,
        runner_cls,
        model_preflight_checker=None,
        session_id=None,
        resume: bool = False,
    ) -> int:
        captured["config"] = config
        captured["initial_prompt"] = initial_prompt
        captured["script"] = input_stream.read()
        captured["session_id"] = session_id
        captured["resume"] = resume
        return 0

    monkeypatch.setattr(chat_commands, "run_chat_session", fake_run_chat_session)

    exit_code = main(["chat", "--repo", ".", "--script", str(script_path)])

    assert exit_code == 0
    assert captured["initial_prompt"] == ""
    assert captured["script"] == "/status\n/exit\n"
    assert captured["session_id"] is None
    assert captured["resume"] is False


def test_chat_command_rejects_missing_script(tmp_path: Path, capsys) -> None:
    exit_code = main(["chat", "--script", str(tmp_path / "missing.patchsmith")])

    assert exit_code == 2
    assert "chat script not found" in capsys.readouterr().err


def test_agent_interactive_starts_chat_without_prompt(monkeypatch) -> None:
    import patchsmith.cli.commands.chat as chat_commands

    captured: dict[str, object] = {}

    def fake_run_chat_session(
        *,
        config,
        initial_prompt: str,
        input_stream,
        output_stream,
        runner_cls,
        model_preflight_checker=None,
        session_id=None,
        resume: bool = False,
    ) -> int:
        captured["config"] = config
        captured["initial_prompt"] = initial_prompt
        captured["session_id"] = session_id
        captured["resume"] = resume
        return 0

    monkeypatch.setattr(chat_commands, "run_chat_session", fake_run_chat_session)

    exit_code = main(["agent", "--interactive", "--repo", "."])

    assert exit_code == 0
    assert captured["initial_prompt"] == ""
    assert captured["config"].repo == "."
    assert captured["session_id"] is None
    assert captured["resume"] is False


def test_agent_interactive_can_resume_named_session(monkeypatch) -> None:
    import patchsmith.cli.commands.chat as chat_commands

    captured: dict[str, object] = {}

    def fake_run_chat_session(
        *,
        config,
        initial_prompt: str,
        input_stream,
        output_stream,
        runner_cls,
        model_preflight_checker=None,
        session_id=None,
        resume: bool = False,
    ) -> int:
        captured["config"] = config
        captured["initial_prompt"] = initial_prompt
        captured["session_id"] = session_id
        captured["resume"] = resume
        return 0

    monkeypatch.setattr(chat_commands, "run_chat_session", fake_run_chat_session)

    exit_code = main(["agent", "--interactive", "--repo", ".", "--resume", "session-123"])

    assert exit_code == 0
    assert captured["initial_prompt"] == ""
    assert captured["session_id"] == "session-123"
    assert captured["resume"] is True


def test_agent_interactive_can_list_saved_sessions(tmp_path: Path, capsys) -> None:
    transcript_dir = tmp_path / "artifacts" / "chat_sessions"
    transcript_dir.mkdir(parents=True)
    (transcript_dir / "agent-session.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-06-14T00:00:00+00:00",
                "session_id": "agent-session",
                "event": "session_start",
                "payload": {"config": {"repo": "."}},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "agent",
            "--interactive",
            "--artifacts-dir",
            str(tmp_path / "artifacts"),
            "--list-sessions",
        ]
    )

    assert exit_code == 0
    assert "agent-session" in capsys.readouterr().out


def test_agent_interactive_can_list_project_custom_commands(
    tmp_path: Path,
    capsys,
) -> None:
    command_dir = tmp_path / ".patchsmith" / "commands"
    command_dir.mkdir(parents=True)
    (command_dir / "review.md").write_text(
        "Review $ARGUMENTS\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "agent",
            "--interactive",
            "--repo",
            str(tmp_path),
            "--list-commands",
        ]
    )

    assert exit_code == 0
    assert "/review" in capsys.readouterr().out


def test_agent_interactive_can_list_project_custom_commands_json(
    tmp_path: Path,
    capsys,
) -> None:
    command_dir = tmp_path / ".patchsmith" / "commands"
    command_dir.mkdir(parents=True)
    (command_dir / "review.md").write_text(
        "---\n"
        "description: Review generated patch evidence\n"
        "---\n"
        "Review $ARGUMENTS\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "agent",
            "--interactive",
            "--repo",
            str(tmp_path),
            "--list-commands",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["commands"][0]["name"] == "review"
    assert payload["commands"][0]["description"] == "Review generated patch evidence"


def test_agent_interactive_rejects_preflight(capsys) -> None:
    assert main(["agent", "--interactive", "--preflight"]) == 2
    captured = capsys.readouterr()
    assert "pass either --interactive or --preflight" in captured.err


def test_agent_noninteractive_rejects_resume(capsys) -> None:
    assert main(["agent", "fix parser", "--resume", "session-123"]) == 2
    captured = capsys.readouterr()
    assert "--resume requires --interactive" in captured.err


def test_agent_noninteractive_rejects_list_sessions(capsys) -> None:
    assert main(["agent", "fix parser", "--list-sessions"]) == 2
    captured = capsys.readouterr()
    assert "--list-sessions requires --interactive" in captured.err


def test_agent_noninteractive_rejects_list_commands(capsys) -> None:
    assert main(["agent", "fix parser", "--list-commands"]) == 2
    captured = capsys.readouterr()
    assert "--list-commands requires --interactive" in captured.err


def test_agent_noninteractive_rejects_list_hooks(capsys) -> None:
    assert main(["agent", "fix parser", "--list-hooks"]) == 2
    captured = capsys.readouterr()
    assert "--list-hooks requires --interactive" in captured.err


def test_agent_noninteractive_rejects_list_agents(capsys) -> None:
    assert main(["agent", "fix parser", "--list-agents"]) == 2
    captured = capsys.readouterr()
    assert "--list-agents requires --interactive" in captured.err


def test_agent_noninteractive_rejects_list_instructions(capsys) -> None:
    assert main(["agent", "fix parser", "--list-instructions"]) == 2
    captured = capsys.readouterr()
    assert "--list-instructions requires --interactive" in captured.err


def test_agent_noninteractive_rejects_script(tmp_path: Path, capsys) -> None:
    script_path = tmp_path / "session.patchsmith"
    script_path.write_text("/exit\n", encoding="utf-8")

    assert main(["agent", "fix parser", "--script", str(script_path)]) == 2
    captured = capsys.readouterr()
    assert "--script requires --interactive" in captured.err


def test_agent_noninteractive_rejects_session_metrics(capsys) -> None:
    assert main(["agent", "fix parser", "--session-metrics", "session-123"]) == 2
    captured = capsys.readouterr()
    assert "--session-metrics requires --interactive" in captured.err


def test_agent_noninteractive_rejects_session_next(capsys) -> None:
    assert main(["agent", "fix parser", "--session-next", "session-123"]) == 2
    captured = capsys.readouterr()
    assert "--session-next requires --interactive" in captured.err


def test_agent_noninteractive_rejects_export_session(capsys) -> None:
    assert main(["agent", "fix parser", "--export-session", "session-123"]) == 2
    captured = capsys.readouterr()
    assert "--export-session requires --interactive" in captured.err


def test_agent_noninteractive_rejects_session_gate(capsys) -> None:
    assert main(["agent", "fix parser", "--session-gate", "session-123"]) == 2
    captured = capsys.readouterr()
    assert "--session-gate requires --interactive" in captured.err


def test_agent_noninteractive_rejects_session_gate_thresholds(capsys) -> None:
    assert main(["agent", "fix parser", "--min-validation-rate", "0.9"]) == 2
    captured = capsys.readouterr()
    assert "session gate thresholds require --session-gate" in captured.err


def test_agent_interactive_validates_shared_agent_options(capsys) -> None:
    assert main(["agent", "--interactive", "--allow-dirty-apply"]) == 2
    captured = capsys.readouterr()
    assert "--allow-dirty-apply requires --apply" in captured.err


def test_quality_gate_cli_defaults_use_production_timeout() -> None:
    parser = build_parser()
    quality_args = parser.parse_args(["quality-gate"])
    refresh_args = parser.parse_args(["refresh-evidence"])

    assert quality_args.timeout_seconds == DEFAULT_QUALITY_GATE_TIMEOUT_SECONDS
    assert refresh_args.quality_timeout_seconds == DEFAULT_QUALITY_GATE_TIMEOUT_SECONDS


def _git_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    _run_git(path, "init")
    _run_git(path, "config", "user.email", "patchsmith@example.invalid")
    _run_git(path, "config", "user.name", "PatchSmith Test")
    (path / "app.py").write_text("value = 1\n", encoding="utf-8")
    _run_git(path, "add", "app.py")
    _run_git(path, "commit", "-m", "init")
    return path


def _write_session_metrics_transcript(artifacts_dir: Path, session_id: str) -> None:
    transcript_dir = artifacts_dir / "chat_sessions"
    transcript_dir.mkdir(parents=True)
    transcript_path = transcript_dir / f"{session_id}.jsonl"
    rows = [
        {
            "timestamp": "2026-06-14T00:00:00+00:00",
            "session_id": session_id,
            "event": "session_start",
            "payload": {
                "config": {
                    "repo": ".",
                    "context_paths": [],
                    "context_provider": "native_hybrid",
                    "max_model_responses": 12,
                    "max_model_tokens": 200000,
                }
            },
        },
        {
            "timestamp": "2026-06-14T00:00:01+00:00",
            "session_id": session_id,
            "event": "preflight",
            "payload": {"status": "passed"},
        },
        {
            "timestamp": "2026-06-14T00:00:02+00:00",
            "session_id": session_id,
            "event": "model_preflight",
            "payload": {
                "provider": "openai_models",
                "model": "gpt-test",
                "endpoint": "https://api.openai.com/v1/models",
                "status": "available",
                "available": True,
                "available_model_count": 3,
                "suggestions": [],
                "error": None,
            },
        },
        {
            "timestamp": "2026-06-14T00:00:03+00:00",
            "session_id": session_id,
            "event": "user_task",
            "payload": {"task": "fix parser"},
        },
        {
            "timestamp": "2026-06-14T00:00:04+00:00",
            "session_id": session_id,
            "event": "run_result",
            "payload": {
                "run_id": "run-session",
                "status": "completed",
                "test_exit_code": 0,
                "report_path": "artifacts/runs/run-session/report.md",
                "trace_path": "artifacts/runs/run-session/traces.jsonl",
                "final_diff_path": "artifacts/runs/run-session/final.diff",
                "model_call_count": 1,
                "model_response_count": 2,
                "model_total_tokens": 100,
                "estimated_cost_usd": 0.01,
            },
        },
        {
            "timestamp": "2026-06-14T00:00:05+00:00",
            "session_id": session_id,
            "event": "diff_review",
            "payload": {
                "risk_level": "low",
                "score": 0,
                "decision": "ready_for_apply_check",
                "confirmation_required": False,
                "findings": [],
            },
        },
        {
            "timestamp": "2026-06-14T00:00:06+00:00",
            "session_id": session_id,
            "event": "apply_check_result",
            "payload": {
                "status": "ready",
                "repo_path": ".",
                "diff_path": "artifacts/runs/run-session/final.diff",
                "message": "diff can be applied to working tree",
                "applied": False,
            },
        },
    ]
    transcript_path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_repeated_failure_transcript(artifacts_dir: Path, session_id: str) -> None:
    transcript_dir = artifacts_dir / "chat_sessions"
    transcript_dir.mkdir(parents=True)
    transcript_path = transcript_dir / f"{session_id}.jsonl"
    rows = [
        {
            "timestamp": "2026-06-14T00:00:00+00:00",
            "session_id": session_id,
            "event": "session_start",
            "payload": {
                "config": {
                    "repo": ".",
                    "context_paths": [],
                    "context_provider": "native_hybrid",
                    "max_model_responses": 12,
                    "max_model_tokens": 200000,
                }
            },
        },
        {
            "timestamp": "2026-06-14T00:00:01+00:00",
            "session_id": session_id,
            "event": "user_task",
            "payload": {"task": "fix parser"},
        },
        {
            "timestamp": "2026-06-14T00:00:02+00:00",
            "session_id": session_id,
            "event": "run_result",
            "payload": _failed_run_payload("run-stuck-1"),
        },
        {
            "timestamp": "2026-06-14T00:00:03+00:00",
            "session_id": session_id,
            "event": "run_evidence",
            "payload": {"run_id": "run-stuck-1", "trace_event_count": 8},
        },
        {
            "timestamp": "2026-06-14T00:00:04+00:00",
            "session_id": session_id,
            "event": "user_task",
            "payload": {"task": "fix parser"},
        },
        {
            "timestamp": "2026-06-14T00:00:05+00:00",
            "session_id": session_id,
            "event": "run_result",
            "payload": _failed_run_payload("run-stuck-2"),
        },
    ]
    transcript_path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def _failed_run_payload(run_id: str) -> dict[str, object]:
    return {
        "run_id": run_id,
        "status": "completed",
        "test_exit_code": 1,
        "report_path": f"artifacts/runs/{run_id}/report.md",
        "trace_path": f"artifacts/runs/{run_id}/traces.jsonl",
        "final_diff_path": f"artifacts/runs/{run_id}/final.diff",
        "retrieved_files": ["calc.py", "test_calc.py"],
        "repair_outcome_status": "unresolved",
        "repair_verdict": "no_patch_tests_failed",
        "repair_failure_category": "no_patch_generated",
        "repair_patch_generated": False,
        "repair_tests_passed": False,
        "repair_next_action": "Improve planning before rerunning.",
        "model_call_count": 1,
        "model_response_count": 2,
        "model_total_tokens": 21056,
        "estimated_cost_usd": 0.01,
    }


def _run_git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
