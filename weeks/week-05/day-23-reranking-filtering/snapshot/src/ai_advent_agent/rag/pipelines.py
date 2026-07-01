"""Оркестрация plain и improved RAG без смешивания этапов pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai_advent_agent.rag.embeddings import EmbeddingBackend
from ai_advent_agent.rag.llm import RagLLM
from ai_advent_agent.rag.prompts import build_rag_prompt
from ai_advent_agent.rag.query_rewrite import QueryRewriteResult, RewriteMode, rewrite_query
from ai_advent_agent.rag.reranking import RerankMode, RerankResult, rerank_chunks
from ai_advent_agent.rag.search import RetrievedContext, retrieve_context


@dataclass(frozen=True, slots=True)
class PlainRagResult:
    context: RetrievedContext
    answer: str


@dataclass(frozen=True, slots=True)
class ImprovedRagResult:
    rewrite: QueryRewriteResult
    retrieved_before_filter: RetrievedContext
    reranked: RerankResult
    selected_context: RetrievedContext
    answer: str


@dataclass(frozen=True, slots=True)
class RagModeComparison:
    question: str
    plain: PlainRagResult
    improved: ImprovedRagResult


def run_plain_and_improved(
    question: str,
    index: list[dict[str, Any]],
    embedder: EmbeddingBackend,
    llm: RagLLM,
    *,
    plain_top_k: int = 4,
    improved_top_k_before: int = 8,
    improved_top_k_after: int = 4,
    similarity_threshold: float = 0.25,
    rewrite_mode: RewriteMode = "heuristic",
    rerank_mode: RerankMode = "heuristic",
) -> RagModeComparison:
    plain_context = retrieve_context(index, question, embedder, top_k=plain_top_k)
    plain = PlainRagResult(plain_context, llm.generate(build_rag_prompt(question, plain_context)))

    rewrite = rewrite_query(question, rewrite_mode, llm=llm)
    before = retrieve_context(
        index,
        rewrite.rewritten_query,
        embedder,
        top_k=improved_top_k_before,
    )
    reranked = rerank_chunks(
        before.chunks,
        rewrite.rewritten_query,
        mode=rerank_mode,
        similarity_threshold=similarity_threshold,
        top_k_after=improved_top_k_after,
    )
    selected = RetrievedContext(
        question=question,
        chunks=[item.chunk for item in reranked.chunks],
        top_k=improved_top_k_after,
        retrieval_mode=f"rewrite:{rewrite_mode}+rerank:{rerank_mode}",
    )
    improved = ImprovedRagResult(
        rewrite,
        before,
        reranked,
        selected,
        llm.generate(build_rag_prompt(question, selected)),
    )
    return RagModeComparison(question, plain, improved)
