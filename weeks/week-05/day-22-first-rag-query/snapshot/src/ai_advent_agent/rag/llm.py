"""LLM adapters для RAG QA: production DeepSeek и deterministic fake."""

from __future__ import annotations

import os
from typing import Protocol

from ai_advent_agent.config import AgentConfig
from ai_advent_agent.env import load_env_file
from ai_advent_agent.llm_client import LLMClient


class RagLLM(Protocol):
    provider: str
    model: str

    def generate(self, prompt: str) -> str: ...


class FakeLLM:
    """Deterministic offline client for tests and smoke demos."""

    provider = "fake"
    model = "deterministic-context-echo"

    def generate(self, prompt: str) -> str:
        if "Контекст:" not in prompt:
            return (
                "Без внутренней базы проекта точный ответ дать нельзя; требуется проверить "
                "документацию проекта."
            )
        context = prompt.split("Контекст:\n", 1)[1]
        excerpts: list[str] = []
        sources: list[str] = []
        current_source = ""
        current_section = ""
        current_chunk = ""
        for line in context.splitlines():
            if line.startswith("source: "):
                current_source = line.removeprefix("source: ")
            elif line.startswith("section: "):
                current_section = line.removeprefix("section: ")
            elif line.startswith("chunk_id: "):
                current_chunk = line.removeprefix("chunk_id: ")
                sources.append(f"- {current_source} | {current_section} | {current_chunk}")
            elif line and not line.startswith(("[Фрагмент ", "text:")):
                excerpts.append(line)
        body = " ".join(excerpts)[:1800].strip()
        return f"{body}\n\nИсточники\n" + "\n".join(sources)


class DeepSeekRagLLM:
    provider = "deepseek"

    def __init__(self, model: str = "deepseek-v4-flash") -> None:
        load_env_file()
        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "Не задан DEEPSEEK_API_KEY. Добавьте ключ в окружение или используйте "
                "--llm-provider fake для offline smoke demo."
            )
        self.model = model
        self._client = LLMClient(api_key=api_key)

    def generate(self, prompt: str) -> str:
        config = AgentConfig(model=self.model, temperature=0.1, max_tokens=1400)
        result = self._client.chat([{"role": "user", "content": prompt}], config)
        return result.content
