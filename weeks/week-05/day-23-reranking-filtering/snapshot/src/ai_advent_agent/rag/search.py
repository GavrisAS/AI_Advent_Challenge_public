"""Cosine similarity retrieval поверх локальных индексных записей."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ai_advent_agent.rag.embeddings import EmbeddingBackend


@dataclass(frozen=True, slots=True)
class SearchResult:
    chunk_id: str
    score: float
    text: str
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk_id: str
    score: float
    source: str
    title: str
    section: str
    text: str
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RetrievedContext:
    question: str
    chunks: list[RetrievedChunk]
    top_k: int
    retrieval_mode: str = "plain_top_k"


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Embedding dimensions do not match")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def search_index(
    chunks: list[dict[str, Any]],
    query: str,
    backend: EmbeddingBackend,
    *,
    top_k: int = 3,
) -> list[SearchResult]:
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    query_vector = backend.embed([query])[0]
    results = [
        SearchResult(
            chunk_id=str(item["chunk_id"]),
            score=cosine_similarity(query_vector, [float(value) for value in item["embedding"]]),
            text=str(item["text"]),
            metadata=dict(item["metadata"]),
        )
        for item in chunks
    ]
    return sorted(results, key=lambda result: (-result.score, result.chunk_id))[:top_k]


def retrieve_context(
    chunks: list[dict[str, Any]],
    question: str,
    backend: EmbeddingBackend,
    *,
    top_k: int = 4,
) -> RetrievedContext:
    """Retrieve plain top-k context; Day 23 can insert filtering after this stage."""

    found = search_index(chunks, question, backend, top_k=top_k)
    return RetrievedContext(
        question=question,
        top_k=top_k,
        chunks=[
            RetrievedChunk(
                chunk_id=item.chunk_id,
                score=item.score,
                source=str(item.metadata.get("source", "")),
                title=str(item.metadata.get("title", "")),
                section=str(item.metadata.get("section", "")),
                text=item.text,
                metadata=item.metadata,
            )
            for item in found
        ],
    )
