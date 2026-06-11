import json
from pathlib import Path

from patchsmith.cli import main


def test_run_cli_accepts_context_path_for_explicit_context_steering(
    tmp_path: Path,
    capsys,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "hinted.py").write_text("def hidden_fix_site():\n    pass\n", encoding="utf-8")
    (repo / "README.md").write_text("nothing useful here\n", encoding="utf-8")

    exit_code = main(
        [
            "run",
            "--repo",
            str(repo),
            "--issue",
            "a vague external failure with no lexical match",
            "--context-provider",
            "native_hybrid",
            "--top-k",
            "1",
            "--context-path",
            "src/hinted.py#hidden_fix_site",
            "--artifacts-dir",
            str(tmp_path / "artifacts"),
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["retrieved_files"] == ["src/hinted.py"]
