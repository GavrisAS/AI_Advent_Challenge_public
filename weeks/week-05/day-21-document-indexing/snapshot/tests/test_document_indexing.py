from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from ai_advent_agent.rag.chunking import chunk_documents_fixed, chunk_documents_structure
from ai_advent_agent.rag.documents import load_documents
from ai_advent_agent.rag.embeddings import HashEmbeddingBackend
from ai_advent_agent.rag.index_store import load_json_index
from ai_advent_agent.rag.search import search_index
from ai_advent_agent.scenarios import main


def _corpus(path: Path) -> Path:
    path.mkdir()
    (path / "guide.md").write_text(
        "# Guide\n\nPublic export safety rules.\n\n## Snapshots\n\n"
        + "Historical scenarios run from snapshots only. " * 30,
        encoding="utf-8",
    )
    (path / "code.py").write_text("def index():\n    return 'chunk'\n", encoding="utf-8")
    (path / "plain.txt").write_text("context strategies and checks\n" * 5, encoding="utf-8")
    hidden = path / ".tmp"
    hidden.mkdir()
    (hidden / "secret.md").write_text("ignored", encoding="utf-8")
    return path


def test_loading_chunking_embeddings_and_search(tmp_path: Path) -> None:
    documents = load_documents(_corpus(tmp_path / "corpus"))
    assert len(documents) == 3
    assert all(len(document.sha256) == 64 for document in documents)
    fixed = chunk_documents_fixed(documents, chunk_size=140, overlap=20)
    structure = chunk_documents_structure(documents, max_chunk_size=160, overlap=20)
    assert len(fixed) > 3
    assert any("Snapshots" in chunk.metadata["section"] for chunk in structure)
    assert [chunk.chunk_id for chunk in fixed] == [
        chunk.chunk_id for chunk in chunk_documents_fixed(documents, chunk_size=140, overlap=20)
    ]

    backend = HashEmbeddingBackend(32)
    texts = ["public export", "historical snapshot", "weather"]
    assert backend.embed(texts) == backend.embed(texts)
    records = [
        {
            "chunk_id": f"fixed:test:{index:04d}",
            "text": text,
            "embedding": embedding,
            "metadata": {"source": "corpus/test.md", "section": "test"},
        }
        for index, (text, embedding) in enumerate(zip(texts, backend.embed(texts), strict=True))
    ]
    assert search_index(records, "snapshot historical", backend, top_k=1)[0].text == texts[1]


def test_structure_chunking_skips_heading_only_sections(tmp_path: Path) -> None:
    corpus = tmp_path / "nested-corpus"
    corpus.mkdir()
    markdown = """# Parent

## Child

Useful child content.

### Empty

#### Nested

Nested useful content.
"""
    (corpus / "nested.md").write_text(markdown, encoding="utf-8")
    documents = load_documents(corpus)

    structure = chunk_documents_structure(documents, max_chunk_size=200, overlap=20)
    fixed = chunk_documents_fixed(documents, chunk_size=500, overlap=20)

    assert fixed[0].text == markdown.strip()
    assert any(chunk.metadata["section"] == "Parent > Child" for chunk in structure)
    assert any(
        chunk.metadata["section"] == "Parent > Child > Empty > Nested" for chunk in structure
    )
    assert all(
        any(
            line.strip() and re.fullmatch(r"#{1,6}\s+.+", line.strip()) is None
            for line in chunk.text.splitlines()
        )
        for chunk in structure
    )


def test_hash_scenario_smoke_creates_all_artifacts(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path / "corpus")
    output = tmp_path / "artifacts"
    exit_code = main(
        [
            "document-indexing-demo",
            "--corpus-dir",
            str(corpus),
            "--output-dir",
            str(output),
            "--embedding-backend",
            "hash",
            "--hash-dim",
            "32",
            "--fixed-chunk-size",
            "160",
            "--fixed-overlap",
            "20",
            "--structure-max-chunk-size",
            "180",
            "--structure-overlap",
            "20",
        ]
    )
    assert exit_code == 0
    expected = {
        "fixed-index.json",
        "fixed-index.sqlite3",
        "structure-index.json",
        "structure-index.sqlite3",
        "chunking-comparison.md",
        "index-manifest.json",
        "sample-search-results.json",
    }
    assert expected == {path.name for path in output.iterdir()}
    manifest, chunks = load_json_index(output / "structure-index.json")
    assert manifest["embedding_backend"] == "hash"
    assert manifest["embedding_dim"] == 32
    assert chunks[0]["metadata"]["section"]
    with sqlite3.connect(output / "fixed-index.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] > 0
    search_payload = json.loads((output / "sample-search-results.json").read_text())
    assert search_payload["queries"]

    assert (
        main(
            [
                "document-indexing-demo",
                "--corpus-dir",
                str(corpus),
                "--output-dir",
                str(output),
                "--embedding-backend",
                "hash",
                "--hash-dim",
                "32",
                "--fixed-chunk-size",
                "160",
                "--fixed-overlap",
                "20",
                "--structure-max-chunk-size",
                "180",
                "--structure-overlap",
                "20",
            ]
        )
        == 0
    )
    index_manifest = json.loads((output / "index-manifest.json").read_text(encoding="utf-8"))
    artifacts = index_manifest["artifacts"]
    assert len(artifacts) == len(set(artifacts))
