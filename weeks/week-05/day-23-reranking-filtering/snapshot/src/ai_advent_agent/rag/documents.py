"""Загрузка public-safe текстовых документов для локального индекса."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

SUPPORTED_SUFFIXES = frozenset({".md", ".txt", ".py"})
SKIPPED_DIRECTORY_NAMES = frozenset(
    {"__pycache__", ".git", ".tmp", ".venv", "artifacts", "node_modules"}
)


@dataclass(frozen=True, slots=True)
class Document:
    source: str
    path: Path
    relative_path: str
    title: str
    text: str
    line_count: int
    char_count: int
    word_count: int
    sha256: str


def _is_skipped(path: Path, corpus_dir: Path) -> bool:
    relative = path.relative_to(corpus_dir)
    return any(
        part.startswith(".") or part in SKIPPED_DIRECTORY_NAMES for part in relative.parts[:-1]
    ) or relative.name.startswith(".")


def _title_for(path: Path, text: str) -> str:
    if path.suffix.lower() == ".md":
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
    return path.stem.replace("-", " ").replace("_", " ").strip().title()


def load_documents(corpus_dir: Path | str) -> list[Document]:
    """Загрузить поддерживаемые файлы corpus в стабильном лексикографическом порядке."""

    root = Path(corpus_dir).resolve()
    if not root.is_dir():
        raise ValueError(f"Corpus directory does not exist: {root}")

    documents: list[Document] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        if _is_skipped(path, root):
            continue
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"Document is not valid UTF-8: {path}") from error
        relative_path = path.relative_to(root).as_posix()
        documents.append(
            Document(
                source=f"corpus/{relative_path}",
                path=path,
                relative_path=relative_path,
                title=_title_for(path, text),
                text=text,
                line_count=len(text.splitlines()),
                char_count=len(text),
                word_count=len(text.split()),
                sha256=sha256(raw).hexdigest(),
            )
        )
    if not documents:
        raise ValueError(f"Corpus contains no supported documents: {root}")
    return documents
