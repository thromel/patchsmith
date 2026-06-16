from __future__ import annotations

import pytest

from patchsmith.patch_quality import assess_diff_quality, assess_patch_quality
from patchsmith.planning import RepairPlan

pytestmark = pytest.mark.unit


def test_assess_patch_quality_marks_simple_source_fix_low_risk() -> None:
    assessment = assess_patch_quality(
        RepairPlan(
            name="simple",
            path="src/calc.py",
            old="return left - right",
            new="return left + right",
            summary="Fix addition.",
        )
    )

    assert assessment.severity == "low"
    assert assessment.score == 0
    assert assessment.findings == ()


def test_assess_patch_quality_flags_docstring_semantic_regression() -> None:
    assessment = assess_patch_quality(
        RepairPlan(
            name="doc_overfit",
            path="src/requests/exceptions.py",
            old='"""The server declared chunked encoding but sent an invalid chunk."""',
            new=(
                '"""This exception is raised when a chunked transfer-encoding '
                'response is interrupted by a transient connection reset."""'
            ),
            summary="Mention transient resets.",
        )
    )

    assert assessment.severity == "high"
    assert assessment.findings[0].code == "documentation_semantic_regression"


def test_assess_patch_quality_allows_additive_docstring_repair() -> None:
    assessment = assess_patch_quality(
        RepairPlan(
            name="doc_additive",
            path="src/requests/exceptions.py",
            old='"""The server declared chunked encoding but sent an invalid chunk."""',
            new=(
                '"""The server declared chunked encoding but sent an invalid chunk.\n\n'
                "This can also surface from transient connection resets while reading a "
                'chunked response."""'
            ),
            summary="Mention transient resets.",
        )
    )

    assert assessment.severity == "low"
    assert assessment.findings == ()


def test_assess_diff_quality_flags_docstring_semantic_regression() -> None:
    diff = """diff --git a/src/requests/exceptions.py b/src/requests/exceptions.py
--- a/src/requests/exceptions.py
+++ b/src/requests/exceptions.py
@@ -130,7 +130,8 @@
-    \"\"\"The server declared chunked encoding but sent an invalid chunk.\"\"\"
+    \"\"\"This exception is raised when a chunked transfer-encoding response is
+    interrupted by a transient connection reset.\"\"\"
"""

    assessment = assess_diff_quality(diff)

    assert assessment.severity == "high"
    assert assessment.findings[0].code == "documentation_semantic_regression"


def test_assess_diff_quality_downgrades_stale_comment_changes_with_code_fix() -> None:
    diff = """diff --git a/pricing.py b/pricing.py
--- a/pricing.py
+++ b/pricing.py
@@ -3,6 +3,7 @@ from discounts import bulk_discount_rate
 def checkout_total(items):
     subtotal = sum(item["unit_price"] * item["quantity"] for item in items)
-    # BUG: this uses the number of line items, not the total quantity bought.
-    discount = bulk_discount_rate(len(items))
+    # Compute total units across all line items so bulk discounts apply to unit counts.
+    total_units = sum(item["quantity"] for item in items)
+    discount = bulk_discount_rate(total_units)
     return round(subtotal * (1 - discount), 2)
"""

    assessment = assess_diff_quality(diff)

    assert assessment.severity == "medium"
    assert assessment.findings[0].code == "documentation_semantic_regression"
    assert assessment.findings[0].severity == "medium"


