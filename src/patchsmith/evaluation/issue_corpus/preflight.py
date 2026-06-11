"""Evaluation issue corpus preflight (split from evaluation.py)."""

from __future__ import annotations

import csv
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from patchsmith.artifacts import write_json
from patchsmith.evaluation_models import (
    IssueCorpusRepoPreflightResult,
    IssueCorpusRepoPreflightSummary,
)
from patchsmith.evaluation_reports import (
    render_issue_corpus_repo_preflight_report,
)


def preflight_issue_corpus_repositories(
    *,
    corpus_path: Path,
    output_dir: Path,
    timeout_seconds: int = 20,
) -> tuple[list[IssueCorpusRepoPreflightResult], IssueCorpusRepoPreflightSummary]:
    if not corpus_path.exists():
        raise FileNotFoundError(f"issue corpus does not exist: {corpus_path}")
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("issues"), list):
        raise ValueError("issue corpus missing list field: issues")
    repositories = _issue_corpus_repositories(payload["issues"])
    output_dir.mkdir(parents=True, exist_ok=True)
    results = [
        _preflight_issue_corpus_repository(
            repository=repository,
            repo_url=repo_url,
            issue_count=issue_count,
            timeout_seconds=timeout_seconds,
        )
        for repository, repo_url, issue_count in repositories
    ]
    summary = summarize_issue_corpus_repo_preflight(
        corpus_path=corpus_path,
        results=results,
    )
    write_issue_corpus_repo_preflight_outputs(
        output_dir=output_dir,
        corpus_path=corpus_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_issue_corpus_repo_preflight(
    *,
    corpus_path: Path,
    results: list[IssueCorpusRepoPreflightResult],
) -> IssueCorpusRepoPreflightSummary:
    latencies = [result.latency_ms for result in results if result.status == "reachable"]
    return IssueCorpusRepoPreflightSummary(
        corpus_path=str(corpus_path),
        repository_count=len(results),
        reachable_repositories=sum(1 for result in results if result.status == "reachable"),
        unreachable_repositories=sum(1 for result in results if result.status != "reachable"),
        issue_count=sum(result.issue_count for result in results),
        avg_latency_ms=round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
    )


def write_issue_corpus_repo_preflight_outputs(
    *,
    output_dir: Path,
    corpus_path: Path,
    results: list[IssueCorpusRepoPreflightResult],
    summary: IssueCorpusRepoPreflightSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "repo_preflight_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(output_dir / "repo_preflight_summary.json", summary.to_dict(), trailing_newline=True)
    with (output_dir / "repo_preflight_results.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        fieldnames = list(results[0].to_dict()) if results else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if results:
            writer.writeheader()
            for result in results:
                writer.writerow(result.to_dict())
    (output_dir / "repo_preflight_report.md").write_text(
        render_issue_corpus_repo_preflight_report(
            corpus_path=corpus_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def _issue_corpus_repositories(issues: list[Any]) -> list[tuple[str, str, int]]:
    repo_urls: dict[str, str] = {}
    issue_counts: dict[str, int] = {}
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        repository = issue.get("repository")
        repo_url = issue.get("repo_url")
        if not isinstance(repository, str) or not repository.strip():
            continue
        if not isinstance(repo_url, str) or not repo_url.strip():
            continue
        repository = repository.strip()
        repo_urls[repository] = repo_url.strip()
        issue_counts[repository] = issue_counts.get(repository, 0) + 1
    return [
        (repository, repo_urls[repository], issue_counts[repository])
        for repository in sorted(repo_urls)
    ]


def _preflight_issue_corpus_repository(
    *,
    repository: str,
    repo_url: str,
    issue_count: int,
    timeout_seconds: int,
) -> IssueCorpusRepoPreflightResult:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            ["git", "ls-remote", "--symref", repo_url, "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return IssueCorpusRepoPreflightResult(
            repository=repository,
            repo_url=repo_url,
            status="unreachable",
            default_branch=None,
            head_sha=None,
            latency_ms=int((time.perf_counter() - started) * 1000),
            error=str(error),
            issue_count=issue_count,
        )
    latency_ms = int((time.perf_counter() - started) * 1000)
    default_branch, head_sha = _parse_ls_remote_head(completed.stdout)
    if completed.returncode != 0:
        failure = completed.stderr.strip() or completed.stdout.strip() or "git ls-remote failed"
        return IssueCorpusRepoPreflightResult(
            repository=repository,
            repo_url=repo_url,
            status="unreachable",
            default_branch=default_branch,
            head_sha=head_sha,
            latency_ms=latency_ms,
            error=failure,
            issue_count=issue_count,
        )
    return IssueCorpusRepoPreflightResult(
        repository=repository,
        repo_url=repo_url,
        status="reachable",
        default_branch=default_branch,
        head_sha=head_sha,
        latency_ms=latency_ms,
        error=None,
        issue_count=issue_count,
    )


def _parse_ls_remote_head(output: str) -> tuple[str | None, str | None]:
    default_branch: str | None = None
    head_sha: str | None = None
    for line in output.splitlines():
        if line.startswith("ref:") and "\tHEAD" in line:
            ref = line.split()[1] if len(line.split()) >= 2 else ""
            prefix = "refs/heads/"
            default_branch = ref[len(prefix) :] if ref.startswith(prefix) else ref or None
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "HEAD":
            head_sha = parts[0]
    return default_branch, head_sha
