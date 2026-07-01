"""Переиспользуемые компоненты локальной индексации документов."""

from ai_advent_agent.rag.chunking import Chunk, chunk_documents_fixed, chunk_documents_structure
from ai_advent_agent.rag.documents import Document, load_documents
from ai_advent_agent.rag.embeddings import HashEmbeddingBackend, OllamaEmbeddingBackend
from ai_advent_agent.rag.qa import AnswerResult, answer_question
from ai_advent_agent.rag.query_rewrite import QueryRewriteResult, heuristic_rewrite, rewrite_query
from ai_advent_agent.rag.reranking import RerankedChunk, RerankResult, rerank_chunks
from ai_advent_agent.rag.search import (
    RetrievedChunk,
    RetrievedContext,
    SearchResult,
    cosine_similarity,
    retrieve_context,
    search_index,
)

__all__ = [
    "AnswerResult",
    "Chunk",
    "Document",
    "HashEmbeddingBackend",
    "OllamaEmbeddingBackend",
    "QueryRewriteResult",
    "RerankResult",
    "RerankedChunk",
    "RetrievedChunk",
    "RetrievedContext",
    "SearchResult",
    "answer_question",
    "chunk_documents_fixed",
    "chunk_documents_structure",
    "cosine_similarity",
    "heuristic_rewrite",
    "load_documents",
    "rerank_chunks",
    "retrieve_context",
    "rewrite_query",
    "search_index",
]
