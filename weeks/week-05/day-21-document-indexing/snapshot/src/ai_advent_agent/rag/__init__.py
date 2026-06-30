"""Переиспользуемые компоненты локальной индексации документов."""

from ai_advent_agent.rag.chunking import Chunk, chunk_documents_fixed, chunk_documents_structure
from ai_advent_agent.rag.documents import Document, load_documents
from ai_advent_agent.rag.embeddings import HashEmbeddingBackend, OllamaEmbeddingBackend
from ai_advent_agent.rag.search import SearchResult, cosine_similarity, search_index

__all__ = [
    "Chunk",
    "Document",
    "HashEmbeddingBackend",
    "OllamaEmbeddingBackend",
    "SearchResult",
    "chunk_documents_fixed",
    "chunk_documents_structure",
    "cosine_similarity",
    "load_documents",
    "search_index",
]
