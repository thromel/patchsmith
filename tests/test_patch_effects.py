from patchsmith.patch_effects import (
    diff_changes_only_python_imports,
    replacement_changes_only_python_imports,
    text_mentions_import_resolution_failure,
)


def test_replacement_changes_only_python_imports_detects_import_only_edit() -> None:
    assert replacement_changes_only_python_imports(
        old="from pathlib import Path",
        new="import re\nfrom pathlib import Path",
    )


def test_replacement_changes_only_python_imports_rejects_behavior_edit() -> None:
    assert not replacement_changes_only_python_imports(
        old="return left - right",
        new="return left + right",
    )


def test_diff_changes_only_python_imports_detects_import_only_diff() -> None:
    diff = "\n".join(
        [
            "diff --git a/src/module.py b/src/module.py",
            "@@ -1 +1,2 @@",
            "+import re",
            " from pathlib import Path",
        ]
    )

    assert diff_changes_only_python_imports(diff)


def test_text_mentions_import_resolution_failure_accepts_exact_failure_markers() -> None:
    assert text_mentions_import_resolution_failure("NameError: name 're' is not defined")
    assert text_mentions_import_resolution_failure("ModuleNotFoundError: No module named x")
    assert not text_mentions_import_resolution_failure("AssertionError: stale co_filename")
