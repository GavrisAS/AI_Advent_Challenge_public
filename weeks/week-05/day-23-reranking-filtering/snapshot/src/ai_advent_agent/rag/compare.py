"""Построение локальных индексов и сравнительного отчёта chunking strategies."""

from __future__ import annotations

import json
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_advent_agent.rag.chunking import (
    Chunk,
    chunk_documents_fixed,
    chunk_documents_structure,
)
from ai_advent_agent.rag.documents import Document, load_documents
from ai_advent_agent.rag.embeddings import EmbeddingBackend
from ai_advent_agent.rag.index_store import save_json_index, save_sqlite_index
from ai_advent_agent.rag.search import search_index

DEFAULT_SAMPLE_QUERIES = (
    "Как запускать historical day-specific сценарии?",
    "Какие правила public export?",
    "Что такое MCP orchestration?",
    "Как устроены context strategies?",
    "Какие проверки нужно запускать перед сдачей?",
)
GENERATED_ARTIFACT_NAMES = (
    "chunking-comparison.md",
    "fixed-index.json",
    "fixed-index.sqlite3",
    "index-manifest.json",
    "sample-search-results.json",
    "structure-index.json",
    "structure-index.sqlite3",
)


def _embedded_chunks(chunks: list[Chunk], backend: EmbeddingBackend) -> list[dict[str, Any]]:
    embeddings = backend.embed([chunk.text for chunk in chunks])
    if len(embeddings) != len(chunks):
        raise RuntimeError("Embedding backend returned an unexpected number of vectors")
    return [
        {
            "chunk_id": chunk.chunk_id,
            "text": chunk.text,
            "embedding": embedding,
            "metadata": chunk.metadata,
        }
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    ]


def _manifest(
    strategy: str,
    backend: EmbeddingBackend,
    documents: list[Document],
    chunks: list[dict[str, Any]],
    created_at: str,
    settings: dict[str, int],
) -> dict[str, Any]:
    dimension = len(chunks[0]["embedding"]) if chunks else 0
    return {
        "strategy": strategy,
        "embedding_backend": backend.name,
        "embedding_model": backend.model,
        "created_at": created_at,
        "document_count": len(documents),
        "chunk_count": len(chunks),
        "embedding_dim": dimension,
        "sources": [document.source for document in documents],
        "settings": settings,
    }


def _stats(chunks: list[dict[str, Any]], json_path: Path, sqlite_path: Path) -> dict[str, Any]:
    chars = [int(item["metadata"]["char_count"]) for item in chunks]
    words = [int(item["metadata"]["word_count"]) for item in chunks]
    return {
        "chunk_count": len(chunks),
        "chars_min": min(chars),
        "chars_avg": round(statistics.fmean(chars), 1),
        "chars_max": max(chars),
        "words_min": min(words),
        "words_avg": round(statistics.fmean(words), 1),
        "words_max": max(words),
        "section_chunks": sum(bool(item["metadata"].get("section")) for item in chunks),
        "source_count": len({item["metadata"]["source"] for item in chunks}),
        "json_bytes": json_path.stat().st_size,
        "sqlite_bytes": sqlite_path.stat().st_size,
    }


def _search_payload(
    indexes: dict[str, list[dict[str, Any]]],
    backend: EmbeddingBackend,
    queries: tuple[str, ...],
    top_k: int,
) -> dict[str, Any]:
    return {
        "embedding_backend": backend.name,
        "embedding_model": backend.model,
        "top_k": top_k,
        "queries": [
            {
                "query": query,
                "strategies": {
                    strategy: [
                        {
                            "rank": rank,
                            "chunk_id": result.chunk_id,
                            "score": round(result.score, 6),
                            "source": result.metadata["source"],
                            "section": result.metadata.get("section"),
                            "line_range": [
                                result.metadata.get("start_line"),
                                result.metadata.get("end_line"),
                            ],
                            "text_preview": result.text[:240].replace("\n", " "),
                        }
                        for rank, result in enumerate(
                            search_index(chunks, query, backend, top_k=top_k), 1
                        )
                    ]
                    for strategy, chunks in indexes.items()
                },
            }
            for query in queries
        ],
    }


