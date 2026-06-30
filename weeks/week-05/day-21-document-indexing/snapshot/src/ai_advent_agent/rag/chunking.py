"""Fixed-size и structure-aware стратегии chunking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ai_advent_agent.rag.documents import Document

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
PYTHON_BLOCK_RE = re.compile(r"^(?:async\s+def|def|class)\s+([A-Za-z_]\w*)")


@dataclass(frozen=True, slots=True)
class Chunk:
    chunk_id: str
    text: str
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _Segment:
    text: str
    start_line: int
    end_line: int


def _validate_window(max_chars: int, overlap: int) -> None:
    if max_chars <= 0:
        raise ValueError("Chunk size must be positive")
    if overlap < 0 or overlap >= max_chars:
        raise ValueError("Overlap must be non-negative and smaller than chunk size")


def _split_lines(lines: list[str], start_line: int, max_chars: int, overlap: int) -> list[_Segment]:
    """Split on line boundaries; a single oversized line is sliced as a safe fallback."""

    if not lines:
        return []
    joined = "".join(lines)
    line_offsets = [0]
    for line in lines:
        line_offsets.append(line_offsets[-1] + len(line))

    segments: list[_Segment] = []
    cursor = 0
    while cursor < len(joined):
        target = min(cursor + max_chars, len(joined))
        end = target
        if target < len(joined):
            candidates = [offset for offset in line_offsets if cursor < offset <= target]
            if candidates:
                end = candidates[-1]
        if end <= cursor:
            end = target
        text = joined[cursor:end].strip()
        if text:
            first_index = max(
                0,
                next((i - 1 for i, value in enumerate(line_offsets) if value > cursor), 0),
            )
            last_index = max(
                first_index,
                next(
                    (i - 1 for i, value in enumerate(line_offsets) if value >= end),
                    len(lines) - 1,
                ),
            )
            segments.append(
                _Segment(
                    text=text,
                    start_line=start_line + first_index,
                    end_line=start_line + last_index,
                )
            )
        if end == len(joined):
            break
        desired = max(cursor + 1, end - overlap)
        prior_offsets = [offset for offset in line_offsets if cursor < offset <= desired]
        cursor = prior_offsets[-1] if prior_offsets else desired
    return segments


def _chunk(document: Document, strategy: str, section: str, index: int, segment: _Segment) -> Chunk:
    chunk_id = f"{strategy}:{document.relative_path}:{index:04d}"
    metadata: dict[str, Any] = {
        "source": document.source,
        "title": document.title,
        "section": section,
        "chunk_id": chunk_id,
        "strategy": strategy,
        "source_sha256": document.sha256,
        "start_line": segment.start_line,
        "end_line": segment.end_line,
        "char_count": len(segment.text),
        "word_count": len(segment.text.split()),
        "chunk_index": index,
    }
    return Chunk(chunk_id=chunk_id, text=segment.text, metadata=metadata)


def chunk_documents_fixed(
    documents: list[Document], *, chunk_size: int = 1600, overlap: int = 200
) -> list[Chunk]:
    _validate_window(chunk_size, overlap)
    chunks: list[Chunk] = []
    for document in documents:
        lines = document.text.splitlines(keepends=True)
        for index, segment in enumerate(_split_lines(lines, 1, chunk_size, overlap)):
            chunks.append(_chunk(document, "fixed", document.title, index, segment))
    return chunks


def _markdown_sections(document: Document) -> list[tuple[str, int, list[str]]]:
    lines = document.text.splitlines(keepends=True)
    heading_stack: list[tuple[int, str]] = []
    sections: list[tuple[str, int, list[str]]] = []
    current_start = 1
    current_lines: list[str] = []
    current_section = document.title

    for line_number, line in enumerate(lines, 1):
        match = HEADING_RE.match(line.rstrip("\n"))
        if match and current_lines:
            sections.append((current_section, current_start, current_lines))
            current_lines = []
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()
            heading_stack = [
                (old_level, value) for old_level, value in heading_stack if old_level < level
            ]
            heading_stack.append((level, title))
            current_section = " > ".join(value for _, value in heading_stack)
            current_start = line_number
        current_lines.append(line)
    if current_lines:
        sections.append((current_section, current_start, current_lines))
    return sections


def _has_markdown_content(lines: list[str]) -> bool:
    """Return whether lines contain content beyond headings and whitespace."""

    return any(
        stripped and HEADING_RE.fullmatch(stripped) is None
        for line in lines
        if (stripped := line.strip())
    )


def _python_sections(document: Document) -> list[tuple[str, int, list[str]]]:
    lines = document.text.splitlines(keepends=True)
    starts: list[tuple[int, str]] = []
    for line_number, line in enumerate(lines, 1):
        match = PYTHON_BLOCK_RE.match(line)
        if match:
            starts.append((line_number, match.group(1)))
    if not starts:
        return [(document.title, 1, lines)]
    if starts[0][0] != 1:
        starts.insert(0, (1, document.title))
    sections: list[tuple[str, int, list[str]]] = []
    for index, (start, title) in enumerate(starts):
        end = starts[index + 1][0] - 1 if index + 1 < len(starts) else len(lines)
        sections.append((title, start, lines[start - 1 : end]))
    return sections


def _plain_sections(document: Document) -> list[tuple[str, int, list[str]]]:
    lines = document.text.splitlines(keepends=True)
    sections: list[tuple[str, int, list[str]]] = []
    current: list[str] = []
    start = 1
    for line_number, line in enumerate(lines, 1):
        if not line.strip() and current:
            current.append(line)
            sections.append((document.title, start, current))
            current = []
            start = line_number + 1
        else:
            if not current:
                start = line_number
            current.append(line)
    if current:
        sections.append((document.title, start, current))
    return sections


def chunk_documents_structure(
    documents: list[Document], *, max_chunk_size: int = 2400, overlap: int = 200
) -> list[Chunk]:
    _validate_window(max_chunk_size, overlap)
    chunks: list[Chunk] = []
    for document in documents:
        is_markdown = document.path.suffix.lower() == ".md"
        if is_markdown:
            sections = _markdown_sections(document)
        elif document.path.suffix.lower() == ".py":
            sections = _python_sections(document)
        else:
            sections = _plain_sections(document)
        chunk_index = 0
        for section, start_line, lines in sections:
            if is_markdown and not _has_markdown_content(lines):
                continue
            for segment in _split_lines(lines, start_line, max_chunk_size, overlap):
                if is_markdown and not _has_markdown_content(segment.text.splitlines()):
                    continue
                chunks.append(_chunk(document, "structure", section, chunk_index, segment))
                chunk_index += 1
    return chunks
