from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from patchsmith.cli import main

pytestmark = pytest.mark.unit


def test_index_command_uses_repository_cli_module(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    import patchsmith.cli.commands.repository as repository_commands

    captured: dict[str, Any] = {}
    repo_path = tmp_path / "repo"

    def fake_clone_or_copy_repository(
        repo: str,
        dest: Path,
        *,
        commit: str | None = None,
        branch: str | None = None,
    ) -> SimpleNamespace:
        captured["clone"] = {
            "repo": repo,
            "dest_name": dest.name,
            "commit": commit,
            "branch": branch,
        }
        return SimpleNamespace(repo_path=repo_path)

    class FakeRepoIndex:
        def to_dict(self) -> dict[str, object]:
            return {"files": [{"path": "src/calc.py"}]}

    def fake_index_repository(path: Path) -> FakeRepoIndex:
        captured["index_path"] = path
        return FakeRepoIndex()

    monkeypatch.setattr(
        repository_commands,
        "clone_or_copy_repository",
        fake_clone_or_copy_repository,
    )
    monkeypatch.setattr(repository_commands, "index_repository", fake_index_repository)

    exit_code = main(["index", "--repo", "repo-url", "--commit", "abc", "--branch", "main"])

    assert exit_code == 0
    assert captured == {
        "clone": {
            "repo": "repo-url",
            "dest_name": "repo",
            "commit": "abc",
            "branch": "main",
        },
        "index_path": repo_path,
    }
    assert json.loads(capsys.readouterr().out) == {"files": [{"path": "src/calc.py"}]}


def test_retrieve_command_uses_repository_cli_module(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    import patchsmith.cli.commands.repository as repository_commands

    captured: dict[str, Any] = {}
    repo_path = tmp_path / "repo"

    class FakeRepoIndex:
        pass

    class FakeContext:
        def to_dict(self) -> dict[str, object]:
            return {"path": "src/calc.py", "rank": 1}

    class FakeRetriever:
        def retrieve(
            self,
            *,
            repo_path: Path,
            repo_index: FakeRepoIndex,
            issue_text: str,
            top_k: int,
        ) -> list[FakeContext]:
            captured["retrieve"] = {
                "repo_path": repo_path,
                "repo_index": repo_index,
                "issue_text": issue_text,
                "top_k": top_k,
            }
            return [FakeContext()]

    def fake_clone_or_copy_repository(
        repo: str,
        dest: Path,
        *,
        commit: str | None = None,
        branch: str | None = None,
    ) -> SimpleNamespace:
        captured["clone"] = {
            "repo": repo,
            "dest_name": dest.name,
            "commit": commit,
            "branch": branch,
        }
        return SimpleNamespace(repo_path=repo_path)

    def fake_index_repository(path: Path) -> FakeRepoIndex:
        captured["index_path"] = path
        return FakeRepoIndex()

    def fake_retriever_for(name: str) -> FakeRetriever:
        captured["retrieval"] = name
        return FakeRetriever()

    monkeypatch.setattr(
        repository_commands,
        "clone_or_copy_repository",
        fake_clone_or_copy_repository,
    )
    monkeypatch.setattr(repository_commands, "index_repository", fake_index_repository)
    monkeypatch.setattr(repository_commands, "_retriever_for", fake_retriever_for)

    exit_code = main(
        [
            "retrieve",
            "--repo",
            "repo-url",
            "--issue",
            "broken addition",
            "--retrieval",
            "native_hybrid",
            "--top-k",
            "2",
        ]
    )

    assert exit_code == 0
    assert captured["clone"] == {
        "repo": "repo-url",
        "dest_name": "repo",
        "commit": None,
        "branch": None,
    }
    assert captured["index_path"] == repo_path
    assert captured["retrieval"] == "native_hybrid"
    assert captured["retrieve"]["repo_path"] == repo_path
    assert captured["retrieve"]["issue_text"] == "broken addition"
    assert captured["retrieve"]["top_k"] == 2
    assert json.loads(capsys.readouterr().out) == [{"path": "src/calc.py", "rank": 1}]