def test_assess_patch_quality_flags_broad_code_object_patch() -> None:
    new = (
        "@hookimpl(trylast=True)\n"
        "def pytest_pyfunc_call(pyfuncitem: Function) -> object | None:\n"
        "    testfunction = pyfuncitem.obj\n"
        "    try:\n"
        "        co = testfunction.__code__\n"
        '        filename = getattr(pyfuncitem, "fspath", None)\n'
        "        if co.co_filename != filename:\n"
        "            try:\n"
        "                testfunction.__code__ = co.replace(co_filename=str(filename))\n"
        "            except Exception:\n"
        "                try:\n"
        "                    testfunction.__code__ = types.CodeType(\n"
        "                        co.co_argcount, co.co_posonlyargcount, co.co_kwonlyargcount,\n"
        "                        co.co_nlocals, co.co_stacksize, co.co_flags, co.co_code,\n"
        "                        co.co_consts, co.co_names, co.co_varnames, str(filename),\n"
        "                        co.co_name, co.co_firstlineno, co.co_lnotab,\n"
        "                        co.co_freevars, co.co_cellvars,\n"
        "                    )\n"
        "                except Exception:\n"
        "                    pass\n"
        "    except Exception:\n"
        "        pass  # best-effort fallback; not critical\n"
        "    return None\n"
    )

    assessment = assess_patch_quality(
        RepairPlan(
            name="broad",
            path="src/_pytest/python.py",
            old="@hookimpl(trylast=True)\ndef pytest_pyfunc_call(pyfuncitem):\n    testfunction = pyfuncitem.obj",
            new=new,
            summary="Update co_filename before test call.",
        )
    )

    assert assessment.severity == "high"
    codes = {finding.code for finding in assessment.findings}
    assert {
        "moderate_replacement",
        "broad_exception_swallow",
        "code_object_mutation",
        "manual_code_type_rebuild",
        "filename_metadata_rewrite",
        "best_effort_fallback",
    } <= codes


def test_assess_patch_quality_allows_code_type_checks_and_filename_comparisons() -> None:
    old = (
        "if not isinstance(co, types.CodeType):\n"
        '    trace(f"_read_pyc({source}): not a code object")\n'
        "    return None\n"
        "return co"
    )
    new = (
        "if not isinstance(co, types.CodeType):\n"
        '    trace(f"_read_pyc({source}): not a code object")\n'
        "    return None\n"
        "if co.co_filename != str(source):\n"
        '    trace(f"_read_pyc({source}): stale co_filename {co.co_filename}")\n'
        "    return None\n"
        "return co"
    )

    assessment = assess_patch_quality(
        RepairPlan(
            name="invalidate_stale_pyc",
            path="src/_pytest/assertion/rewrite.py",
            old=old,
            new=new,
            summary="Invalidate pyc cache entries with stale filenames.",
        )
    )

    assert assessment.severity == "low"
    assert assessment.findings == ()


def test_assess_patch_quality_flags_dead_branch_source_recompile() -> None:
    old = (
        "if not isinstance(co, types.CodeType):\n"
        '    trace(f"_read_pyc({source}): not a code object")\n'
        "    return None\n"
        "return co"
    )
    new = (
        "if not isinstance(co, types.CodeType):\n"
        '    trace(f"_read_pyc({source}): not a code object")\n'
        "    return None\n"
        "return compile(\n"
        "    co.co_consts[0] if False else source.read_text(encoding='utf-8'),\n"
        "    str(source),\n"
        "    'exec',\n"
        "    dont_inherit=True,\n"
        ")"
    )

    assessment = assess_patch_quality(
        RepairPlan(
            name="recompile_source_text",
            path="src/_pytest/assertion/rewrite.py",
            old=old,
            new=new,
            summary="Recompile moved file source directly.",
        )
    )

    assert assessment.severity == "high"
    codes = {finding.code for finding in assessment.findings}
    assert {"constant_boolean_branch", "source_text_recompile"} <= codes


def test_assess_patch_quality_allows_edits_inside_existing_broad_handler() -> None:
    old = (
        "try:\n"
        '    fp = open(pyc, "rb")\n'
        "    co = marshal.load(fp)\n"
        "    if not isinstance(co, types.CodeType):\n"
        '        trace(f"_read_pyc({source}): not a code object")\n'
        "        return None\n"
        "    return co\n"
        "except Exception:\n"
        "    return None"
    )
    new = (
        "try:\n"
        '    fp = open(pyc, "rb")\n'
        "    co = marshal.load(fp)\n"
        "    if not isinstance(co, types.CodeType):\n"
        '        trace(f"_read_pyc({source}): not a code object")\n'
        "        return None\n"
        "    if co.co_filename != str(source):\n"
        '        trace(f"_read_pyc({source}): stale co_filename {co.co_filename!r}")\n'
        "        return None\n"
        "    return co\n"
        "except Exception:\n"
        "    return None"
    )

    assessment = assess_patch_quality(
        RepairPlan(
            name="invalidate_stale_pyc_inside_existing_handler",
            path="src/_pytest/assertion/rewrite.py",
            old=old,
            new=new,
            summary="Invalidate stale pyc entries without adding exception swallowing.",
        )
    )

    assert assessment.severity == "low"
    assert assessment.findings == ()


