"""Configuration objects for the AI Advent Challenge training agent."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

AgentStrategy = Literal["direct", "step_by_step"]
SummaryMode = Literal["off", "llm"]
ContextStrategy = Literal["sliding_window", "sticky_facts", "branching"]

DEFAULT_API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_CONTEXT_FILE = Path(".agent_context/messages.json")
DEFAULT_SUMMARY_FILE = Path(".agent_context/summary.json")
DEFAULT_FACTS_FILE = Path(".agent_context/facts.json")
DEFAULT_BRANCHES_FILE = Path(".agent_context/branches.json")
DEFAULT_TOKEN_REPORT_FILE = Path(".agent_context/token_reports.jsonl")
DEFAULT_SHORT_TERM_MEMORY_FILE = Path(".agent_context/short_term_memory.json")
DEFAULT_WORKING_MEMORY_FILE = Path(".agent_context/working_memory.json")
DEFAULT_LONG_TERM_MEMORY_FILE = Path(".agent_context/long_term_memory.json")
DEFAULT_MEMORY_EVENTS_FILE = Path(".agent_context/memory_events.jsonl")
DEFAULT_USER_PROFILES_FILE = Path(".agent_context/user_profiles.json")
DEFAULT_PROFILE_EVENTS_FILE = Path(".agent_context/profile_events.jsonl")
DEFAULT_TASK_STATE_FILE = Path(".agent_context/task_state.json")
DEFAULT_TASK_EVENTS_FILE = Path(".agent_context/task_events.jsonl")
DEFAULT_CONTEXT_WINDOW_TOKENS = 1_000_000
DEFAULT_WARN_CONTEXT_RATIO = 0.80
DEFAULT_RECENT_MESSAGES_LIMIT = 6
DEFAULT_SUMMARIZE_EVERY_MESSAGES = 8
DEFAULT_SUMMARY_MAX_TOKENS = 600
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

    # Token/context settings.
    context_window_tokens: int = DEFAULT_CONTEXT_WINDOW_TOKENS
    warn_context_ratio: float = DEFAULT_WARN_CONTEXT_RATIO
    overflow_policy: ContextOverflowPolicy = ContextOverflowPolicy.ERROR

    # Prices are intentionally zero by default: fill actual provider prices in .env.
    input_price_per_1m_tokens: float = 0.0
    output_price_per_1m_tokens: float = 0.0

    # Day 9 summary-memory settings.
    summary_mode: SummaryMode = "off"
    recent_messages_limit: int = DEFAULT_RECENT_MESSAGES_LIMIT
    summarize_every_messages: int = DEFAULT_SUMMARIZE_EVERY_MESSAGES
    summary_max_tokens: int = DEFAULT_SUMMARY_MAX_TOKENS

    # Day 10 context-management strategy.
    context_strategy: ContextStrategy = "sliding_window"

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
        if self.summary_mode not in {"off", "llm"}:
            raise ValueError("summary_mode должен быть off или llm")
        if self.recent_messages_limit < 0:
            raise ValueError("recent_messages_limit не может быть отрицательным")
        if self.summarize_every_messages <= 0:
            raise ValueError("summarize_every_messages должен быть больше 0")
        if self.summary_max_tokens <= 0:
            raise ValueError("summary_max_tokens должен быть больше 0")
        if self.context_strategy not in {"sliding_window", "sticky_facts", "branching"}:
            raise ValueError(
                "context_strategy должен быть sliding_window, sticky_facts или branching"
            )


def parse_overflow_policy(value: str | ContextOverflowPolicy) -> ContextOverflowPolicy:
    """Parse a CLI/env value into ContextOverflowPolicy."""

    if isinstance(value, ContextOverflowPolicy):
        return value

    try:
        return ContextOverflowPolicy(value.strip().lower())
    except ValueError as error:
        allowed = ", ".join(item.value for item in ContextOverflowPolicy)
        raise ValueError(f"overflow_policy должен быть одним из: {allowed}") from error
