"""Stateful minimal LLM agent with persistent context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai_advent_agent.config import AgentConfig, AgentStrategy
from ai_advent_agent.llm_client import ChatResult, DeepSeekError, LLMClient, Message
from ai_advent_agent.storage import ContextStorageError, JsonContextStore

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
    context_saved: bool
    context_path: str | None
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
    - restores messages from persistent JSON context on startup;
    - saves messages to JSON after successful assistant answers;
    - applies direct or step-by-step strategy;
    - delegates HTTP transport to LLMClient;
    - exposes reset/history methods for external interfaces.
    """

    def __init__(
        self,
        *,
        client: LLMClient,
        config: AgentConfig,
        context_store: JsonContextStore | None = None,
        load_context: bool = True,
    ) -> None:
        self.client = client
        self.config = config
        self.config.validate()
        self.context_store = context_store
        self.messages: list[Message] = []

        if self.context_store is not None and load_context:
            self.messages = self._load_or_init_context()
        else:
            self.reset(save=False)

    @property
    def context_path(self) -> str | None:
        if self.context_store is None:
            return None
        return str(self.context_store.path)

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
        self.save_context()
        return self._to_agent_response(result, active_strategy)

    def reset(self, *, save: bool = True) -> None:
        """Clear session state and keep only the current system prompt."""

        self.messages = [{"role": "system", "content": self.config.system_prompt}]
        if save:
            self.save_context()

    def clear_context_file(self) -> None:
        """Delete persisted context and reset in-memory state to system prompt."""

        self.messages = [{"role": "system", "content": self.config.system_prompt}]
        if self.context_store is not None:
            self.context_store.clear()

    def save_context(self) -> None:
        """Persist current messages if a context store is configured."""

        if self.context_store is not None:
            self.context_store.save(self.messages)

    def get_history(self) -> list[Message]:
        """Return a shallow copy of the current session history."""

        return [message.copy() for message in self.messages]

    def set_strategy(self, strategy: AgentStrategy) -> None:
        """Change default strategy for future calls."""

        if strategy not in {"direct", "step_by_step"}:
            raise ValueError("strategy должен быть direct или step_by_step")
        self.config.strategy = strategy

    def _load_or_init_context(self) -> list[Message]:
        if self.context_store is None:
            return [{"role": "system", "content": self.config.system_prompt}]

        loaded_messages = self.context_store.load()
        if not loaded_messages:
            return [{"role": "system", "content": self.config.system_prompt}]

        # Keep the saved conversation exactly when it already contains a system prompt.
        if loaded_messages[0]["role"] == "system":
            return loaded_messages

        # Older or manually edited files may contain only user/assistant messages.
        return [{"role": "system", "content": self.config.system_prompt}, *loaded_messages]

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
            context_saved=self.context_store is not None,
            context_path=self.context_path,
            has_reasoning_content=result.has_reasoning_content,
        )


__all__ = [
    "AgentResponse",
    "ContextStorageError",
    "JsonContextStore",
    "SimpleAgent",
]
