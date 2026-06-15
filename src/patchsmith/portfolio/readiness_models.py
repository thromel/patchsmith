"""Portfolio readiness and calibration report models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class DemoReadinessGate:
    name: str
    status: str
    evidence: str
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DemoReadinessReport:
    artifacts_dir: str
    generated_at: str
    readiness_status: str
    experiment_count: int
    run_count: int
    metric_count: int
    runs_requiring_attention: int
    failure_categories: dict[str, int]
    model_providers: dict[str, int]
    gates: list[DemoReadinessGate]
    demo_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "readiness_status": self.readiness_status,
            "experiment_count": self.experiment_count,
            "run_count": self.run_count,
            "metric_count": self.metric_count,
            "runs_requiring_attention": self.runs_requiring_attention,
            "failure_categories": self.failure_categories,
            "model_providers": self.model_providers,
            "gates": [gate.to_dict() for gate in self.gates],
            "demo_commands": self.demo_commands,
        }


@dataclass(frozen=True)
class LiveCalibrationCheck:
    name: str
    status: str
    evidence: str
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LiveCalibrationReport:
    artifacts_dir: str
    generated_at: str
    calibration_status: str
    saved_live_provider_count: int
    deepagents_package_run_count: int
    deepagents_compatibility_run_count: int
    model_providers: dict[str, int]
    checks: list[LiveCalibrationCheck]
    smoke_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "calibration_status": self.calibration_status,
            "saved_live_provider_count": self.saved_live_provider_count,
            "deepagents_package_run_count": self.deepagents_package_run_count,
            "deepagents_compatibility_run_count": self.deepagents_compatibility_run_count,
            "model_providers": self.model_providers,
            "checks": [check.to_dict() for check in self.checks],
            "smoke_commands": self.smoke_commands,
        }


@dataclass(frozen=True)
class LiveCalibrationPlanRun:
    name: str
    stage: str
    status: str
    runtime: str
    planner: str
    context_provider: str
    output_path: str
    requires_credentials: bool
    command: str
    success_evidence: str
    claim_boundary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LiveCalibrationPlanReport:
    artifacts_dir: str
    generated_at: str
    plan_status: str
    calibration_status: str
    saved_live_provider_count: int
    credentials_configured: bool
    model: str
    cost_rates_configured: bool
    runs: list[LiveCalibrationPlanRun]
    prerequisites: list[LiveCalibrationCheck]
    claim_boundary: list[str]

    def to_dict(self) -> dict[str, Any]:
        run_statuses = [run.status for run in self.runs]
        return {
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "plan_status": self.plan_status,
            "calibration_status": self.calibration_status,
            "saved_live_provider_count": self.saved_live_provider_count,
            "credentials_configured": self.credentials_configured,
            "model": self.model,
            "cost_rates_configured": self.cost_rates_configured,
            "run_count": len(self.runs),
            "ready_runs": run_statuses.count("ready"),
            "blocked_runs": run_statuses.count("blocked"),
            "runs": [run.to_dict() for run in self.runs],
            "prerequisites": [check.to_dict() for check in self.prerequisites],
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class DockerSmokeCheck:
    name: str
    status: str
    evidence: str
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DockerSmokeReport:
    project_root: str
    artifacts_dir: str
    generated_at: str
    smoke_status: str
    docker_binary: str
    image: str
    task_dir: str
    test_command: str
    runtime: str
    context_provider: str
    run_report_path: str | None
    run_trace_path: str | None
    run_id: str | None
    test_exit_code: int | None
    checks: list[DockerSmokeCheck]
    environment: dict[str, str]
    remediation_commands: list[str]
    build_command: str
    smoke_command: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "smoke_status": self.smoke_status,
            "docker_binary": self.docker_binary,
            "image": self.image,
            "task_dir": self.task_dir,
            "test_command": self.test_command,
            "runtime": self.runtime,
            "context_provider": self.context_provider,
            "run_report_path": self.run_report_path,
            "run_trace_path": self.run_trace_path,
            "run_id": self.run_id,
            "test_exit_code": self.test_exit_code,
            "checks": [check.to_dict() for check in self.checks],
            "environment": self.environment,
            "remediation_commands": self.remediation_commands,
            "build_command": self.build_command,
            "smoke_command": self.smoke_command,
        }


@dataclass(frozen=True)
class EnvironmentReadinessCheck:
    area: str
    name: str
    status: str
    evidence: str
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EnvironmentReadinessReport:
    project_root: str
    artifacts_dir: str
    generated_at: str
    readiness_status: str
    passed_count: int
    warning_count: int
    blocked_count: int
    checks: list[EnvironmentReadinessCheck]
    remediation_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "readiness_status": self.readiness_status,
            "passed_count": self.passed_count,
            "warning_count": self.warning_count,
            "blocked_count": self.blocked_count,
            "checks": [check.to_dict() for check in self.checks],
            "remediation_commands": self.remediation_commands,
        }


__all__ = [
    "DemoReadinessGate",
    "DemoReadinessReport",
    "DockerSmokeCheck",
    "DockerSmokeReport",
    "EnvironmentReadinessCheck",
    "EnvironmentReadinessReport",
    "LiveCalibrationCheck",
    "LiveCalibrationPlanReport",
    "LiveCalibrationPlanRun",
    "LiveCalibrationReport",
]
