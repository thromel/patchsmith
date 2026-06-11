from patchsmith.evaluation import (
    RepairEvalResult,
    recall,
    render_public_issue_reproduction_plan_report,
    render_repair_eval_report,
    render_retrieval_eval_report,
    top_k_recall,
)
from patchsmith.evaluation_models import RepairEvalResult as EvaluationModelsRepairEvalResult
from patchsmith.evaluation_reports import (
    render_retrieval_eval_report as evaluation_reports_render_retrieval_eval_report,
)
from patchsmith.public_issue_reports import (
    render_public_issue_reproduction_plan_report as public_issue_reports_render_public_issue_reproduction_plan_report,
)
from patchsmith.repair_reports import (
    render_repair_eval_report as repair_reports_render_repair_eval_report,
)


def test_recall_metrics() -> None:
    assert top_k_recall(["src/a.py", "src/b.py"], ["src/a.py"], 1) == 1.0
    assert top_k_recall(["src/b.py", "src/a.py"], ["src/a.py"], 1) == 0.0
    assert top_k_recall(["src/b.py", "src/a.py"], ["src/a.py"], 3) == 1.0
    assert recall(["tests/test_a.py"], ["tests/test_a.py", "tests/test_b.py"]) == 0.5


def test_evaluation_reexports_result_models() -> None:
    assert RepairEvalResult is EvaluationModelsRepairEvalResult


def test_evaluation_reexports_public_issue_report_renderers() -> None:
    assert (
        render_public_issue_reproduction_plan_report
        is public_issue_reports_render_public_issue_reproduction_plan_report
    )


def test_evaluation_reexports_repair_report_renderers() -> None:
    assert render_repair_eval_report is repair_reports_render_repair_eval_report


def test_evaluation_reexports_evaluation_report_renderers() -> None:
    assert render_retrieval_eval_report is evaluation_reports_render_retrieval_eval_report
