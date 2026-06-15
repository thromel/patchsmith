from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from patchsmith.session.metrics import AgentSessionMetrics


@dataclass(frozen=True)
class AgentSessionGateConfig:
    require_validated_run: bool = False
    require_diff_review: bool = False
    require_ready_apply_check: bool = False
    min_validation_rate: float | None = None
    min_preflight_to_run_rate: float | None = None
    min_apply_success_rate: float | None = None
    max_high_risk_diff_reviews: int | None = None
    max_cost_per_validated_run_usd: float | None = None
    max_run_errors: int | None = None


@dataclass(frozen=True)
class AgentSessionGateCheck:
    name: str
    status: str
    value: object
    threshold: object
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "value": self.value,
            "threshold": self.threshold,
            "message": self.message,
        }


@dataclass(frozen=True)
class AgentSessionGateResult:
    status: str
    checks: list[AgentSessionGateCheck]
    metrics: AgentSessionMetrics

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "checks": [check.to_dict() for check in self.checks],
            "metrics": self.metrics.to_dict(),
        }


def evaluate_session_gate(
    metrics: AgentSessionMetrics,
    config: AgentSessionGateConfig,
) -> AgentSessionGateResult:
    checks = [
        _validated_run_check(metrics, config.require_validated_run),
        _minimum_number_check(
            name="diff_review_count",
            value=metrics.current_diff_review_count,
            threshold=1 if config.require_diff_review else None,
            value_formatter=str,
        ),
        _minimum_number_check(
            name="ready_apply_check_count",
            value=metrics.current_apply_check_ready_count,
            threshold=1 if config.require_ready_apply_check else None,
            value_formatter=str,
        ),
        _minimum_rate_check(
            name="validation_rate",
            value=metrics.validation_rate,
            threshold=config.min_validation_rate,
        ),
        _minimum_rate_check(
            name="preflight_to_run_rate",
            value=metrics.preflight_to_run_rate,
            threshold=config.min_preflight_to_run_rate,
        ),
        _minimum_rate_check(
            name="apply_success_rate",
            value=metrics.apply_success_rate,
            threshold=config.min_apply_success_rate,
        ),
        _maximum_number_check(
            name="high_risk_diff_review_count",
            value=metrics.current_diff_review_high_count,
            threshold=config.max_high_risk_diff_reviews,
            value_formatter=str,
        ),
        _maximum_number_check(
            name="cost_per_validated_run_usd",
            value=metrics.cost_per_validated_run_usd,
            threshold=config.max_cost_per_validated_run_usd,
            value_formatter=_format_cost,
        ),
        _maximum_number_check(
            name="run_error_count",
            value=metrics.run_error_count,
            threshold=config.max_run_errors,
            value_formatter=str,
        ),
    ]
    status = "failed" if any(check.status == "failed" for check in checks) else "passed"
    return AgentSessionGateResult(status=status, checks=checks, metrics=metrics)


def format_session_gate(result: AgentSessionGateResult) -> str:
    lines = [f"Session gate: {result.status}"]
    for check in result.checks:
        lines.append(f"- {check.name}: {check.status} - {check.message}")
    return "\n".join(lines)


def _validated_run_check(
    metrics: AgentSessionMetrics,
    required: bool,
) -> AgentSessionGateCheck:
    value = metrics.validated_run_count
    if not required:
        return AgentSessionGateCheck(
            name="validated_run",
            status="skipped",
            value=value,
            threshold=None,
            message="no validated-run requirement configured",
        )
    if value > 0:
        return AgentSessionGateCheck(
            name="validated_run",
            status="passed",
            value=value,
            threshold=">=1",
            message=f"{value} validated run(s)",
        )
    return AgentSessionGateCheck(
        name="validated_run",
        status="failed",
        value=value,
        threshold=">=1",
        message="no validated runs recorded",
    )


def _minimum_rate_check(
    *,
    name: str,
    value: float | None,
    threshold: float | None,
) -> AgentSessionGateCheck:
    if threshold is None:
        return AgentSessionGateCheck(
            name=name,
            status="skipped",
            value=value,
            threshold=None,
            message="no threshold configured",
        )
    if value is None:
        return AgentSessionGateCheck(
            name=name,
            status="failed",
            value=None,
            threshold=threshold,
            message=f"missing rate; expected >= {_format_rate(threshold)}",
        )
    if value >= threshold:
        return AgentSessionGateCheck(
            name=name,
            status="passed",
            value=value,
            threshold=threshold,
            message=f"{_format_rate(value)} >= {_format_rate(threshold)}",
        )
    return AgentSessionGateCheck(
        name=name,
        status="failed",
        value=value,
        threshold=threshold,
        message=f"{_format_rate(value)} < {_format_rate(threshold)}",
    )


def _maximum_number_check(
    *,
    name: str,
    value: float | int | None,
    threshold: float | int | None,
    value_formatter: Callable[[object], str],
) -> AgentSessionGateCheck:
    if threshold is None:
        return AgentSessionGateCheck(
            name=name,
            status="skipped",
            value=value,
            threshold=None,
            message="no threshold configured",
        )
    if value is None:
        return AgentSessionGateCheck(
            name=name,
            status="failed",
            value=None,
            threshold=threshold,
            message=f"missing value; expected <= {value_formatter(threshold)}",
        )
    if value <= threshold:
        return AgentSessionGateCheck(
            name=name,
            status="passed",
            value=value,
            threshold=threshold,
            message=f"{value_formatter(value)} <= {value_formatter(threshold)}",
        )
    return AgentSessionGateCheck(
        name=name,
        status="failed",
        value=value,
        threshold=threshold,
        message=f"{value_formatter(value)} > {value_formatter(threshold)}",
    )


def _minimum_number_check(
    *,
    name: str,
    value: int,
    threshold: int | None,
    value_formatter: Callable[[object], str],
) -> AgentSessionGateCheck:
    if threshold is None:
        return AgentSessionGateCheck(
            name=name,
            status="skipped",
            value=value,
            threshold=None,
            message="no threshold configured",
        )
    if value >= threshold:
        return AgentSessionGateCheck(
            name=name,
            status="passed",
            value=value,
            threshold=threshold,
            message=f"{value_formatter(value)} >= {value_formatter(threshold)}",
        )
    return AgentSessionGateCheck(
        name=name,
        status="failed",
        value=value,
        threshold=threshold,
        message=f"{value_formatter(value)} < {value_formatter(threshold)}",
    )


def _format_rate(value: object) -> str:
    if not isinstance(value, int | float):
        return "n/a"
    return f"{float(value):.2%}"


def _format_cost(value: object) -> str:
    if not isinstance(value, int | float):
        return "n/a"
    return f"${float(value):.6f}"

