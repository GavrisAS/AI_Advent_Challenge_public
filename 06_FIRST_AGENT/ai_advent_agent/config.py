"""Configuration objects for the Day 6 agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AgentStrategy = Literal["direct", "step_by_step"]

DEFAULT_API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_SYSTEM_PROMPT = (
    "Ты полезный AI-ассистент. Отвечай на русском языке. "
    "Давай практичный, структурированный и проверяемый ответ."
)


@dataclass(slots=True)
class AgentConfig:
    """Runtime settings for SimpleAgent and LLMClient."""

    model: str = DEFAULT_MODEL
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    temperature: float = 0.7
    max_tokens: int = 1000
    strategy: AgentStrategy = "direct"
    thinking_type: Literal["disabled", "enabled"] = "disabled"
    reasoning_effort: str | None = None
    stop: list[str] | None = None

    def validate(self) -> None:
        """Validate values early to get readable errors before API calls."""

        if not self.model.strip():
            raise ValueError("model не должен быть пустым")
        if not self.system_prompt.strip():
            raise ValueError("system_prompt не должен быть пустым")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens должен быть больше 0")
        if not 0 <= self.temperature <= 2:
            raise ValueError("temperature должен быть в диапазоне от 0 до 2")
        if self.strategy not in {"direct", "step_by_step"}:
            raise ValueError("strategy должен быть direct или step_by_step")
        if self.thinking_type not in {"disabled", "enabled"}:
            raise ValueError("thinking_type должен быть disabled или enabled")
