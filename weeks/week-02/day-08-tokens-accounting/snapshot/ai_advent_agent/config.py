"""Configuration objects for the Day 8 token-aware agent."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

AgentStrategy = Literal["direct", "step_by_step"]

DEFAULT_API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_CONTEXT_FILE = Path(".agent_context/messages.json")
DEFAULT_TOKEN_REPORT_FILE = Path(".agent_context/token_reports.jsonl")
DEFAULT_CONTEXT_WINDOW_TOKENS = 1_000_000
DEFAULT_WARN_CONTEXT_RATIO = 0.80
DEFAULT_SYSTEM_PROMPT = (
    "Ты полезный AI-ассистент. Отвечай на русском языке. "
    "Давай практичный, структурированный и проверяемый ответ."
)


class ContextOverflowPolicy(StrEnum):
    """What to do when the estimated request exceeds the context window."""

    ERROR = "error"
    NO_TRIM = "no_trim"
    SLIDING_WINDOW = "sliding_window"


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

    # Day 8 token/context settings.
    context_window_tokens: int = DEFAULT_CONTEXT_WINDOW_TOKENS
    warn_context_ratio: float = DEFAULT_WARN_CONTEXT_RATIO
    overflow_policy: ContextOverflowPolicy = ContextOverflowPolicy.ERROR

    # Prices are intentionally zero by default: fill actual provider prices in .env.
    input_price_per_1m_tokens: float = 0.0
    output_price_per_1m_tokens: float = 0.0

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
        if self.context_window_tokens <= 0:
            raise ValueError("context_window_tokens должен быть больше 0")
        if not 0 < self.warn_context_ratio <= 1:
            raise ValueError("warn_context_ratio должен быть в диапазоне (0, 1]")
        if self.input_price_per_1m_tokens < 0:
            raise ValueError("input_price_per_1m_tokens не может быть отрицательной")
        if self.output_price_per_1m_tokens < 0:
            raise ValueError("output_price_per_1m_tokens не может быть отрицательной")


def parse_overflow_policy(value: str | ContextOverflowPolicy) -> ContextOverflowPolicy:
    """Parse a CLI/env value into ContextOverflowPolicy."""

    if isinstance(value, ContextOverflowPolicy):
        return value

    try:
        return ContextOverflowPolicy(value.strip().lower())
    except ValueError as error:
        allowed = ", ".join(item.value for item in ContextOverflowPolicy)
        raise ValueError(f"overflow_policy должен быть одним из: {allowed}") from error
