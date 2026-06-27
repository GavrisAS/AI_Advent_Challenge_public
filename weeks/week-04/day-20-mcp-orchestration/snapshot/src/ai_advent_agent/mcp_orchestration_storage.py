"""Path-safe storage MCP server for Day 20 final artifacts."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Annotated, Any, TypedDict

from mcp.server.fastmcp import FastMCP
from pydantic import Field

ORCHESTRATION_OUTPUT_DIR_ENV = "AI_ADVENT_ORCHESTRATION_OUTPUT_DIR"


class SaveFilePayload(TypedDict):
    saved: bool
    path: str
    bytes_written: int
    sha256: str


def validate_storage_filename(filename: str, *, suffix: str) -> str:
    """Validate a flat relative filename with the required suffix."""

    stripped = filename.strip()
    if not stripped:
        raise ValueError("filename must not be empty")
    candidate = Path(stripped)
    if candidate.is_absolute():
        raise ValueError("absolute paths are forbidden")
    if len(candidate.parts) != 1 or any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValueError("nested paths and parent/current path segments are forbidden")
    if candidate.suffix.casefold() != suffix:
        raise ValueError(f"filename must use {suffix} suffix")
    return candidate.name


def configured_output_dir() -> Path:
    return Path(os.environ.get(ORCHESTRATION_OUTPUT_DIR_ENV, "artifacts")).expanduser()


def build_storage_server() -> FastMCP:
    """Build the isolated write-only-to-configured-directory storage server."""

    server = FastMCP("AI Advent Orchestration Storage")

    @server.tool(structured_output=True)
    def save_markdown_file(
        filename: Annotated[str, Field(description="Flat relative .md filename.")],
        content: Annotated[str, Field(description="Markdown content to save.")],
    ) -> SaveFilePayload:
        """Save Markdown only inside the configured output directory."""

        return _save_bytes(validate_storage_filename(filename, suffix=".md"), content.encode())

    @server.tool(structured_output=True)
    def save_json_file(
        filename: Annotated[str, Field(description="Flat relative .json filename.")],
        data: Annotated[dict[str, Any], Field(description="JSON object to save.")],
    ) -> SaveFilePayload:
        """Save a JSON object only inside the configured output directory."""

        payload = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        return _save_bytes(validate_storage_filename(filename, suffix=".json"), payload)

    return server


def _save_bytes(filename: str, payload: bytes) -> SaveFilePayload:
    output_dir = configured_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / filename
    destination.write_bytes(payload)
    return {
        "saved": True,
        "path": filename,
        "bytes_written": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


mcp = build_storage_server()
