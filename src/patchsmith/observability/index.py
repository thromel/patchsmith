"""Observability index (split from observability.py)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from patchsmith.artifacts import write_json, write_markdown
from patchsmith.observability.discovery import (
    _discover_runs,
    _experiment_kind,
    _experiment_metric_entries,
    _experiment_run_count,
    _first_existing,
    _relative_or_none,
    _result_count,
    _run_detail_output_path,
    _updated_at,
    _utc_timestamp,
)
from patchsmith.observability.models import (
    GENERATED_EXPERIMENT_DIR_NAMES,
    RECENT_RUN_LIMIT,
    REPORT_FILENAMES,
    RESULT_FILENAMES,
    SUMMARY_FILENAMES,
    ArtifactIndex,
    ExperimentArtifactIndexEntry,
    ExperimentMetricIndexEntry,
)
from patchsmith.observability.render_html import render_artifact_dashboard, render_run_detail_page
from patchsmith.observability.render_md import render_artifact_index


def build_artifact_index(*, artifacts_dir: Path) -> ArtifactIndex:
    artifacts_dir = artifacts_dir.resolve()
    experiments_dir = artifacts_dir / "experiments"
    entries: list[ExperimentArtifactIndexEntry] = []
    metrics: list[ExperimentMetricIndexEntry] = []
    if experiments_dir.exists():
        for experiment_dir in sorted(path for path in experiments_dir.iterdir() if path.is_dir()):
            if experiment_dir.name in GENERATED_EXPERIMENT_DIR_NAMES:
                continue
            report_path = _first_existing(experiment_dir, REPORT_FILENAMES)
            summary_path = _first_existing(experiment_dir, SUMMARY_FILENAMES)
            results_path = _first_existing(experiment_dir, RESULT_FILENAMES)
            kind = _experiment_kind(experiment_dir.name, report_path)
            entry = ExperimentArtifactIndexEntry(
                name=experiment_dir.name,
                kind=kind,
                report_path=_relative_or_none(artifacts_dir, report_path),
                summary_path=_relative_or_none(artifacts_dir, summary_path),
                results_path=_relative_or_none(artifacts_dir, results_path),
                result_count=_result_count(results_path),
                run_count=_experiment_run_count(experiment_dir),
                updated_at=_updated_at(
                    experiment_dir,
                    report_path,
                    summary_path,
                    results_path,
                ),
            )
            entries.append(entry)
            metrics.extend(
                _experiment_metric_entries(
                    experiment=experiment_dir.name,
                    kind=kind,
                    report_path=entry.report_path,
                    summary_path=summary_path,
                    results_path=results_path,
                )
            )

    runs = _discover_runs(artifacts_dir)
    return ArtifactIndex(
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_timestamp(datetime.now(UTC).timestamp()),
        experiment_count=len(entries),
        run_count=len(runs),
        experiments=entries,
        metrics=metrics,
        runs=runs,
    )


def write_artifact_index(
    *,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    html_output_path: Path | None = None,
    run_detail_output_dir: Path | None = None,
) -> ArtifactIndex:
    index = build_artifact_index(artifacts_dir=artifacts_dir)
    if run_detail_output_dir is not None:
        write_run_detail_pages(
            index=index,
            output_dir=run_detail_output_dir,
            dashboard_path=html_output_path,
        )
    write_markdown(
        output_path,
        render_artifact_index(
            index,
            run_detail_output_dir=run_detail_output_dir,
        ),
    )
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(json_output_path, index.to_dict(), trailing_newline=True)
    if html_output_path is not None:
        write_markdown(
            html_output_path,
            render_artifact_dashboard(
                index,
                output_path=html_output_path,
                run_detail_output_dir=run_detail_output_dir,
            ),
        )
    return index


def write_run_detail_pages(
    *,
    index: ArtifactIndex,
    output_dir: Path,
    dashboard_path: Path | None = None,
    limit: int = RECENT_RUN_LIMIT,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale_path in output_dir.glob("*.html"):
        stale_path.unlink()
    written: list[Path] = []
    artifacts_dir = Path(index.artifacts_dir)
    for run in index.runs[:limit]:
        output_path = _run_detail_output_path(output_dir, run)
        output_path.write_text(
            render_run_detail_page(
                run,
                artifacts_dir=artifacts_dir,
                output_path=output_path,
                dashboard_path=dashboard_path,
            ),
            encoding="utf-8",
        )
        written.append(output_path)
    return written
