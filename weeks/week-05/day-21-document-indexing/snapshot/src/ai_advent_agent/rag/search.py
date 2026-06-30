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
