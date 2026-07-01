"""Изолированный query rewrite для RAG retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ai_advent_agent.rag.llm import RagLLM

RewriteMode = Literal["none", "heuristic", "llm"]


@dataclass(frozen=True, slots=True)
class QueryRewriteResult:
    original_question: str
    rewritten_query: str
    rewrite_mode: RewriteMode
    added_terms: tuple[str, ...] = ()


_RULES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("проверк", "сдач", "python"),
        (
            "make check",
            "make safety",
            "pytest",
            "py_compile",
            "export_public",
            "check_repo_safety",
            "development rules",
        ),
    ),
    (
        ("day-specific", "сценар", "историческ"),
        (
            "snapshot",
            "historical runner",
            "ai-advent-scenarios",
            "актуальный package",
            "development rules",
        ),
    ),
    (
        ("public export", "публичн", "экспорт"),
        (
            ".tmp",
            ".env",
            ".agent_context",
            "scripts/export_public.py",
            "check_repo_safety",
            "development rules",
        ),
    ),
    (
        ("metadata", "метадан", "chunk"),
        ("chunk_id", "source", "title", "section", "start_line", "end_line"),
    ),
    (
        ("hash", "embedding", "эмбед"),
        ("deterministic fallback", "offline tests", "semantic quality"),
    ),
)


def heuristic_rewrite(question: str) -> QueryRewriteResult:
    """Расширить запрос проектными терминами без сети и случайности."""

    original = question.strip()
    if not original:
        raise ValueError("question must not be empty")
    folded = original.casefold()
    added: list[str] = []
    for triggers, terms in _RULES:
        if any(trigger in folded for trigger in triggers):
            for term in terms:
                if term.casefold() not in folded and term not in added:
                    added.append(term)
    rewritten = " ".join((original, *added))
    return QueryRewriteResult(original, rewritten, "heuristic", tuple(added))


def rewrite_query(
    question: str,
    mode: RewriteMode,
    *,
    llm: RagLLM | None = None,
) -> QueryRewriteResult:
    """Выполнить выбранную стратегию rewrite."""

    original = question.strip()
    if not original:
        raise ValueError("question must not be empty")
    if mode == "none":
        return QueryRewriteResult(original, original, mode)
    if mode == "heuristic":
        return heuristic_rewrite(original)
    if mode != "llm":
        raise ValueError("rewrite mode must be none, heuristic, or llm")
    if llm is None:
        raise ValueError("llm rewrite mode requires an LLM")
    prompt = (
        "Перепиши вопрос в один короткий поисковый запрос для локальной базы проекта. "
        "Сохрани исходный смысл, добавь только полезные технические термины, не отвечай на вопрос."
        f"\n\nВопрос: {original}\n\nПоисковый запрос:"
    )
    rewritten = llm.generate(prompt).strip()
    if not rewritten:
        rewritten = original
    return QueryRewriteResult(original, rewritten, mode)
