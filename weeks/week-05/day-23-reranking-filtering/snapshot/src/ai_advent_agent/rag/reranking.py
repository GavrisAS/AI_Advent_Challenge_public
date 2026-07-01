"""Фильтрация и объяснимый heuristic reranking retrieved chunks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from ai_advent_agent.rag.search import RetrievedChunk

RerankMode = Literal["none", "similarity_threshold", "heuristic"]
_TOKEN_RE = re.compile(r"[\w.-]{3,}", re.UNICODE)
_STOP_WORDS = {
    "как",
    "что",
    "для",
    "или",
    "это",
    "какие",
    "почему",
    "нужно",
    "должны",
    "после",
    "перед",
    "with",
    "from",
    "the",
}


@dataclass(frozen=True, slots=True)
class ScoreComponents:
    similarity_score: float
    source_bonus: float
    section_bonus: float
    keyword_bonus: float

    @property
    def final_score(self) -> float:
        return self.similarity_score + self.source_bonus + self.section_bonus + self.keyword_bonus


@dataclass(frozen=True, slots=True)
class RerankedChunk:
    chunk: RetrievedChunk
    components: ScoreComponents

    @property
    def final_score(self) -> float:
        return self.components.final_score


@dataclass(frozen=True, slots=True)
class RerankResult:
    chunks: list[RerankedChunk]
    fallback_used: bool
    rejected_chunk_ids: tuple[str, ...]
    mode: RerankMode
    similarity_threshold: float
    top_k_after: int


def _keywords(text: str) -> set[str]:
    return {
        token.casefold() for token in _TOKEN_RE.findall(text) if token.casefold() not in _STOP_WORDS
    }


def _score(chunk: RetrievedChunk, query: str, mode: RerankMode) -> ScoreComponents:
    if mode != "heuristic":
        return ScoreComponents(chunk.score, 0.0, 0.0, 0.0)
    query_terms = _keywords(query)
    source_hits = len(query_terms & _keywords(chunk.source))
    section_hits = len(query_terms & _keywords(f"{chunk.title} {chunk.section}"))
    text_hits = len(query_terms & _keywords(chunk.text))
    denominator = max(1, min(len(query_terms), 12))
    return ScoreComponents(
        similarity_score=chunk.score,
        source_bonus=min(0.06, source_hits * 0.02),
        section_bonus=min(0.10, section_hits * 0.025),
        keyword_bonus=min(0.18, text_hits / denominator * 0.18),
    )


def rerank_chunks(
    chunks: list[RetrievedChunk],
    query: str,
    *,
    mode: RerankMode = "heuristic",
    similarity_threshold: float = 0.25,
    top_k_after: int = 4,
) -> RerankResult:
    """Применить threshold, reranking и непустой fallback."""

    if mode not in {"none", "similarity_threshold", "heuristic"}:
        raise ValueError("rerank mode must be none, similarity_threshold, or heuristic")
    if top_k_after <= 0:
        raise ValueError("top_k_after must be positive")
    if not -1.0 <= similarity_threshold <= 1.0:
        raise ValueError("similarity_threshold must be between -1 and 1")
    scored = [_score(chunk, query, mode) for chunk in chunks]
    pairs = [
        RerankedChunk(chunk, components) for chunk, components in zip(chunks, scored, strict=True)
    ]
    if mode == "none":
        accepted = pairs
    else:
        accepted = [
            item for item in pairs if item.components.similarity_score >= similarity_threshold
        ]
    rejected = tuple(item.chunk.chunk_id for item in pairs if item not in accepted)
    fallback_used = bool(pairs) and not accepted
    if fallback_used:
        accepted = [
            max(pairs, key=lambda item: (item.components.similarity_score, item.chunk.chunk_id))
        ]
    if mode == "heuristic":
        accepted.sort(key=lambda item: (-item.final_score, item.chunk.chunk_id))
    else:
        accepted.sort(key=lambda item: (-item.components.similarity_score, item.chunk.chunk_id))
    return RerankResult(
        chunks=accepted[:top_k_after],
        fallback_used=fallback_used,
        rejected_chunk_ids=rejected,
        mode=mode,
        similarity_threshold=similarity_threshold,
        top_k_after=top_k_after,
    )
