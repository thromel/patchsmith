import json
from pathlib import Path

from patchsmith.models import CommandPolicyDecision, CommandResult, RunRequest
from patchsmith.planning import RepairPlan
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
        json.loads(line) for line in result.trace_path.read_text(encoding="utf-8").splitlines()
    ]
    sandbox_event = next(
        event for event in trace_events if event["event_type"] == "sandbox_command"
    )
    assert sandbox_event["payload"]["sandbox_mode"] == "docker"
    assert sandbox_event["payload"]["sandbox_image"] == "patchsmith-test:latest"


def test_deepagents_runner_retries_with_sandbox_feedback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")
    planner = SequencedFeedbackPlanner()
    sandbox = SequencedSandboxRunner(exit_codes=[1, 0])

    monkeypatch.setattr("patchsmith.workflow._planner_for", lambda planner_name: planner)
    monkeypatch.setattr(
        "patchsmith.workflow.create_sandbox_runner",
        lambda *, mode, image: sandbox,
    )

    result = RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(fixture / "repo"),
            issue_text=(fixture / "issue.md").read_text(encoding="utf-8"),
            test_command="python3 -m pytest",
            runtime="deepagents",
            planner="deepagents",
            max_retries=1,
            context_provider="native_hybrid",
            retrieval_strategy="native_hybrid",
        )
    )

    assert result.test_result is not None
    assert result.test_result.exit_code == 0
    assert len(planner.issue_texts) == 2
    assert "Previous DeepAgents repair attempt 1 did not validate" in planner.issue_texts[1]
    assert "previous patch is on the code path reached" in planner.issue_texts[1]
    assert "failure from attempt 1" in planner.issue_texts[1]
    assert len(sandbox.calls) == 2
    assert "return left + right" in (result.repo_path / "src/simple_calc.py").read_text(
        encoding="utf-8"
    )
    trace_events = [
        json.loads(line) for line in result.trace_path.read_text(encoding="utf-8").splitlines()
    ]
    retry_event = next(event for event in trace_events if event["node_name"] == "feedback_retry")
    assert retry_event["payload"]["next_attempt"] == 2
    test_events = [event for event in trace_events if event["event_type"] == "sandbox_command"]
    assert [event["payload"]["attempt"] for event in test_events] == [1, 2]


def test_deepagents_runner_retries_after_rejected_edit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")
    planner = RejectedEditFeedbackPlanner()
    sandbox = SequencedSandboxRunner(exit_codes=[1, 0])

    monkeypatch.setattr("patchsmith.workflow._planner_for", lambda planner_name: planner)
    monkeypatch.setattr(
        "patchsmith.workflow.create_sandbox_runner",
        lambda *, mode, image: sandbox,
    )

    result = RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(fixture / "repo"),
            issue_text=(fixture / "issue.md").read_text(encoding="utf-8"),
            test_command="python3 -m pytest",
            runtime="deepagents",
            planner="deepagents",
            max_retries=1,
            context_provider="native_hybrid",
            retrieval_strategy="native_hybrid",
        )
    )

    assert result.test_result is not None
    assert result.test_result.exit_code == 0
    assert len(planner.issue_texts) == 2
    assert "Previous agent status:\nno_patch_generated" in planner.issue_texts[1]
    assert "replacement text not found" in planner.issue_texts[1]
    assert len(sandbox.calls) == 2
    assert "return left + right" in (result.repo_path / "src/simple_calc.py").read_text(
        encoding="utf-8"
    )


class SequencedFeedbackPlanner:
    def __init__(self) -> None:
        self.issue_texts: list[str] = []

    def prepare_task(self, task: object) -> None:
        pass

    def plan(
        self,
        *,
        issue_text: str,
        retrieved_context: list[object],
    ) -> RepairPlan | None:
        self.issue_texts.append(issue_text)
        if len(self.issue_texts) == 1:
            return RepairPlan(
                name="bad_first_patch",
                path="src/simple_calc.py",
                old="return left - right",
                new="return left + 0",
                summary="Intentionally incomplete first patch.",
            )
        return RepairPlan(
            name="feedback_patch",
            path="src/simple_calc.py",
            old="return left + 0",
            new="return left + right",
            summary="Use sandbox feedback to repair the failed attempt.",
        )


class RejectedEditFeedbackPlanner:
    def __init__(self) -> None:
        self.issue_texts: list[str] = []

    def prepare_task(self, task: object) -> None:
        pass

    def plan(
        self,
        *,
        issue_text: str,
        retrieved_context: list[object],
    ) -> RepairPlan | None:
        self.issue_texts.append(issue_text)
        if len(self.issue_texts) == 1:
            return RepairPlan(
                name="bad_span",
                path="src/simple_calc.py",
                old="return does_not_exist",
                new="return left + right",
                summary="Use an old span that does not exist.",
            )
        return RepairPlan(
            name="feedback_patch",
            path="src/simple_calc.py",
            old="return left - right",
            new="return left + right",
            summary="Use feedback to provide the exact old span.",
        )


class SequencedSandboxRunner:
    def __init__(self, *, exit_codes: list[int]) -> None:
        self.exit_codes = exit_codes
        self.calls: list[str] = []

    def run(self, *, command: str, workspace: Path, timeout_seconds: int = 60) -> CommandResult:
        self.calls.append(command)
        exit_code = self.exit_codes[len(self.calls) - 1]
        attempt = len(self.calls)
        return CommandResult(
            command=command,
            exit_code=exit_code,
            stdout=f"stdout from attempt {attempt}\n",
            stderr="" if exit_code == 0 else f"failure from attempt {attempt}\n",
            duration_ms=7,
            timed_out=False,
            policy_decision=CommandPolicyDecision(
                allowed=True,
                reason="allowed",
                tokens=("python3", "-m", "pytest"),
            ),
        )
