from __future__ import annotations

import pytest

from patchsmith.models import RetrievedContext
from patchsmith.target_localization import target_localization_candidates

pytestmark = pytest.mark.unit


def _context(
    path: str,
    excerpt: str,
    *,
    score: float = 1.0,
    matched_terms: list[str] | None = None,
) -> RetrievedContext:
    return RetrievedContext(
        path=path,
        rank=1,
        score=score,
        method="native_hybrid",
        matched_terms=matched_terms or [],
        excerpt=excerpt,
    )


def test_target_localization_ranks_import_cache_source_target_over_raw_order() -> None:
    issue = (
        "Moving a test module leaves stale co_filename in f_code because pytest "
        "reuses an import cache instead of recompiling the renamed path."
    )
    candidates = target_localization_candidates(
        issue_text=issue,
        retrieved_context=[
            _context(
                "src/_pytest/python.py",
                "def pytest_pycollect_makemodule(module_path):\n    return import_path(module_path)\n",
            ),
            _context(
                "docs/example.py",
                "Documentation mentioning co_filename and sys.modules.",
            ),
            _context(
                "tests/test_collection.py",
                "assert item.location[0].endswith('test_foo.py')",
            ),
            _context(
                "src/_pytest/pathlib.py",
                "module_name = module_name_from_path(path)\n"
                "with contextlib.suppress(KeyError):\n"
                "    return sys.modules[module_name]\n"
                "return importlib.import_module(module_name)\n",
            ),
            _context(
                "src/_pytest/assertion/rewrite.py",
                "def _read_pyc(source, pyc):\n    co = marshal.load(fp)\n    return co\n",
            ),
        ],
    )

    assert candidates[0].path == "src/_pytest/assertion/rewrite.py"
    assert {candidate.path for candidate in candidates[1:]} == {
        "src/_pytest/pathlib.py",
        "src/_pytest/python.py",
    }
    assert "stale_code_object_control_point" in ";".join(candidates[0].reasons)


def test_target_localization_excludes_historical_targets_by_default() -> None:
    issue = "stale co_filename after renamed module path uses cached import state"
    candidates = target_localization_candidates(
        issue_text=issue,
        historical_paths=["src/_pytest/pathlib.py"],
        retrieved_context=[
            _context(
                "src/_pytest/pathlib.py",
                "return sys.modules[module_name]\n",
            ),
            _context(
                "src/_pytest/assertion/rewrite.py",
                "def _read_pyc(source, pyc):\n    return co\n",
            ),
        ],
    )

    assert [candidate.path for candidate in candidates] == [
        "src/_pytest/assertion/rewrite.py",
    ]


def test_target_localization_can_include_historical_targets_after_new_targets() -> None:
    issue = "stale co_filename after renamed module path uses cached import state"
    candidates = target_localization_candidates(
        issue_text=issue,
        historical_paths=["src/_pytest/pathlib.py"],
        include_historical=True,
        retrieved_context=[
            _context(
                "src/_pytest/pathlib.py",
                "module_name = module_name_from_path(path)\nreturn sys.modules[module_name]\n",
            ),
            _context(
                "src/_pytest/assertion/rewrite.py",
                "def _read_pyc(source, pyc):\n    return co\n",
            ),
        ],
    )

    assert [candidate.path for candidate in candidates] == [
        "src/_pytest/assertion/rewrite.py",
        "src/_pytest/pathlib.py",
    ]
    assert candidates[1].historical is True
    assert "historical_retry_penalty" in candidates[1].reasons