def test_assess_patch_quality_flags_bare_except_swallowing() -> None:
    assessment = assess_patch_quality(
        RepairPlan(
            name="bare_except",
            path="src/loader.py",
            old="value = load(path)\nreturn value",
            new=("try:\n    value = load(path)\nexcept:\n    pass\nreturn value"),
            summary="Ignore loader failures.",
        )
    )

    assert assessment.severity == "high"
    assert assessment.findings[0].code == "broad_exception_swallow"


def test_assess_patch_quality_flags_broad_exception_return_fallback() -> None:
    assessment = assess_patch_quality(
        RepairPlan(
            name="return_fallback",
            path="src/loader.py",
            old="return load_current(path)",
            new=(
                "try:\n"
                "    return load_current(path)\n"
                "except Exception:\n"
                "    return load_cached(path)"
            ),
            summary="Fall back to cached data.",
        )
    )

    assert assessment.severity == "high"
    assert assessment.findings[0].code == "broad_exception_swallow"


def test_assess_patch_quality_allows_broad_exception_reraise() -> None:
    assessment = assess_patch_quality(
        RepairPlan(
            name="reraises",
            path="src/loader.py",
            old="return load_current(path)",
            new=("try:\n    return load_current(path)\nexcept Exception:\n    raise"),
            summary="Keep broad handler behavior explicit.",
        )
    )

    assert "broad_exception_swallow" not in {finding.code for finding in assessment.findings}


def test_assess_patch_quality_flags_module_file_metadata_rewrite() -> None:
    old = (
        'if modfile.endswith(os.sep + "__init__.py"):\n'
        '    if self.basename != "__init__.py":\n'
        "        modfile = modfile[:-12]\n"
        "try:\n"
        "    issame = self.samefile(modfile)\n"
    )
    new = (
        'if modfile.endswith(os.sep + "__init__.py"):\n'
        '    if self.basename != "__init__.py":\n'
        "        modfile = modfile[:-12]\n"
        "if modfile != str(self):\n"
        "    mod.__file__ = str(self)\n"
        "    modfile = mod.__file__\n"
        "try:\n"
        "    issame = self.samefile(modfile)\n"
    )

    assessment = assess_patch_quality(
        RepairPlan(
            name="rewrite_module_file",
            path="src/_pytest/_py/path.py",
            old=old,
            new=new,
            summary="Update module file metadata after moving a test file.",
        )
    )

    assert assessment.severity == "medium"
    assert assessment.findings[0].code == "module_file_metadata_rewrite"


def test_assess_patch_quality_flags_naked_import_cache_invalidation() -> None:
    old = (
        "elif example_path.is_file():\n"
        "    result = self.path.joinpath(example_path.name)\n"
        "    shutil.copy(example_path, result)\n"
        "    return result\n"
    )
    new = (
        "elif example_path.is_file():\n"
        "    result = self.path.joinpath(example_path.name)\n"
        "    shutil.copy(example_path, result)\n"
        "    import importlib\n"
        "\n"
        "    importlib.invalidate_caches()\n"
        "    return result\n"
    )

    assessment = assess_patch_quality(
        RepairPlan(
            name="naked_import_cache_invalidation",
            path="src/_pytest/pytester.py",
            old=old,
            new=new,
            summary="Invalidate importlib caches after copying an example file.",
        )
    )

    assert assessment.severity == "medium"
    assert assessment.findings[0].code == "naked_import_cache_invalidation"


def test_assess_patch_quality_allows_cache_invalidation_with_real_guard() -> None:
    old = "if cache_key in self._cache:\n    return self._cache[cache_key]\n"
    new = (
        "if cache_key in self._cache:\n"
        "    cached = self._cache[cache_key]\n"
        "    if cached.path == path:\n"
        "        return cached\n"
        "    importlib.invalidate_caches()\n"
    )

    assessment = assess_patch_quality(
        RepairPlan(
            name="guarded_cache_invalidation",
            path="src/importer.py",
            old=old,
            new=new,
            summary="Invalidate stale cache only after a path mismatch.",
        )
    )

    assert "naked_import_cache_invalidation" not in {
        finding.code for finding in assessment.findings
    }


