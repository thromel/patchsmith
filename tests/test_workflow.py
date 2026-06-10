import json
from pathlib import Path

from patchsmith.models import CommandPolicyDecision, CommandResult, RunRequest
from patchsmith.workflow import RepairRunner


def test_repair_runner_writes_report_trace_and_test_output(tmp_path: Path) -> None:
    fixture = Path("tests/fixtures/simple_calc_bug")
    issue = (fixture / "issue.md").read_text(encoding="utf-8")

    result = RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(fixture / "repo"),
            issue_text=issue,
            test_command="python3 -m pytest",
        )
    )

    assert result.status == "completed"
    assert result.report_path.exists()
    assert result.trace_path.exists()
    assert result.final_diff_path.exists()
    assert result.test_result is not None
    assert result.test_result.exit_code == 1
    assert result.retrieved_context[0].path == "src/simple_calc.py"

    report = result.report_path.read_text(encoding="utf-8")
    assert "# PatchSmith Run Report" in report
    assert "src/simple_calc.py" in report
    assert "Test Results" in report
    assert "Context Packing" in report
    assert "Approximate tokens" in report
    assert "Sandbox: `local`" in report
    assert "Repair Analysis" in report
    assert "Final Verdict" in report
    assert "`no_patch_tests_failed`" in report
    trace = result.trace_path.read_text(encoding="utf-8")
    assert '"node_name": "analyze"' in trace
    assert '"event_type": "repair_outcome"' in trace


def test_repair_runner_auto_context_provider_falls_back_to_native(tmp_path: Path) -> None:
    fixture = Path("tests/fixtures/simple_calc_bug")
    issue = (fixture / "issue.md").read_text(encoding="utf-8")

    result = RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(fixture / "repo"),
            issue_text=issue,
            test_command="python3 -m pytest",
            context_provider="auto",
            retrieval_strategy="auto",
        )
    )

    assert result.status == "completed"
    assert result.retrieved_context[0].path == "src/simple_calc.py"
    trace = result.trace_path.read_text(encoding="utf-8")
    assert "context_broker_call" in trace


def test_repair_runner_heuristic_runtime_generates_passing_patch(tmp_path: Path) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")
    issue = (fixture / "issue.md").read_text(encoding="utf-8")

    result = RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(fixture / "repo"),
            issue_text=issue,
            test_command="python3 -m pytest",
            runtime="heuristic",
            context_provider="native_hybrid",
            retrieval_strategy="native_hybrid",
        )
    )

    assert result.status == "completed"
    assert result.test_result is not None
    assert result.test_result.exit_code == 0
    assert "+    return left + right" in result.final_diff_path.read_text(encoding="utf-8")
    report = result.report_path.read_text(encoding="utf-8")
    assert "Patch generation: `patch_generated`" in report
    assert "`patch_validated`" in report


def test_repair_runner_records_selected_sandbox_in_trace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")
    created: list[tuple[str, str]] = []

    class FakeSandboxRunner:
        def run(self, *, command: str, workspace: Path, timeout_seconds: int = 60) -> CommandResult:
            return CommandResult(
                command=command,
                exit_code=0,
                stdout="ok\n",
                stderr="",
                duration_ms=7,
                timed_out=False,
                policy_decision=CommandPolicyDecision(
                    allowed=True,
                    reason="allowed",
                    tokens=("python3", "-m", "pytest"),
                ),
            )

    def fake_create_sandbox_runner(*, mode: str, image: str):
        created.append((mode, image))
        return FakeSandboxRunner()

    monkeypatch.setattr("patchsmith.workflow.create_sandbox_runner", fake_create_sandbox_runner)

    result = RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(fixture / "repo"),
            issue_text=(fixture / "issue.md").read_text(encoding="utf-8"),
            test_command="python3 -m pytest",
            runtime="heuristic",
            context_provider="native_hybrid",
            retrieval_strategy="native_hybrid",
            sandbox_mode="docker",
            sandbox_image="patchsmith-test:latest",
        )
    )

    assert result.test_result is not None
    assert result.test_result.exit_code == 0
    assert created == [("docker", "patchsmith-test:latest")]
    trace_events = [
        json.loads(line)
        for line in result.trace_path.read_text(encoding="utf-8").splitlines()
    ]
    sandbox_event = next(
        event for event in trace_events if event["event_type"] == "sandbox_command"
    )
    assert sandbox_event["payload"]["sandbox_mode"] == "docker"
    assert sandbox_event["payload"]["sandbox_image"] == "patchsmith-test:latest"
