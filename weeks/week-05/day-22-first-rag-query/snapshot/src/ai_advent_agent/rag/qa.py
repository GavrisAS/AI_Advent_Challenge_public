"""Первый RAG QA pipeline: baseline, retrieval и grounded generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ai_advent_agent.rag.embeddings import EmbeddingBackend
from ai_advent_agent.rag.llm import RagLLM
from ai_advent_agent.rag.prompts import build_baseline_prompt, build_rag_prompt
from ai_advent_agent.rag.search import RetrievedContext, retrieve_context

AnswerMode = Literal["baseline", "rag", "both"]


@dataclass(frozen=True, slots=True)
class AnswerResult:
    question: str
    mode: AnswerMode
    baseline_answer: str | None
    rag_answer: str | None
    retrieved_context: RetrievedContext | None


def answer_question(
    question: str,
    mode: AnswerMode,
    index: list[dict[str, Any]] | None,
    embedder: EmbeddingBackend,
    llm: RagLLM,
    top_k: int = 4,
) -> AnswerResult:
    if mode not in {"baseline", "rag", "both"}:
        raise ValueError("mode must be baseline, rag, or both")
    if not question.strip():
        raise ValueError("question must not be empty")
    needs_rag = mode in {"rag", "both"}
    if needs_rag and index is None:
        raise ValueError("RAG mode requires an index")
    baseline = llm.generate(build_baseline_prompt(question)) if mode != "rag" else None
    context = retrieve_context(index or [], question, embedder, top_k=top_k) if needs_rag else None
    rag = llm.generate(build_rag_prompt(question, context)) if context is not None else None
    return AnswerResult(question, mode, baseline, rag, context)
