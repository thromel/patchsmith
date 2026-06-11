"""Evaluation package; public entry points for the evaluation workflows.

Result/summary models live in ``patchsmith.evaluation_models`` and report
renderers in ``patchsmith.evaluation_reports``, ``patchsmith.repair_reports``,
and ``patchsmith.public_issue_reports``.
"""

from __future__ import annotations

from patchsmith.evaluation.issue_corpus.focused_setup_plan import (
    plan_focused_test_setups,
)
from patchsmith.evaluation.issue_corpus.focused_setup_validation import (
    validate_focused_test_setups,
)
from patchsmith.evaluation.issue_corpus.focused_tests import (
    check_focused_test_setup_readiness,
    diagnose_focused_test_runs,
    execute_focused_test_setups,
    plan_materialized_issue_focused_tests,
    run_materialized_issue_focused_tests,
)
from patchsmith.evaluation.issue_corpus.materialize import (
    check_materialized_issue_run_readiness,
    materialize_issue_corpus_tasks,
    validate_materialized_issue_tasks,
)
from patchsmith.evaluation.issue_corpus.preflight import (
    preflight_issue_corpus_repositories,
)
from patchsmith.evaluation.issue_corpus.preview import (
    preview_issue_corpus_context,
)
from patchsmith.evaluation.issue_corpus.public_issue_repairs import (
    check_public_issue_repair_readiness,
    execute_public_issue_repairs,
)
from patchsmith.evaluation.issue_corpus.public_issue_spec_validation import (
    validate_public_issue_reproduction_specs,
)
from patchsmith.evaluation.issue_corpus.public_issues import (
    discover_public_issue_failure_signals,
    execute_public_issue_reproductions,
    plan_public_issue_reproductions,
)
from patchsmith.evaluation.issue_corpus.validate import (
    validate_issue_corpus,
)
from patchsmith.evaluation.metrics import (
    recall,
    top_k_recall,
)
from patchsmith.evaluation.runners.patch_search import run_patch_search_evaluation
from patchsmith.evaluation.runners.repair import run_repair_evaluation
from patchsmith.evaluation.runners.retrieval import run_retrieval_evaluation
from patchsmith.evaluation.runners.scaffold import run_scaffold_comparison
from patchsmith.evaluation.seeded import (
    load_seeded_tasks,
    validate_seeded_dataset,
)

__all__ = [
    "check_focused_test_setup_readiness",
    "check_materialized_issue_run_readiness",
    "check_public_issue_repair_readiness",
    "diagnose_focused_test_runs",
    "discover_public_issue_failure_signals",
    "execute_focused_test_setups",
    "execute_public_issue_repairs",
    "execute_public_issue_reproductions",
    "load_seeded_tasks",
    "materialize_issue_corpus_tasks",
    "plan_focused_test_setups",
    "plan_materialized_issue_focused_tests",
    "plan_public_issue_reproductions",
    "preflight_issue_corpus_repositories",
    "preview_issue_corpus_context",
    "recall",
    "run_materialized_issue_focused_tests",
    "run_patch_search_evaluation",
    "run_repair_evaluation",
    "run_retrieval_evaluation",
    "run_scaffold_comparison",
    "top_k_recall",
    "validate_focused_test_setups",
    "validate_issue_corpus",
    "validate_materialized_issue_tasks",
    "validate_public_issue_reproduction_specs",
    "validate_seeded_dataset",
]
