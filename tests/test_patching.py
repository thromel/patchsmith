from pathlib import Path

import pytest

from patchsmith.ingest import clone_or_copy_repository
from patchsmith.patching import PatchSafetyError, apply_text_replacement


def test_apply_text_replacement_writes_unified_diff(tmp_path: Path) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo")
    snapshot = clone_or_copy_repository(str(fixture), tmp_path / "repo")

    edit = apply_text_replacement(
        repo_path=snapshot.repo_path,
        relative_path="src/simple_calc.py",
        old="return left - right",
        new="return left + right",
    )

    assert "src/simple_calc.py" in edit.diff
    assert "+    return left + right" in edit.diff
    assert "return left + right" in (snapshot.repo_path / "src/simple_calc.py").read_text(
        encoding="utf-8"
    )


def test_apply_text_replacement_rejects_path_escape(tmp_path: Path) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo")
    snapshot = clone_or_copy_repository(str(fixture), tmp_path / "repo")

    with pytest.raises(PatchSafetyError):
        apply_text_replacement(
            repo_path=snapshot.repo_path,
            relative_path="../outside.py",
            old="x",
            new="y",
        )


def test_apply_text_replacement_can_reject_python_comment_only_edit(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "module.py"
    target.write_text("def value():\n    return 1\n", encoding="utf-8")

    with pytest.raises(PatchSafetyError, match="comments or whitespace"):
        apply_text_replacement(
            repo_path=repo,
            relative_path="src/module.py",
            old="def value():\n    return 1",
            new="# explain value\ndef value():\n    return 1",
            reject_comment_only=True,
        )

    assert target.read_text(encoding="utf-8") == "def value():\n    return 1\n"


def test_apply_text_replacement_can_reject_python_syntax_error(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "module.py"
    target.write_text("def value():\n    return 1\n", encoding="utf-8")

    with pytest.raises(PatchSafetyError, match="fail Python compilation"):
        apply_text_replacement(
            repo_path=repo,
            relative_path="src/module.py",
            old="def value():\n    return 1",
            new="def value():\n    break",
            reject_python_syntax_errors=True,
        )

    assert target.read_text(encoding="utf-8") == "def value():\n    return 1\n"


def test_apply_text_replacement_rejects_dangling_compound_header_span(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "rewrite.py"
    target.write_text(
        "def _read_pyc(source, pyc):\n"
        "    if is_stale(pyc):\n"
        "        return None\n"
        "    return marshal.load(pyc)\n",
        encoding="utf-8",
    )

    with pytest.raises(PatchSafetyError, match="compound statement without its body"):
        apply_text_replacement(
            repo_path=repo,
            relative_path="src/rewrite.py",
            old="def _read_pyc(source, pyc):\n    if is_stale(pyc):",
            new=(
                "def _read_pyc(source, pyc):\n"
                "    if source_changed(source, pyc):\n"
                "        return None\n"
                "    return marshal.load(pyc)"
            ),
            reject_python_syntax_errors=True,
        )

    assert target.read_text(encoding="utf-8").splitlines()[1] == "    if is_stale(pyc):"


def test_apply_text_replacement_can_reject_new_unbound_python_names(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "rewrite.py"
    target.write_text(
        "def _rewrite_test(fn, config):\n"
        "    return fn.stat(), compile(fn.read_text(), str(fn), 'exec')\n"
        "\n"
        "class Hook:\n"
        "    def exec_module(self, module):\n"
        "        fn = Path(module.__spec__.origin)\n"
        "        source_stat, co = _rewrite_test(fn, self.config)\n",
        encoding="utf-8",
    )

    with pytest.raises(PatchSafetyError, match="unbound Python name"):
        apply_text_replacement(
            repo_path=repo,
            relative_path="src/rewrite.py",
            old="source_stat, co = _rewrite_test(fn, self.config)",
            new="source_stat, co = _rewrite_test(path, config)",
            reject_python_syntax_errors=True,
            reject_python_unbound_names=True,
        )

    assert "path, config" not in target.read_text(encoding="utf-8")


def test_apply_text_replacement_rejects_removed_import_still_used(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "collector.py"
    target.write_text(
        "from _pytest.pathlib import import_path\n"
        "\n"
        "def collect(path):\n"
        "    return import_path(path)\n",
        encoding="utf-8",
    )

    with pytest.raises(PatchSafetyError, match="`import_path`"):
        apply_text_replacement(
            repo_path=repo,
            relative_path="src/collector.py",
            old="from _pytest.pathlib import import_path\n",
            new="",
            reject_python_syntax_errors=True,
            reject_python_unbound_names=True,
        )

    assert "from _pytest.pathlib import import_path" in target.read_text(encoding="utf-8")


def test_apply_text_replacement_rejects_removed_module_function_still_used(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "rewrite.py"
    old_function = "def _read_pyc(source, pyc):\n    co = marshal.load(pyc)\n    return co\n"
    target.write_text(
        "def _rewrite_test(fn, config):\n"
        "    return fn.stat()\n"
        "\n"
        f"{old_function}"
        "\n"
        "class Hook:\n"
        "    def exec_module(self, module):\n"
        "        co = _read_pyc(module.__file__, module.__cached__)\n",
        encoding="utf-8",
    )

    with pytest.raises(PatchSafetyError, match="`_read_pyc`"):
        apply_text_replacement(
            repo_path=repo,
            relative_path="src/rewrite.py",
            old=old_function,
            new=(
                "    def _read_pyc(source, pyc):\n"
                "        co = marshal.load(pyc)\n"
                "        return co\n"
            ),
            reject_python_syntax_errors=True,
            reject_python_unbound_names=True,
        )

    assert target.read_text(encoding="utf-8").splitlines()[3] == "def _read_pyc(source, pyc):"


def test_apply_text_replacement_rejects_introduced_duplicate_import(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "collector.py"
    target.write_text(
        "from _pytest.pathlib import fnmatch_ex\n"
        "from _pytest.pathlib import import_path\n"
        "from _pytest.pathlib import ImportPathMismatchError\n"
        "from _pytest.pathlib import scandir\n",
        encoding="utf-8",
    )

    with pytest.raises(PatchSafetyError, match="`ImportPathMismatchError`"):
        apply_text_replacement(
            repo_path=repo,
            relative_path="src/collector.py",
            old="from _pytest.pathlib import import_path",
            new=(
                "from _pytest.pathlib import ImportPathMismatchError\n"
                "from _pytest.pathlib import import_path"
            ),
            reject_python_syntax_errors=True,
            reject_python_unbound_names=True,
        )

    assert target.read_text(encoding="utf-8").count("ImportPathMismatchError") == 1


def test_apply_text_replacement_allows_new_nonduplicate_import(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "collector.py"
    target.write_text(
        "from _pytest.pathlib import fnmatch_ex\n"
        "from _pytest.pathlib import import_path\n"
        "from _pytest.pathlib import scandir\n",
        encoding="utf-8",
    )

    apply_text_replacement(
        repo_path=repo,
        relative_path="src/collector.py",
        old="from _pytest.pathlib import import_path",
        new=(
            "from _pytest.pathlib import ImportPathMismatchError\n"
            "from _pytest.pathlib import import_path"
        ),
        reject_python_syntax_errors=True,
        reject_python_unbound_names=True,
    )

    assert target.read_text(encoding="utf-8").count("ImportPathMismatchError") == 1


def test_apply_text_replacement_allows_available_names_in_python_edit(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "rewrite.py"
    target.write_text(
        "def _rewrite_test(fn, config):\n"
        "    return fn.stat(), compile(fn.read_text(), str(fn), 'exec')\n"
        "\n"
        "class Hook:\n"
        "    def exec_module(self, module):\n"
        "        fn = Path(module.__spec__.origin)\n"
        "        source_stat, co = _rewrite_test(fn, self.config)\n",
        encoding="utf-8",
    )

    apply_text_replacement(
        repo_path=repo,
        relative_path="src/rewrite.py",
        old="source_stat, co = _rewrite_test(fn, self.config)",
        new=("source_stat, co = _rewrite_test(fn, self.config)\n        exec(co, module.__dict__)"),
        reject_python_syntax_errors=True,
        reject_python_unbound_names=True,
    )

    assert "exec(co, module.__dict__)" in target.read_text(encoding="utf-8")


def test_apply_text_replacement_allows_helper_defined_in_both_module_branches(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "pathlib.py"
    target.write_text(
        "import sys\n"
        "\n"
        "if sys.platform == 'win32':\n"
        "    def _is_same(left, right):\n"
        "        return left.lower() == right.lower()\n"
        "else:\n"
        "    def _is_same(left, right):\n"
        "        return left == right\n"
        "\n"
        "def import_path(path, module_file):\n"
        "    return module_file\n",
        encoding="utf-8",
    )

    apply_text_replacement(
        repo_path=repo,
        relative_path="src/pathlib.py",
        old="return module_file",
        new=(
            "if _is_same(str(path), module_file):\n        return module_file\n    return str(path)"
        ),
        reject_python_syntax_errors=True,
        reject_python_unbound_names=True,
    )

    assert "_is_same(str(path), module_file)" in target.read_text(encoding="utf-8")


def test_apply_text_replacement_rejects_helper_defined_in_one_module_branch(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "pathlib.py"
    target.write_text(
        "import sys\n"
        "\n"
        "if sys.platform == 'win32':\n"
        "    def _is_same(left, right):\n"
        "        return left.lower() == right.lower()\n"
        "\n"
        "def import_path(path, module_file):\n"
        "    return module_file\n",
        encoding="utf-8",
    )

    with pytest.raises(PatchSafetyError, match="`_is_same`"):
        apply_text_replacement(
            repo_path=repo,
            relative_path="src/pathlib.py",
            old="return module_file",
            new=(
                "if _is_same(str(path), module_file):\n"
                "        return module_file\n"
                "    return str(path)"
            ),
            reject_python_syntax_errors=True,
            reject_python_unbound_names=True,
        )

    assert "_is_same(str(path), module_file)" not in target.read_text(encoding="utf-8")


def test_apply_text_replacement_can_use_nearest_source_span(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "module.py"
    target.write_text(
        "def value(left: int, right: int) -> int:\n    result = left - right\n    return result\n",
        encoding="utf-8",
    )

    edit = apply_text_replacement(
        repo_path=repo,
        relative_path="src/module.py",
        old="def value(left: int, right: int) -> int:\n    return left - right",
        new="def value(left: int, right: int) -> int:\n    return left + right",
        allow_nearest_match=True,
        nearest_match_min_similarity=0.85,
    )

    assert edit.replacement_strategy == "nearest_source_span"
    assert edit.replacement_similarity is not None
    assert edit.replacement_similarity >= 0.85
    assert "return left + right" in target.read_text(encoding="utf-8")
    assert "result = left - right" not in target.read_text(encoding="utf-8")


def test_apply_text_replacement_rejects_low_similarity_nearest_source_span(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "module.py"
    target.write_text("def value():\n    return 1\n", encoding="utf-8")

    with pytest.raises(PatchSafetyError, match="replacement text not found"):
        apply_text_replacement(
            repo_path=repo,
            relative_path="src/module.py",
            old="class CompletelyDifferent:\n    pass",
            new="class CompletelyDifferent:\n    value = 1",
            allow_nearest_match=True,
            nearest_match_min_similarity=0.95,
        )

    assert target.read_text(encoding="utf-8") == "def value():\n    return 1\n"


def test_apply_text_replacement_rejects_unknown_private_self_method_call(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "rewrite.py"
    target.write_text(
        "class Hook:\n    def exec_module(self, module):\n        return module\n",
        encoding="utf-8",
    )

    with pytest.raises(PatchSafetyError, match="`_read_pyc`"):
        apply_text_replacement(
            repo_path=repo,
            relative_path="src/rewrite.py",
            old="return module",
            new="self._read_pyc(module)\n        return module",
            reject_python_syntax_errors=True,
            reject_python_unbound_names=True,
        )

    assert "_read_pyc" not in target.read_text(encoding="utf-8")


def test_apply_text_replacement_allows_existing_private_self_method_call(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "rewrite.py"
    target.write_text(
        "class Hook:\n"
        "    def _read_pyc(self, module):\n"
        "        return None\n"
        "\n"
        "    def exec_module(self, module):\n"
        "        return module\n",
        encoding="utf-8",
    )

    apply_text_replacement(
        repo_path=repo,
        relative_path="src/rewrite.py",
        old="return module",
        new="self._read_pyc(module)\n        return module",
        reject_python_syntax_errors=True,
        reject_python_unbound_names=True,
    )

    assert "self._read_pyc(module)" in target.read_text(encoding="utf-8")


def test_apply_text_replacement_rejects_unknown_private_self_attribute_load(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "rewrite.py"
    target.write_text(
        "class Hook:\n"
        "    def __init__(self):\n"
        "        self._rewritten_names = {}\n"
        "\n"
        "    def exec_module(self, module):\n"
        "        return module\n",
        encoding="utf-8",
    )

    with pytest.raises(PatchSafetyError, match="`_rewrite_names`"):
        apply_text_replacement(
            repo_path=repo,
            relative_path="src/rewrite.py",
            old="return module",
            new="self._rewrite_names[module.__name__] = module\n        return module",
            reject_python_syntax_errors=True,
            reject_python_unbound_names=True,
        )

    assert "_rewrite_names" not in target.read_text(encoding="utf-8")


def test_apply_text_replacement_allows_known_private_self_attribute_load(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "rewrite.py"
    target.write_text(
        "class Hook:\n"
        "    def __init__(self):\n"
        "        self._rewritten_names = {}\n"
        "\n"
        "    def exec_module(self, module):\n"
        "        return module\n",
        encoding="utf-8",
    )

    apply_text_replacement(
        repo_path=repo,
        relative_path="src/rewrite.py",
        old="return module",
        new="self._rewritten_names[module.__name__] = module\n        return module",
        reject_python_syntax_errors=True,
        reject_python_unbound_names=True,
    )

    assert "self._rewritten_names[module.__name__]" in target.read_text(encoding="utf-8")


def test_apply_text_replacement_allows_new_private_self_attribute_assignment(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "rewrite.py"
    target.write_text(
        "class Hook:\n    def exec_module(self, module):\n        return module\n",
        encoding="utf-8",
    )

    apply_text_replacement(
        repo_path=repo,
        relative_path="src/rewrite.py",
        old="return module",
        new="self._rewrite_names = {}\n        return module",
        reject_python_syntax_errors=True,
        reject_python_unbound_names=True,
    )

    assert "self._rewrite_names = {}" in target.read_text(encoding="utf-8")