def test_assess_patch_quality_flags_test_target_patch() -> None:
    assessment = assess_patch_quality(
        RepairPlan(
            name="test_edit",
            path="tests/test_calc.py",
            old="assert add(1, 2) == 2",
            new="assert add(1, 2) == 3",
            summary="Edit failing expectation.",
        )
    )

    assert assessment.severity == "high"
    assert assessment.findings[0].code == "test_target_patch"


def test_assess_diff_quality_flags_broad_added_code() -> None:
    diff = """diff --git a/src/_pytest/python.py b/src/_pytest/python.py
--- a/src/_pytest/python.py
+++ b/src/_pytest/python.py
@@ -160,3 +160,20 @@
 def pytest_pyfunc_call(pyfuncitem):
     testfunction = pyfuncitem.obj
+    try:
+        co = testfunction.__code__
+        if co.co_filename != filename:
+            try:
+                testfunction.__code__ = co.replace(co_filename=str(filename))
+            except Exception:
+                try:
+                    testfunction.__code__ = types.CodeType(
+                        co.co_argcount, co.co_posonlyargcount, co.co_kwonlyargcount,
+                        co.co_nlocals, co.co_stacksize, co.co_flags, co.co_code,
+                        co.co_consts, co.co_names, co.co_varnames, str(filename),
+                        co.co_name, co.co_firstlineno, co.co_lnotab,
+                        co.co_freevars, co.co_cellvars,
+                    )
+                except Exception:
+                    pass
+    except Exception:
+        pass
     return None
"""

    assessment = assess_diff_quality(diff)

    assert assessment.severity == "high"
    codes = {finding.code for finding in assessment.findings}
    assert "code_object_mutation" in codes
    assert "broad_exception_swallow" in codes


def test_assess_diff_quality_flags_module_file_metadata_rewrite() -> None:
    diff = """diff --git a/src/_pytest/_py/path.py b/src/_pytest/_py/path.py
--- a/src/_pytest/_py/path.py
+++ b/src/_pytest/_py/path.py
@@ -1129,6 +1129,9 @@
             if modfile.endswith(os.sep + "__init__.py"):
                 if self.basename != "__init__.py":
                     modfile = modfile[:-12]
+            if modfile != str(self):
+                mod.__file__ = str(self)
+                modfile = mod.__file__
             try:
                 issame = self.samefile(modfile)
"""

    assessment = assess_diff_quality(diff)

    assert assessment.severity == "medium"
    assert assessment.findings[0].code == "module_file_metadata_rewrite"


def test_assess_diff_quality_flags_naked_import_cache_invalidation() -> None:
    diff = """diff --git a/src/_pytest/pytester.py b/src/_pytest/pytester.py
--- a/src/_pytest/pytester.py
+++ b/src/_pytest/pytester.py
@@ -984,6 +984,9 @@
         elif example_path.is_file():
             result = self.path.joinpath(example_path.name)
             shutil.copy(example_path, result)
+            import importlib
+
+            importlib.invalidate_caches()
             return result
"""

    assessment = assess_diff_quality(diff)

    assert assessment.severity == "medium"
    assert assessment.findings[0].code == "naked_import_cache_invalidation"


def test_assess_diff_quality_flags_dead_branch_source_recompile() -> None:
    diff = """diff --git a/src/_pytest/assertion/rewrite.py b/src/_pytest/assertion/rewrite.py
--- a/src/_pytest/assertion/rewrite.py
+++ b/src/_pytest/assertion/rewrite.py
@@ -397,7 +397,7 @@ def _read_pyc(
         if not isinstance(co, types.CodeType):
             trace(f"_read_pyc({source}): not a code object")
             return None
-        return co
+        return compile(co.co_consts[0] if False else source.read_text(encoding='utf-8'), str(source), 'exec', dont_inherit=True)
"""

    assessment = assess_diff_quality(diff)

    assert assessment.severity == "high"
    codes = {finding.code for finding in assessment.findings}
    assert {"constant_boolean_branch", "source_text_recompile"} <= codes
