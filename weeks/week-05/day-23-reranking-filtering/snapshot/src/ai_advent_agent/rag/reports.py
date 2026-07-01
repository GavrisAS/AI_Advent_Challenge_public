"""Reproducible index and comparison artifacts for RAG QA."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_advent_agent.rag.chunking import chunk_documents_structure
from ai_advent_agent.rag.documents import load_documents
from ai_advent_agent.rag.embeddings import EmbeddingBackend
from ai_advent_agent.rag.eval_set import (
    ControlQuestion,
    heuristic_point_coverage,
    load_control_questions,
)
from ai_advent_agent.rag.index_store import load_json_index, save_json_index, save_sqlite_index
from ai_advent_agent.rag.llm import RagLLM
from ai_advent_agent.rag.qa import answer_question

ARTIFACT_NAMES = (
    "index-manifest.json",
    "rag-comparison.json",
    "rag-comparison.md",
    "sample-rag-answer.json",
    "structure-index.json",
    "structure-index.sqlite3",
)


def build_structure_index(
    corpus_dir: Path | str,
    output_dir: Path | str,
    backend: EmbeddingBackend,
    *,
    max_chunk_size: int = 2400,
    overlap: int = 200,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    documents = load_documents(corpus_dir)
    chunks = chunk_documents_structure(documents, max_chunk_size=max_chunk_size, overlap=overlap)
    vectors = backend.embed([chunk.text for chunk in chunks])
    if len(vectors) != len(chunks):
        raise RuntimeError("Embedding backend returned an unexpected number of vectors")
    embedded = [
        {
            "chunk_id": chunk.chunk_id,
            "text": chunk.text,
            "embedding": vector,
            "metadata": chunk.metadata,
        }
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    manifest = {
        "strategy": "structure",
        "embedding_backend": backend.name,
        "embedding_model": backend.model,
        "embedding_dim": len(vectors[0]) if vectors else 0,
        "created_at": datetime.now(UTC).isoformat(),
        "document_count": len(documents),
        "chunk_count": len(embedded),
        "sources": [document.source for document in documents],
        "settings": {"max_chunk_size": max_chunk_size, "overlap": overlap},
    }
    output = Path(output_dir)
    save_json_index(output / "structure-index.json", manifest, embedded)
    save_sqlite_index(output / "structure-index.sqlite3", manifest, embedded)
    return manifest, embedded


def _retrieved_payload(context: Any) -> list[dict[str, Any]]:
    return [
        {
            "rank": rank,
            "chunk_id": item.chunk_id,
            "score": round(item.score, 6),
            "source": item.source,
            "title": item.title,
            "section": item.section,
            "line_range": [item.metadata.get("start_line"), item.metadata.get("end_line")],
            "text_preview": item.text[:300].replace("\n", " "),
        }
        for rank, item in enumerate(context.chunks, 1)
    ]


def _question_payload(
    control: ControlQuestion,
    chunks: list[dict[str, Any]],
    backend: EmbeddingBackend,
    llm: RagLLM,
    top_k: int,
) -> dict[str, Any]:
    result = answer_question(control.question, "both", chunks, backend, llm, top_k)
    assert result.baseline_answer is not None and result.rag_answer is not None
    assert result.retrieved_context is not None
    retrieved = _retrieved_payload(result.retrieved_context)
    found_names = {Path(item["source"]).name for item in retrieved}
    return {
        "id": control.id,
        "question": control.question,
        "expected_points": control.expected_points,
        "expected_sources": control.expected_sources,
        "retrieved_chunks": retrieved,
        "baseline_answer": result.baseline_answer,
        "rag_answer": result.rag_answer,
        "quality": {
            "baseline_expected_points_covered": heuristic_point_coverage(
                result.baseline_answer, control.expected_points
            ),
            "rag_expected_points_covered": heuristic_point_coverage(
                result.rag_answer, control.expected_points
            ),
            "expected_sources_found": all(
                source in found_names for source in control.expected_sources
            ),
            "notes": "Эвристика: совпадение значимых слов; это не LLM-as-judge.",
        },
    }


def _comparison_markdown(payload: dict[str, Any]) -> str:
    settings = payload["settings"]
    lines = [
        "# Сравнение baseline и RAG — Day 22",
        "",
        "Цель: сравнить одну LLM без проектного контекста и с top-k chunks локального индекса.",
        "",
        "## Настройки",
        "",
        f"- Embeddings: `{settings['embedding_backend']}` / `{settings['embedding_model']}`.",
        f"- LLM: `{settings['llm_provider']}` / `{settings['llm_model']}`.",
        f"- Retrieval: plain top-{settings['top_k']} без reranking и filtering.",
        "",
        "## Сводка",
        "",
        "| ID | Baseline points | RAG points | Expected sources | Вывод |",
        "|---|---:|---:|---|---|",
    ]
    for item in payload["questions"]:
        quality = item["quality"]
        verdict = (
            "RAG лучше"
            if quality["rag_expected_points_covered"] > quality["baseline_expected_points_covered"]
            else "без преимущества по эвристике"
        )
        source_status = "да" if quality["expected_sources_found"] else "нет"
        baseline_points = quality["baseline_expected_points_covered"]
        rag_points = quality["rag_expected_points_covered"]
        lines.append(
            f"| {item['id']} | {baseline_points} | {rag_points} | {source_status} | {verdict} |"
        )
    lines.extend(["", "## Подробности", ""])
    for item in payload["questions"]:
        sources = ", ".join(
            f"`{chunk['source']}` ({chunk['score']})" for chunk in item["retrieved_chunks"]
        )
        lines.extend(
            [
                f"### {item['id']}: {item['question']}",
                "",
                f"- Baseline: {item['baseline_answer'][:500]}",
                f"- RAG: {item['rag_answer'][:800]}",
                f"- Найденные источники: {sources}.",
                f"- Вывод: {item['quality']['notes']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Общий вывод",
            "",
            "RAG получает проверяемый проектный контекст и source metadata; baseline не имеет "
            "доступа к внутренним правилам. Числа являются keyword-эвристикой, а не полной "
            "оценкой factual correctness. Day 23 добавит query rewrite и этап фильтрации.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def run_rag_comparison(
    corpus_dir: Path | str,
    questions_json: Path | str,
    output_dir: Path | str,
    backend: EmbeddingBackend,
    llm: RagLLM,
    *,
    top_k: int = 4,
    rebuild_index: bool = False,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    index_path = output / "structure-index.json"
    if rebuild_index or not index_path.exists():
        manifest, chunks = build_structure_index(corpus_dir, output, backend)
    else:
        try:
            manifest, chunks = load_json_index(index_path)
        except (OSError, TypeError, ValueError):
            manifest, chunks = build_structure_index(corpus_dir, output, backend)
        else:
            compatible = (
                manifest.get("embedding_backend") == backend.name
                and manifest.get("embedding_model") == backend.model
            )
            if not compatible:
                manifest, chunks = build_structure_index(corpus_dir, output, backend)
    controls = load_control_questions(questions_json)
    questions = [_question_payload(control, chunks, backend, llm, top_k) for control in controls]
    payload = {
        "settings": {
            "corpus_dir": str(corpus_dir),
            "index_json": str(index_path),
            "embedding_backend": backend.name,
            "embedding_model": backend.model,
            "llm_provider": llm.provider,
            "llm_model": llm.model,
            "top_k": top_k,
        },
        "index": manifest,
        "questions": questions,
    }
    (output / "rag-comparison.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "rag-comparison.md").write_text(_comparison_markdown(payload), encoding="utf-8")
    (output / "sample-rag-answer.json").write_text(
        json.dumps(questions[0], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    index_manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "embedding_backend": backend.name,
        "embedding_model": backend.model,
        "llm_provider": llm.provider,
        "llm_model": llm.model,
        "artifacts": sorted(set(ARTIFACT_NAMES)),
        "index": manifest,
    }
    (output / "index-manifest.json").write_text(
        json.dumps(index_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return payload
