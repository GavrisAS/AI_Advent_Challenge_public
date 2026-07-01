"""JSON и SQLite persistence локального document index."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def save_json_index(
    path: Path | str, manifest: dict[str, Any], chunks: list[dict[str, Any]]
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"manifest": manifest, "chunks": chunks}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_json_index(path: Path | str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    manifest = payload.get("manifest")
    chunks = payload.get("chunks")
    if not isinstance(manifest, dict) or not isinstance(chunks, list):
        raise ValueError("Invalid JSON index: expected manifest object and chunks array")
    return manifest, chunks


def save_sqlite_index(
    path: Path | str, manifest: dict[str, Any], chunks: list[dict[str, Any]]
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target)
    try:
        connection.executescript(
            """
            DROP TABLE IF EXISTS chunks;
            DROP TABLE IF EXISTS index_manifest;
            CREATE TABLE index_manifest (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL
            );
            CREATE TABLE chunks (
                chunk_id TEXT PRIMARY KEY,
                strategy TEXT NOT NULL,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                section TEXT,
                start_line INTEGER,
                end_line INTEGER,
                text TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            );
            CREATE INDEX chunks_source_idx ON chunks(source);
            """
        )
        connection.executemany(
            "INSERT INTO index_manifest(key, value_json) VALUES (?, ?)",
            [
                (key, json.dumps(value, ensure_ascii=False, sort_keys=True))
                for key, value in sorted(manifest.items())
            ],
        )
        connection.executemany(
            """
            INSERT INTO chunks(
                chunk_id, strategy, source, title, section, start_line, end_line,
                text, embedding_json, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["chunk_id"],
                    item["metadata"]["strategy"],
                    item["metadata"]["source"],
                    item["metadata"]["title"],
                    item["metadata"].get("section"),
                    item["metadata"].get("start_line"),
                    item["metadata"].get("end_line"),
                    item["text"],
                    json.dumps(item["embedding"], separators=(",", ":")),
                    json.dumps(item["metadata"], ensure_ascii=False, sort_keys=True),
                )
                for item in chunks
            ],
        )
        connection.commit()
    finally:
        connection.close()


def load_sqlite_index(path: Path | str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    connection = sqlite3.connect(Path(path))
    connection.row_factory = sqlite3.Row
    try:
        manifest = {
            row["key"]: json.loads(row["value_json"])
            for row in connection.execute("SELECT key, value_json FROM index_manifest ORDER BY key")
        }
        chunks = [
            {
                "chunk_id": row["chunk_id"],
                "text": row["text"],
                "embedding": json.loads(row["embedding_json"]),
                "metadata": json.loads(row["metadata_json"]),
            }
            for row in connection.execute("SELECT * FROM chunks ORDER BY chunk_id")
        ]
    finally:
        connection.close()
    return manifest, chunks
