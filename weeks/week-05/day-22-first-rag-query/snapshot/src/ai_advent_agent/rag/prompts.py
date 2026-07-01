"""Prompt builders для baseline и grounded RAG-ответов."""

from __future__ import annotations

from ai_advent_agent.rag.search import RetrievedContext


def build_baseline_prompt(question: str) -> str:
    """Build a prompt that deliberately has no retrieved project context."""

    return (
        "Ты отвечаешь на вопрос о проекте без доступа к его внутренней базе знаний. "
        "Не придумывай внутренние правила, команды или файлы проекта. Если точных данных нет, "
        "явно укажи неопределённость.\n\n"
        f"Вопрос: {question.strip()}"
    )


def build_rag_prompt(question: str, context: RetrievedContext) -> str:
    """Build a grounded prompt with explicit source metadata."""

    blocks = []
    for rank, chunk in enumerate(context.chunks, 1):
        blocks.append(
            "\n".join(
                (
                    f"[Фрагмент {rank}]",
                    f"source: {chunk.source}",
                    f"section: {chunk.section}",
                    f"chunk_id: {chunk.chunk_id}",
                    f"text:\n{chunk.text}",
                )
            )
        )
    rendered_context = "\n\n".join(blocks) or "[Контекст пуст]"
    return (
        "Ответь только на основе предоставленного контекста. Не добавляй факты вне контекста. "
        "Если контекста недостаточно, прямо скажи: «Найденных источников недостаточно». "
        "В конце добавь раздел «Источники» и перечисли использованные source, section и chunk_id."
        f"\n\nВопрос: {question.strip()}\n\nКонтекст:\n{rendered_context}"
    )
