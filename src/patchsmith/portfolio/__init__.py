"""Portfolio package; public report-writer entry points.

Report dataclasses live in ``patchsmith.portfolio.models`` and the
``build_*``/``render_*`` helpers in the per-report modules.
"""

from __future__ import annotations

from patchsmith.portfolio.delivery_audit import write_delivery_audit_report
from patchsmith.portfolio.demo_assets import (
    write_demo_media_assets,
    write_demo_script_report,
)
from patchsmith.portfolio.demo_readiness import write_demo_readiness_report
from patchsmith.portfolio.docker_smoke import write_docker_smoke_report
from patchsmith.portfolio.environment_readiness import write_environment_readiness_report
from patchsmith.portfolio.evidence_refresh import write_evidence_refresh_report
from patchsmith.portfolio.final_evaluation import write_final_evaluation_report
from patchsmith.portfolio.launch_blockers import write_launch_blocker_report
from patchsmith.portfolio.live_calibration import (
    write_live_calibration_plan_report,
    write_live_calibration_report,
)
from patchsmith.portfolio.mvp_progress import write_mvp_progress_report
from patchsmith.portfolio.project_status import write_project_status_report
from patchsmith.portfolio.quality_gate import write_quality_gate_report
from patchsmith.portfolio.release_hygiene import write_release_hygiene_report

__all__ = [
    "write_delivery_audit_report",
    "write_demo_media_assets",
    "write_demo_readiness_report",
    "write_demo_script_report",
    "write_docker_smoke_report",
    "write_environment_readiness_report",
    "write_evidence_refresh_report",
    "write_final_evaluation_report",
    "write_launch_blocker_report",
    "write_live_calibration_plan_report",
    "write_live_calibration_report",
    "write_mvp_progress_report",
    "write_project_status_report",
    "write_quality_gate_report",
    "write_release_hygiene_report",
]
