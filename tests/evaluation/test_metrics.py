from patchsmith.evaluation import recall, top_k_recall


def test_recall_metrics() -> None:
    assert top_k_recall(["src/a.py", "src/b.py"], ["src/a.py"], 1) == 1.0
    assert top_k_recall(["src/b.py", "src/a.py"], ["src/a.py"], 1) == 0.0
    assert top_k_recall(["src/b.py", "src/a.py"], ["src/a.py"], 3) == 1.0
    assert recall(["tests/test_a.py"], ["tests/test_a.py", "tests/test_b.py"]) == 0.5
