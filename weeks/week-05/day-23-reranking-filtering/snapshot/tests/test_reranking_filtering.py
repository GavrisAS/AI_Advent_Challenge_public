from __future__ import annotations

import json
from pathlib import Path

from ai_advent_agent.scenarios import main

DAY_DIR = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = DAY_DIR / "snapshot"


def test_offline_hash_fake_scenario_creates_day23_artifacts(tmp_path: Path) -> None:
    output = tmp_path / "artifacts"

    exit_code = main(
        [
            "reranking-filtering-demo",
            "--corpus-dir",
            str(DAY_DIR / "corpus"),
            "--questions-json",
            str(DAY_DIR / "eval/control-questions.json"),
            "--embedding-backend",
            "hash",
            "--llm-provider",
            "fake",
            "--rewrite-mode",
            "heuristic",
            "--rerank-mode",
            "heuristic",
            "--top-k-plain",
            "4",
            "--top-k-before",
            "8",
            "--top-k-after",
            "4",
            "--similarity-threshold",
            "0.10",
            "--output-dir",
            str(output),
            "--hash-dim",
            "64",
            "--rebuild-index",
        ]
    )

    assert exit_code == 0
    expected = {
        "day23-comparison.json",
        "day23-comparison.md",
        "sample-improved-rag-answer.json",
        "structure-index.json",
        "structure-index.sqlite3",
        "index-manifest.json",
    }
    assert expected == {path.name for path in output.iterdir()}
    payload = json.loads((output / "day23-comparison.json").read_text(encoding="utf-8"))
    assert len(payload["questions"]) == 10
    assert payload["settings"]["embedding_backend"] == "hash"
    assert payload["settings"]["llm_provider"] == "fake"


def test_snapshot_has_no_day21_or_day22_runtime_dependencies() -> None:
    forbidden = ("day-21-document-indexing", "day-22-first-rag-query")
    sources = list((SNAPSHOT_DIR / "src").rglob("*.py"))

    assert sources
    for source in sources:
        text = source.read_text(encoding="utf-8")
        assert all(value not in text for value in forbidden)


def test_scenario_entry_point_exists_only_in_snapshot_package() -> None:
    snapshot_pyproject = (SNAPSHOT_DIR / "pyproject.toml").read_text(encoding="utf-8")
    repo_root = Path(__file__).resolve().parents[5]
    current_pyproject = (repo_root / "packages/ai_advent_agent/pyproject.toml").read_text(
        encoding="utf-8"
    )

    assert 'ai-advent-scenarios = "ai_advent_agent.scenarios:main"' in snapshot_pyproject
    assert "ai-advent-scenarios" not in current_pyproject
