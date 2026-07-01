"""Validation and heuristic scoring for the Day 22 control set."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ControlQuestion:
    id: str
    question: str
    expected_points: list[str]
    expected_sources: list[str]


def load_control_questions(path: Path | str) -> list[ControlQuestion]:
    payload: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Control questions must be a JSON array")
    questions: list[ControlQuestion] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("Each control question must be an object")
        question = ControlQuestion(
            id=str(item.get("id", "")).strip(),
            question=str(item.get("question", "")).strip(),
            expected_points=[str(value) for value in item.get("expected_points", [])],
            expected_sources=[str(value) for value in item.get("expected_sources", [])],
        )
        if not all((question.id, question.question, question.expected_points)):
            raise ValueError("Question requires id, question, and expected_points")
        questions.append(question)
    if len({item.id for item in questions}) != len(questions):
        raise ValueError("Control question ids must be unique")
    return questions


def heuristic_point_coverage(answer: str, expected_points: list[str]) -> int:
    """Count points whose meaningful words mostly occur in an answer."""

    answer_words = set(re.findall(r"[\w-]{4,}", answer.casefold()))
    covered = 0
    for point in expected_points:
        words = set(re.findall(r"[\w-]{4,}", point.casefold()))
        if words and len(words & answer_words) / len(words) >= 0.5:
            covered += 1
    return covered
