"""Artifacts сравнения plain и improved RAG для Day 23."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_advent_agent.rag.embeddings import EmbeddingBackend
from ai_advent_agent.rag.eval_set import (
    ControlQuestion,
    heuristic_point_coverage,
    load_control_questions,
)
from ai_advent_agent.rag.index_store import load_json_index
from ai_advent_agent.rag.llm import RagLLM
from ai_advent_agent.rag.pipelines import RagModeComparison, run_plain_and_improved
from ai_advent_agent.rag.query_rewrite import RewriteMode
from ai_advent_agent.rag.reports import build_structure_index
from ai_advent_agent.rag.reranking import RerankedChunk, RerankMode
from ai_advent_agent.rag.search import RetrievedChunk

DAY23_ARTIFACT_NAMES = (
    "day23-comparison.json",
    "day23-comparison.md",
    "index-manifest.json",
    "sample-improved-rag-answer.json",
    "structure-index.json",
    "structure-index.sqlite3",
)


def _plain_chunk_payload(chunk: RetrievedChunk, rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "chunk_id": chunk.chunk_id,
        "similarity_score": round(chunk.score, 6),
        "source": chunk.source,
        "title": chunk.title,
        "section": chunk.section,
        "line_range": [chunk.metadata.get("start_line"), chunk.metadata.get("end_line")],
        "text_preview": chunk.text[:500].replace("\n", " "),
    }


def _reranked_chunk_payload(item: RerankedChunk, rank: int) -> dict[str, Any]:
    chunk = item.chunk
    components = item.components
    return {
        "rank": rank,
        "chunk_id": chunk.chunk_id,
        "similarity_score": round(components.similarity_score, 6),
        "final_rerank_score": round(item.final_score, 6),
        "score_components": {
            "similarity_score": round(components.similarity_score, 6),
            "source_bonus": round(components.source_bonus, 6),
            "section_bonus": round(components.section_bonus, 6),
            "keyword_bonus": round(components.keyword_bonus, 6),
        },
        "source": chunk.source,
        "title": chunk.title,
        "section": chunk.section,
        "line_range": [chunk.metadata.get("start_line"), chunk.metadata.get("end_line")],
        "text_preview": chunk.text[:500].replace("\n", " "),
    }


def _source_hit(chunks: list[dict[str, Any]], expected_sources: list[str]) -> bool:
    found = {Path(str(item["source"])).name for item in chunks}
    return any(Path(source).name in found for source in expected_sources)


def _question_payload(control: ControlQuestion, result: RagModeComparison) -> dict[str, Any]:
    plain_chunks = [
        _plain_chunk_payload(chunk, rank)
        for rank, chunk in enumerate(result.plain.context.chunks, 1)
    ]
    before = [
        _plain_chunk_payload(chunk, rank)
        for rank, chunk in enumerate(result.improved.retrieved_before_filter.chunks, 1)
    ]
    after = [
        _reranked_chunk_payload(item, rank)
        for rank, item in enumerate(result.improved.reranked.chunks, 1)
    ]
    plain_points = heuristic_point_coverage(result.plain.answer, control.expected_points)
    improved_points = heuristic_point_coverage(result.improved.answer, control.expected_points)
    plain_hit = _source_hit(plain_chunks, control.expected_sources)
    improved_hit = _source_hit(after, control.expected_sources)
    source_delta = int(improved_hit) - int(plain_hit)
    point_delta = improved_points - plain_points
    if source_delta > 0 or point_delta > 0:
        summary = "Improved RAG улучшил попадание в источники или покрытие ожидаемых пунктов."
    elif source_delta < 0 or point_delta < 0:
        summary = "По deterministic-эвристике improved RAG регрессировал на этом вопросе."
    else:
        summary = "По deterministic-эвристике режимы дали одинаковый результат."
    return {
        "id": control.id,
        "question": control.question,
        "expected_points": control.expected_points,
        "expected_sources": control.expected_sources,
        "plain_rag": {
            "retrieved_chunks": plain_chunks,
            "answer": result.plain.answer,
            "expected_sources_found": plain_hit,
            "expected_points_covered": plain_points,
        },
        "improved_rag": {
            "original_question": result.improved.rewrite.original_question,
            "rewritten_query": result.improved.rewrite.rewritten_query,
            "rewrite_mode": result.improved.rewrite.rewrite_mode,
            "added_terms": list(result.improved.rewrite.added_terms),
            "retrieved_before_filter": before,
            "filtered_or_reranked_chunks": after,
            "rejected_chunk_ids": list(result.improved.reranked.rejected_chunk_ids),
            "answer": result.improved.answer,
            "expected_sources_found": improved_hit,
            "expected_points_covered": improved_points,
            "fallback_used": result.improved.reranked.fallback_used,
        },
        "comparison": {
            "source_hit_delta": source_delta,
            "expected_points_delta": point_delta,
            "summary": summary,
        },
    }


def _aggregate(questions: list[dict[str, Any]]) -> dict[str, int]:
    improved = 0
    regressed = 0
    for item in questions:
        comparison = item["comparison"]
        deltas = (comparison["source_hit_delta"], comparison["expected_points_delta"])
        if any(delta > 0 for delta in deltas) and not any(delta < 0 for delta in deltas):
            improved += 1
        elif any(delta < 0 for delta in deltas):
            regressed += 1
    return {
        "plain_expected_source_hits": sum(
            item["plain_rag"]["expected_sources_found"] for item in questions
        ),
        "improved_expected_source_hits": sum(
            item["improved_rag"]["expected_sources_found"] for item in questions
        ),
        "plain_expected_points_covered": sum(
            item["plain_rag"]["expected_points_covered"] for item in questions
        ),
        "improved_expected_points_covered": sum(
            item["improved_rag"]["expected_points_covered"] for item in questions
        ),
        "questions_improved": improved,
        "questions_regressed": regressed,
        "questions_same": len(questions) - improved - regressed,
    }


def _chunks_markdown(chunks: list[dict[str, Any]], *, reranked: bool = False) -> list[str]:
    if not chunks:
        return ["Ничего не найдено.", ""]
    lines: list[str] = []
    for chunk in chunks:
        score = (
            f"similarity `{chunk['similarity_score']}`, final `{chunk['final_rerank_score']}`"
            if reranked
            else f"similarity `{chunk['similarity_score']}`"
        )
        lines.append(
            f"{chunk['rank']}. `{chunk['source']}` — `{chunk['section']}`; {score}; "
            f"chunk `{chunk['chunk_id']}`."
        )
    lines.append("")
    return lines


def comparison_markdown(payload: dict[str, Any]) -> str:
    settings = payload["settings"]
    aggregate = payload["aggregate"]
    lines = [
        "# Day 23 — Реранкинг, фильтрация и query rewrite",
        "",
        "## Настройки",
        "",
        f"- Plain RAG: top_k=`{settings['plain_top_k']}`, без rewrite и filter.",
        f"- Improved RAG: rewrite=`{settings['rewrite_mode']}`, "
        f"top_k_before=`{settings['improved_top_k_before']}`, "
        f"threshold=`{settings['similarity_threshold']}`, "
        f"top_k_after=`{settings['improved_top_k_after']}`, "
        f"rerank=`{settings['rerank_mode']}`.",
        f"- Embeddings: `{settings['embedding_backend']}` / `{settings['embedding_model']}`.",
        f"- LLM: `{settings['llm_provider']}` / `{settings['llm_model']}`.",
        "",
        "## Итоговая таблица",
        "",
        "| ID | Вопрос | Plain source hit | Improved source hit | Plain coverage | "
        "Improved coverage | Вывод |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for item in payload["questions"]:
        plain = item["plain_rag"]
        improved = item["improved_rag"]
        question = item["question"].replace("|", "\\|")
        lines.append(
            f"| {item['id']} | {question} | {int(plain['expected_sources_found'])} | "
            f"{int(improved['expected_sources_found'])} | {plain['expected_points_covered']} | "
            f"{improved['expected_points_covered']} | {item['comparison']['summary']} |"
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- Source hits: plain `{aggregate['plain_expected_source_hits']}`, improved "
            f"`{aggregate['improved_expected_source_hits']}`.",
            f"- Expected points: plain `{aggregate['plain_expected_points_covered']}`, improved "
            f"`{aggregate['improved_expected_points_covered']}`.",
            f"- Вопросы: improved `{aggregate['questions_improved']}`, regressed "
            f"`{aggregate['questions_regressed']}`, same `{aggregate['questions_same']}`.",
            "",
            "## Детализация по вопросам",
            "",
        ]
    )
    for item in payload["questions"]:
        improved = item["improved_rag"]
        lines.extend(
            [
                f"### {item['id']} — {item['question']}",
                "",
                f"**Original question:** {improved['original_question']}",
                "",
                f"**Rewritten query:** {improved['rewritten_query']}",
                "",
                "#### Plain RAG chunks",
                "",
                *_chunks_markdown(item["plain_rag"]["retrieved_chunks"]),
                "#### Improved RAG chunks before filtering",
                "",
                *_chunks_markdown(improved["retrieved_before_filter"]),
                "#### Improved RAG chunks after filtering/reranking",
                "",
                *_chunks_markdown(improved["filtered_or_reranked_chunks"], reranked=True),
                f"Fallback: `{str(improved['fallback_used']).lower()}`.",
                "",
                "#### Ответ plain RAG",
                "",
                item["plain_rag"]["answer"],
                "",
                "#### Ответ improved RAG",
                "",
                improved["answer"],
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def run_day23_comparison(
    corpus_dir: Path | str,
    questions_json: Path | str,
    output_dir: Path | str,
    backend: EmbeddingBackend,
    llm: RagLLM,
    *,
    plain_top_k: int = 4,
    improved_top_k_before: int = 8,
    improved_top_k_after: int = 4,
    similarity_threshold: float = 0.25,
    rewrite_mode: RewriteMode = "heuristic",
    rerank_mode: RerankMode = "heuristic",
    rebuild_index: bool = False,
) -> dict[str, Any]:
    """Создать индекс и полное deterministic-сравнение двух RAG режимов."""

    if improved_top_k_before < improved_top_k_after:
        raise ValueError("improved_top_k_before must be >= improved_top_k_after")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    index_path = output / "structure-index.json"
    if rebuild_index or not index_path.exists():
        index_manifest, chunks = build_structure_index(corpus_dir, output, backend)
    else:
        try:
            index_manifest, chunks = load_json_index(index_path)
        except (OSError, TypeError, ValueError):
            index_manifest, chunks = build_structure_index(corpus_dir, output, backend)
        else:
            compatible = (
                index_manifest.get("embedding_backend") == backend.name
                and index_manifest.get("embedding_model") == backend.model
            )
            if not compatible:
                index_manifest, chunks = build_structure_index(corpus_dir, output, backend)

    settings = {
        "corpus_dir": str(corpus_dir),
        "questions_json": str(questions_json),
        "embedding_backend": backend.name,
        "embedding_model": backend.model,
        "llm_provider": llm.provider,
        "llm_model": llm.model,
        "plain_top_k": plain_top_k,
        "improved_top_k_before": improved_top_k_before,
        "improved_top_k_after": improved_top_k_after,
        "similarity_threshold": similarity_threshold,
        "rewrite_mode": rewrite_mode,
        "rerank_mode": rerank_mode,
    }
    controls = load_control_questions(questions_json)
    questions = []
    for control in controls:
        result = run_plain_and_improved(
            control.question,
            chunks,
            backend,
            llm,
            plain_top_k=plain_top_k,
            improved_top_k_before=improved_top_k_before,
            improved_top_k_after=improved_top_k_after,
            similarity_threshold=similarity_threshold,
            rewrite_mode=rewrite_mode,
            rerank_mode=rerank_mode,
        )
        questions.append(_question_payload(control, result))
    payload = {
        "settings": settings,
        "index": index_manifest,
        "questions": questions,
        "aggregate": _aggregate(questions),
        "evaluation_notes": (
            "Source hits и expected point coverage считаются deterministic-эвристикой; "
            "expected_sources не участвуют в production-like reranker."
        ),
    }
    (output / "day23-comparison.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "day23-comparison.md").write_text(comparison_markdown(payload), encoding="utf-8")
    sample = next((item for item in questions if item["id"] == "q03"), questions[0])
    (output / "sample-improved-rag-answer.json").write_text(
        json.dumps(sample, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    artifact_manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        **settings,
        "artifacts": list(DAY23_ARTIFACT_NAMES),
        "index": index_manifest,
    }
    (output / "index-manifest.json").write_text(
        json.dumps(artifact_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return payload
