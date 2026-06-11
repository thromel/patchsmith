"""Evaluation metrics (split from evaluation.py)."""

from __future__ import annotations


def top_k_recall(retrieved: list[str], expected: list[str], k: int) -> float:
    if not expected:
        return 1.0
    return recall(retrieved[:k], expected)


def recall(retrieved: list[str], expected: list[str]) -> float:
    if not expected:
        return 1.0
    retrieved_set = set(retrieved)
    expected_set = set(expected)
    return len(retrieved_set & expected_set) / len(expected_set)
