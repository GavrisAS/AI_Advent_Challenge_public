from __future__ import annotations

import json
from pathlib import Path

from ai_advent_agent.rag.embeddings import HashEmbeddingBackend
from ai_advent_agent.rag.eval_set import load_control_questions
from ai_advent_agent.rag.llm import FakeLLM
from ai_advent_agent.rag.prompts import build_baseline_prompt, build_rag_prompt
from ai_advent_agent.rag.reports import run_rag_comparison
from ai_advent_agent.rag.search import RetrievedChunk, RetrievedContext

DAY_DIR = Path(__file__).resolve().parents[2]


def test_control_set_has_exactly_ten_valid_questions() -> None:
    questions = load_control_questions(DAY_DIR / "eval/control-questions.json")
    assert len(questions) == 10
    assert all(item.id and item.question and item.expected_points for item in questions)
    assert all(isinstance(item.expected_sources, list) for item in questions)
    corpus_files = {path.name for path in (DAY_DIR / "corpus").iterdir() if path.is_file()}
    assert all(source in corpus_files for item in questions for source in item.expected_sources)


def test_prompts_separate_baseline_and_context() -> None:
    chunk = RetrievedChunk("c1", 0.9, "corpus/a.md", "A", "S", "grounded text", {})
    context = RetrievedContext("q", [chunk], 1)
    assert "Контекст:" not in build_baseline_prompt("q")
    rag = build_rag_prompt("q", context)
    assert "grounded text" in rag and "Источники" in rag and "chunk_id" in rag


def test_fake_demo_is_deterministic_and_manifest_has_no_duplicates(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    args = (DAY_DIR / "corpus", DAY_DIR / "eval/control-questions.json")
    for output in (first, second):
        run_rag_comparison(*args, output, HashEmbeddingBackend(64), FakeLLM(), rebuild_index=True)
    left = json.loads((first / "rag-comparison.json").read_text(encoding="utf-8"))
    right = json.loads((second / "rag-comparison.json").read_text(encoding="utf-8"))
    assert left["questions"] == right["questions"]
    manifest = json.loads((first / "index-manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["artifacts"]) == len(set(manifest["artifacts"]))


def test_existing_index_is_rebuilt_when_embedding_model_changes(tmp_path: Path) -> None:
    output = tmp_path / "artifacts"
    args = (DAY_DIR / "corpus", DAY_DIR / "eval/control-questions.json")
    run_rag_comparison(*args, output, HashEmbeddingBackend(32), FakeLLM(), rebuild_index=True)
    run_rag_comparison(*args, output, HashEmbeddingBackend(64), FakeLLM())
    index = json.loads((output / "structure-index.json").read_text(encoding="utf-8"))
    assert index["manifest"]["embedding_model"] == "feature-hash-64"
    assert index["manifest"]["embedding_dim"] == 64


def test_snapshot_has_no_day21_dependency() -> None:
    forbidden = "day-21-" + "document-indexing"
    for path in (DAY_DIR / "snapshot").rglob("*"):
        if path.is_file() and path.suffix in {".py", ".toml", ".md"}:
            assert forbidden not in path.read_text(encoding="utf-8")