def test_target_localization_prefers_stale_path_control_point_on_retry() -> None:
    issue = (
        "Retry diagnosis: the previous patch only invalidated importlib caches, "
        "but the sandbox still reported the stale path mismatch. Move the repair "
        "to the branch that directly returns the old path."
    )
    candidates = target_localization_candidates(
        issue_text=issue,
        retrieved_context=[
            _context(
                "src/_pytest/pytester.py",
                "def copy_example(self, name):\n"
                "    shutil.copy(example_path, result)\n"
                "    importlib.invalidate_caches()\n"
                "    return result\n",
                score=30.0,
            ),
            _context(
                "src/_pytest/assertion/rewrite.py",
                "def _read_pyc(source, pyc):\n"
                "    co = marshal.load(fp)\n"
                "    if co.co_filename != str(source):\n"
                "        return None\n"
                "    return co\n",
                score=1.0,
            ),
            _context(
                "src/_pytest/pathlib.py",
                "with contextlib.suppress(KeyError):\n    return sys.modules[module_name]\n",
                score=1.0,
            ),
        ],
    )

    assert candidates[0].path == "src/_pytest/assertion/rewrite.py"
    assert "stale_path_control_point_cues" in ";".join(candidates[0].reasons)
    pytester = next(candidate for candidate in candidates if candidate.path.endswith("pytester.py"))
    assert "late_cache_side_effect_penalty" in ";".join(pytester.reasons)


def test_target_localization_prefers_symbol_control_point_over_generic_retry_noise() -> None:
    issue = (
        "Retry diagnosis: the sandbox still reported the stale path mismatch. "
        "Prefer `_read_pyc`, bytecode cache validation, `compile`, or `exec`; "
        "avoid metadata-only co_filename rewrites and generic config handling."
    )
    noisy_terms = [
        "__file__",
        "__future__",
        "_pytest",
        "actual",
        "added",
        "already",
        "assert",
        "assertion",
        "before",
        "cache",
        "co_filename",
        "compile",
        "config",
        "expected",
        "file",
        "filename",
        "import",
        "module",
        "path",
        "pytest",
        "source",
        "stale",
        "test",
    ]
    candidates = target_localization_candidates(
        issue_text=issue,
        historical_paths=["src/_pytest/assertion/rewrite.py"],
        include_historical=True,
        retrieved_context=[
            _context(
                "src/_pytest/config/__init__.py",
                "def parse(args):\n    if cached and co_filename:\n        return config\n",
                score=40.0,
                matched_terms=noisy_terms,
            ),
            _context(
                "src/_pytest/assertion/rewrite.py",
                "def _read_pyc(source, pyc):\n"
                "    co = marshal.load(fp)\n"
                "    if co.co_filename != str(source):\n"
                "        return None\n"
                "    return co\n",
                score=1.0,
                matched_terms=["reviewed_source_hint", "symbol:_read_pyc", "co_filename"],
            ),
        ],
    )

    assert candidates[0].path == "src/_pytest/assertion/rewrite.py"
    assert candidates[0].historical is True
    assert "symbol_identifiers:_read_pyc" in ";".join(candidates[0].reasons)


def test_target_localization_revives_reviewed_source_hint_with_exact_identifier() -> None:
    issue = (
        "The reproduction imports ChunkedEncodingError and asserts its __doc__ "
        "mentions transient connection resets."
    )
    candidates = target_localization_candidates(
        issue_text=issue,
        historical_paths=["src/requests/exceptions.py"],
        include_historical=True,
        retrieved_context=[
            _context(
                "src/requests/models.py",
                "def iter_content(self, chunk_size=1, decode_unicode=False):\n"
                "    for chunk in self.raw.stream(chunk_size, decode_content=True):\n"
                "        yield chunk\n",
                score=40.0,
                matched_terms=["chunked", "connection", "transient"],
            ),
            _context(
                "src/requests/exceptions.py",
                "class ChunkedEncodingError(RequestException):\n"
                '    """The server declared chunked encoding but sent an invalid chunk."""\n',
                score=1.0,
                matched_terms=[
                    "reviewed_source_hint",
                    "chunkedencodingerror",
                    "connection",
                ],
            ),
        ],
    )

    assert candidates[0].path == "src/requests/exceptions.py"
    assert candidates[0].historical is True
    reasons = ";".join(candidates[0].reasons)
    assert "reviewed_source_hint" in reasons
    assert "exact_identifiers:chunkedencodingerror" in reasons