def _comparison_markdown(
    documents: list[Document],
    manifests: dict[str, dict[str, Any]],
    stats: dict[str, dict[str, Any]],
    searches: dict[str, Any],
) -> str:
    fixed = stats["fixed"]
    structure = stats["structure"]
    lines = [
        "# Сравнение стратегий chunking — Day 21",
        "",
        "## Corpus",
        "",
        f"Проиндексировано {len(documents)} public-safe документов: "
        f"{sum(document.word_count for document in documents):,} слов, "
        f"{sum(document.char_count for document in documents):,} символов.",
        "",
        "## Настройки",
        "",
        f"- Fixed-size: `{manifests['fixed']['settings']}`.",
        f"- Structure-aware: `{manifests['structure']['settings']}`.",
        f"- Embeddings: `{manifests['fixed']['embedding_backend']}` / "
        f"`{manifests['fixed']['embedding_model']}`, "
        f"dimension `{manifests['fixed']['embedding_dim']}`.",
        "",
        "## Сравнение",
        "",
        "| Метрика | Fixed-size | Structure-aware |",
        "|---|---:|---:|",
        f"| Документы | {len(documents)} | {len(documents)} |",
        f"| Chunks | {fixed['chunk_count']} | {structure['chunk_count']} |",
        "| Символы min / avg / max | "
        f"{fixed['chars_min']} / {fixed['chars_avg']} / {fixed['chars_max']} | "
        f"{structure['chars_min']} / {structure['chars_avg']} / {structure['chars_max']} |",
        "| Слова min / avg / max | "
        f"{fixed['words_min']} / {fixed['words_avg']} / {fixed['words_max']} | "
        f"{structure['words_min']} / {structure['words_avg']} / {structure['words_max']} |",
        f"| Chunks с section | {fixed['section_chunks']} | {structure['section_chunks']} |",
        f"| Покрыто sources | {fixed['source_count']} | {structure['source_count']} |",
        f"| JSON bytes | {fixed['json_bytes']} | {structure['json_bytes']} |",
        f"| SQLite bytes | {fixed['sqlite_bytes']} | {structure['sqlite_bytes']} |",
        "",
        "## Практические выводы",
        "",
        "Fixed-size даёт простой baseline и предсказуемый верхний предел размера, но границы "
        "могут объединять соседние смысловые разделы.",
        "",
        "Structure-aware сохраняет path заголовков Markdown и границы Python-блоков; крупные "
        "разделы всё равно дробятся с overlap. Размеры chunks поэтому менее равномерны.",
        "",
        "Fixed-size полезен для однородного сырого текста. Structure-aware предпочтителен для "
        "документации и кода, когда section metadata важна для retrieval и объяснимости.",
        "",
        "## Sample retrieval",
        "",
        "Retrieval — sanity check индекса, без генеративной LLM.",
        "",
    ]
    for query in searches["queries"]:
        lines.extend([f"### {query['query']}", ""])
        for strategy in ("fixed", "structure"):
            top = query["strategies"][strategy][0]
            lines.append(
                f"- `{strategy}`: `{top['chunk_id']}`, score `{top['score']}`, "
                f"source `{top['source']}`, section `{top['section']}`."
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def run_indexing_pipeline(
    corpus_dir: Path | str,
    output_dir: Path | str,
    backend: EmbeddingBackend,
    *,
    fixed_chunk_size: int = 1600,
    fixed_overlap: int = 200,
    structure_max_chunk_size: int = 2400,
    structure_overlap: int = 200,
    top_k: int = 3,
    sample_queries: tuple[str, ...] = DEFAULT_SAMPLE_QUERIES,
) -> dict[str, Any]:
    """Build both indexes, retrieval samples, and comparison artifacts."""

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    documents = load_documents(corpus_dir)
    created_at = datetime.now(UTC).isoformat()
    raw_chunks = {
        "fixed": chunk_documents_fixed(
            documents, chunk_size=fixed_chunk_size, overlap=fixed_overlap
        ),
        "structure": chunk_documents_structure(
            documents, max_chunk_size=structure_max_chunk_size, overlap=structure_overlap
        ),
    }
    indexes: dict[str, list[dict[str, Any]]] = {}
    manifests: dict[str, dict[str, Any]] = {}
    paths: dict[str, dict[str, Path]] = {}
    settings = {
        "fixed": {"chunk_size": fixed_chunk_size, "overlap": fixed_overlap},
        "structure": {"max_chunk_size": structure_max_chunk_size, "overlap": structure_overlap},
    }
    for strategy in ("fixed", "structure"):
        indexes[strategy] = _embedded_chunks(raw_chunks[strategy], backend)
        manifests[strategy] = _manifest(
            strategy,
            backend,
            documents,
            indexes[strategy],
            created_at,
            settings[strategy],
        )
        paths[strategy] = {
            "json": output / f"{strategy}-index.json",
            "sqlite": output / f"{strategy}-index.sqlite3",
        }
        save_json_index(paths[strategy]["json"], manifests[strategy], indexes[strategy])
        save_sqlite_index(paths[strategy]["sqlite"], manifests[strategy], indexes[strategy])

    stats = {
        strategy: _stats(indexes[strategy], paths[strategy]["json"], paths[strategy]["sqlite"])
        for strategy in ("fixed", "structure")
    }
    searches = _search_payload(indexes, backend, sample_queries, top_k)
    (output / "sample-search-results.json").write_text(
        json.dumps(searches, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = {
        "created_at": created_at,
        "corpus": {
            "document_count": len(documents),
            "word_count": sum(document.word_count for document in documents),
            "char_count": sum(document.char_count for document in documents),
            "sources": [document.source for document in documents],
        },
        "indexes": manifests,
        "statistics": stats,
        "artifacts": list(GENERATED_ARTIFACT_NAMES),
    }
    (output / "chunking-comparison.md").write_text(
        _comparison_markdown(documents, manifests, stats, searches), encoding="utf-8"
    )
    (output / "index-manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary
