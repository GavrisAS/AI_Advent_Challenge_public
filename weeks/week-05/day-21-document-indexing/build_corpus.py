"""Собрать воспроизводимый public-safe corpus Day 21 из публикуемой документации repo."""

from __future__ import annotations

from pathlib import Path

DAY_DIR = Path(__file__).resolve().parent
REPO_ROOT = DAY_DIR.parents[2]
CORPUS_DIR = DAY_DIR / "corpus"

SINGLE_DOCUMENTS = {
    "project-readme.md": REPO_ROOT / "README.md",
    "package-readme.md": REPO_ROOT / "packages/ai_advent_agent/README.md",
    "docs-development-rules.md": REPO_ROOT / "packages/docs/development-rules.md",
    "docs-examples.md": REPO_ROOT / "packages/docs/examples.md",
    "docs-cli.md": REPO_ROOT / "packages/docs/cli.md",
}


def _normalize_markdown(content: str) -> str:
    return "\n".join(line.rstrip() for line in content.splitlines()).rstrip() + "\n"


def _combined_week(week: int) -> str:
    week_dir = REPO_ROOT / f"weeks/week-{week:02d}"
    parts = [
        f"# Public README документов Week {week:02d}",
        "",
        "Стабильная копия public-safe README завершённых дней для corpus Day 21.",
        "",
    ]
    for readme in sorted(week_dir.glob("day-*/README.md")):
        parts.extend(
            [
                f"<!-- source: {readme.relative_to(REPO_ROOT).as_posix()} -->",
                "",
                _normalize_markdown(readme.read_text(encoding="utf-8")).rstrip(),
                "",
            ]
        )
    return "\n".join(parts).rstrip() + "\n"


def main() -> None:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    for name, source in SINGLE_DOCUMENTS.items():
        (CORPUS_DIR / name).write_text(
            _normalize_markdown(source.read_text(encoding="utf-8")), encoding="utf-8"
        )
    for week in range(1, 5):
        (CORPUS_DIR / f"week-{week:02d}-day-readmes.md").write_text(
            _combined_week(week), encoding="utf-8"
        )

    files = sorted(path for path in CORPUS_DIR.glob("*.md") if path.name != "README.md")
    char_count = sum(len(path.read_text(encoding="utf-8")) for path in files)
    word_count = sum(len(path.read_text(encoding="utf-8").split()) for path in files)
    manifest = [
        "# Corpus Day 21",
        "",
        "Curated corpus собран из документов, которые уже входят в разрешённую public-часть "
        "репозитория: корневого README, README актуального package, package docs и README "
        "завершённых дней Week 01–04.",
        "",
        "В corpus намеренно не входят `learning/`, `notes/`, `memory-bank/`, `codex-log.md`, "
        "секреты, `.env`, runtime state и приватные artifacts. Файлы являются стабильными "
        "копиями на момент сдачи Day 21, поэтому snapshot demo не зависит от последующих "
        "изменений исходных документов.",
        "",
        "## Состав",
        "",
        *[f"- `{path.name}`" for path in files],
        "",
        "## Объём",
        "",
        f"- Документов с основным содержимым: {len(files)}.",
        f"- Символов: {char_count:,}.",
        f"- Слов: {word_count:,}.",
        f"- Грубая оценка при 500 словах на страницу: {word_count / 500:.1f} страниц.",
        "",
        "`README.md` также индексируется как manifest corpus. Для пересборки из текущего "
        "private repo используется `../build_corpus.py`; для воспроизведения Day 21 пересборка "
        "не нужна.",
        "",
    ]
    (CORPUS_DIR / "README.md").write_text("\n".join(manifest), encoding="utf-8")


if __name__ == "__main__":
    main()
