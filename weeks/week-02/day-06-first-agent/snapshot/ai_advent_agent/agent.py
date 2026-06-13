"""Stateful minimal LLM agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai_advent_agent.config import AgentConfig, AgentStrategy
from ai_advent_agent.llm_client import ChatResult, DeepSeekError, LLMClient, Message

STEP_BY_STEP_SUFFIX = (
    "\n\nРешай пошагово. "
    "Проверь условия задачи и возможные ограничения. "
    "В конце отдельно укажи итоговый ответ."
)


@dataclass(slots=True)
class AgentResponse:
    """Public response object returned by SimpleAgent.ask()."""

    content: str
    finish_reason: str | None
    usage: dict[str, Any]
    elapsed_seconds: float
    model: str
    strategy: AgentStrategy
    message_count: int
    has_reasoning_content: bool = False

    @property
    def prompt_tokens(self) -> int | None:
        value = self.usage.get("prompt_tokens")
        return int(value) if value is not None else None

    @property
    def completion_tokens(self) -> int | None:
        value = self.usage.get("completion_tokens")
        return int(value) if value is not None else None

    @property
    def total_tokens(self) -> int | None:
        value = self.usage.get("total_tokens")
        return int(value) if value is not None else None


class SimpleAgent:
    """Minimal separate agent entity.

    Responsibilities:
    - stores session messages;
    - applies direct or step-by-step strategy;
    - delegates HTTP transport to LLMClient;
    - saves successful assistant answers back to the session history;
    - exposes reset/history methods for external interfaces.
    """

    def __init__(self, *, client: LLMClient, config: AgentConfig) -> None:
        self.client = client
        self.config = config
        self.config.validate()
        self.messages: list[Message] = []
        self.reset()

    def ask(self, user_input: str, *, strategy: AgentStrategy | None = None) -> AgentResponse:
        """Send a user request to the LLM and save the answer in session history."""

        cleaned_input = user_input.strip()
        if not cleaned_input:
            raise ValueError("user_input не должен быть пустым")

        active_strategy = strategy or self.config.strategy
        if active_strategy not in {"direct", "step_by_step"}:
            raise ValueError("strategy должен быть direct или step_by_step")

        user_message = self._build_user_message(cleaned_input, active_strategy)
        self.messages.append(user_message)

        try:
            result = self.client.chat(self.messages, self.config)
        except DeepSeekError:
            # Do not keep failed user messages in the conversational state.
            self.messages.pop()
            raise

        self.messages.append({"role": "assistant", "content": result.content})
        return self._to_agent_response(result, active_strategy)

    def reset(self) -> None:
        """Clear session state and keep only the system prompt."""

        self.messages = [{"role": "system", "content": self.config.system_prompt}]

    def get_history(self) -> list[Message]:
        """Return a shallow copy of the current session history."""

        return [message.copy() for message in self.messages]

    def set_strategy(self, strategy: AgentStrategy) -> None:
        """Change default strategy for future calls."""

        if strategy not in {"direct", "step_by_step"}:
            raise ValueError("strategy должен быть direct или step_by_step")
        self.config.strategy = strategy

    @staticmethod
    def _build_user_message(user_input: str, strategy: AgentStrategy) -> Message:
        if strategy == "step_by_step":
            return {"role": "user", "content": f"{user_input}{STEP_BY_STEP_SUFFIX}"}
        return {"role": "user", "content": user_input}

    def _to_agent_response(self, result: ChatResult, strategy: AgentStrategy) -> AgentResponse:
        return AgentResponse(
            content=result.content,
            finish_reason=result.finish_reason,
            usage=result.usage,
            elapsed_seconds=result.elapsed_seconds,
            model=result.model,
            strategy=strategy,
            message_count=len(self.messages),
            has_reasoning_content=result.has_reasoning_content,
        )
