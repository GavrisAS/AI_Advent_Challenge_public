"""Stateful minimal LLM agent with persistent context and token tracking."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from ai_advent_agent.config import AgentConfig, AgentStrategy, ContextOverflowPolicy, SummaryMode
from ai_advent_agent.llm_client import ChatClient, ChatResult, DeepSeekError, Message
from ai_advent_agent.storage import (
    ContextStorageError,
    JsonContextStore,
    JsonSummaryStore,
    SummaryMemory,
)
from ai_advent_agent.token_counter import ApproxTokenCounter, TokenBreakdown
from ai_advent_agent.token_report import TokenReport, TokenReportStore

STEP_BY_STEP_SUFFIX = (
    "\n\nРешай пошагово. "
    "Проверь условия задачи и возможные ограничения. "
    "В конце отдельно укажи итоговый ответ."
)

SUMMARY_SYSTEM_PROMPT = (
    "Ты модуль memory compression внутри AI-агента. "
    "Сожми старую историю диалога в краткую, фактическую summary-память. "
    "Сохраняй имена, цели, решения, ограничения, открытые вопросы и важные факты. "
    "Не добавляй факты, которых нет в истории."
)


class ContextOverflowError(RuntimeError):
    """Raised when the estimated request does not fit the configured context window."""

    def __init__(self, message: str, report: TokenReport) -> None:
        super().__init__(message)
        self.report = report


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
    token_report: TokenReport
    has_reasoning_content: bool = False

    @property
    def summary_active(self) -> bool:
        return self.token_report.summary_active

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


@dataclass(slots=True)
class RequestPreparation:
    """Prepared request and the persistent history base to save after completion."""

    request_messages: list[Message]
    persistent_messages: list[Message]
    report: TokenReport


class SimpleAgent:
    """Minimal separate agent entity.

    Responsibilities:
    - stores session messages;
    - restores messages from persistent JSON context on startup;
    - saves messages to JSON after successful assistant answers;
    - estimates tokens before/after each request;
    - applies context-window overflow policy;
    - applies direct or step-by-step strategy;
    - delegates HTTP transport to LLMClient;
    - exposes reset/history/token methods for external interfaces.
    """

    def __init__(
        self,
        *,
        client: ChatClient,
        config: AgentConfig,
        context_store: JsonContextStore | None = None,
        summary_store: JsonSummaryStore | None = None,
        token_report_store: TokenReportStore | None = None,
        token_counter: ApproxTokenCounter | None = None,
        load_context: bool = True,
    ) -> None:
        self.client = client
        self.config = config
        self.config.validate()
        self.context_store = context_store
        self.summary_store = summary_store
        self.token_report_store = token_report_store
        self.token_counter = token_counter or ApproxTokenCounter()
        self.last_token_report: TokenReport | None = None
        self.summary_memory = SummaryMemory()
        self.messages: list[Message] = []

        if self.context_store is not None and load_context:
            self.messages = self._load_or_init_context()
        else:
            self.reset(save=False, clear_reports=False)
        if self.summary_store is not None and load_context:
            self.summary_memory = self.summary_store.load()

    @property
    def context_path(self) -> str | None:
        if self.context_store is None:
            return None
        return str(self.context_store.path)

    @property
    def token_report_path(self) -> str | None:
        if self.token_report_store is None:
            return None
        return str(self.token_report_store.path)

    @property
    def summary_path(self) -> str | None:
        if self.summary_store is None:
            return None
        return str(self.summary_store.path)

    def ask(self, user_input: str, *, strategy: AgentStrategy | None = None) -> AgentResponse:
        """Send a user request to the LLM, save answer and update token report."""

        cleaned_input = user_input.strip()
        if not cleaned_input:
            raise ValueError("user_input не должен быть пустым")

        active_strategy = strategy or self.config.strategy
        if active_strategy not in {"direct", "step_by_step"}:
            raise ValueError("strategy должен быть direct или step_by_step")

        user_message = self._build_user_message(cleaned_input, active_strategy)
        original_messages = self.get_history()
        original_summary = SummaryMemory(
            summary=self.summary_memory.summary,
            summarized_message_count=self.summary_memory.summarized_message_count,
            updated_at=self.summary_memory.updated_at,
        )

        try:
            preparation = self._prepare_messages_for_request(user_message)
            result = self.client.chat(preparation.request_messages, self.config)
        except (ContextOverflowError, DeepSeekError):
            self.messages = original_messages
            self.summary_memory = original_summary
            raise

        self.messages = preparation.persistent_messages
        self.messages.append(user_message.copy())
        self.messages.append({"role": "assistant", "content": result.content})
        self._complete_token_report(preparation.report, result)
        self.last_token_report = preparation.report
        self._save_token_report(preparation.report)
        self.save_context()
        self.save_summary()
        return self._to_agent_response(result, active_strategy, preparation.report)

    def reset(self, *, save: bool = True, clear_reports: bool = True) -> None:
        """Clear session state and keep only the current system prompt."""

        self.messages = [{"role": "system", "content": self.config.system_prompt}]
        self.summary_memory = SummaryMemory()
        self.last_token_report = None
        if clear_reports and self.token_report_store is not None:
            self.token_report_store.clear()
        if save:
            self.save_context()
            self.save_summary()

    def clear_context_file(self) -> None:
        """Delete persisted context and reset in-memory state to system prompt."""

        self.messages = [{"role": "system", "content": self.config.system_prompt}]
        self.summary_memory = SummaryMemory()
        self.last_token_report = None
        if self.context_store is not None:
            self.context_store.clear()
        if self.summary_store is not None:
            self.summary_store.clear()
        if self.token_report_store is not None:
            self.token_report_store.clear()

    def save_context(self) -> None:
        """Persist current messages if a context store is configured."""

        if self.context_store is not None:
            self.context_store.save(self.messages)

    def save_summary(self) -> None:
        """Persist current summary memory if a summary store is configured."""

        if self.summary_store is not None:
            self.summary_store.save(self.summary_memory)

    def get_history(self) -> list[Message]:
        """Return a shallow copy of the current session history."""

        return [message.copy() for message in self.messages]

    def get_token_breakdown(self) -> TokenBreakdown:
        """Return estimated tokens for the currently loaded history."""

        return self.token_counter.breakdown(self.messages)

    def estimate_text_tokens(self, text: str) -> int:
        """Estimate tokens for arbitrary text using the same local counter."""

        return self.token_counter.count_text(text)

    def build_file_token_report(self, file_content: str) -> TokenReport:
        """Dry-run token report for adding file content as the next user message."""

        user_message: Message = {"role": "user", "content": file_content}
        preparation = self._prepare_messages_for_request(
            user_message,
            dry_run=True,
            allow_error_report=True,
        )
        return preparation.report

    def set_strategy(self, strategy: AgentStrategy) -> None:
        """Change default strategy for future calls."""

        if strategy not in {"direct", "step_by_step"}:
            raise ValueError("strategy должен быть direct или step_by_step")
        self.config.strategy = strategy

    def set_overflow_policy(self, policy: ContextOverflowPolicy | str) -> None:
        """Change context overflow behavior for future calls."""

        self.config.overflow_policy = ContextOverflowPolicy(policy)

    def set_summary_mode(self, mode: SummaryMode) -> None:
        """Change summary mode for future calls."""

        if mode not in {"off", "llm"}:
            raise ValueError("summary_mode должен быть off или llm")
        self.config.summary_mode = mode

    def _prepare_messages_for_request(
        self,
        user_message: Message,
        *,
        dry_run: bool = False,
        allow_error_report: bool = False,
    ) -> RequestPreparation:
        persistent_messages = self._messages_after_optional_summary(dry_run=dry_run)
        history_tokens_before = self.token_counter.count_messages(self.messages)
        request_tokens = self.token_counter.count_text(user_message["content"])
        request_messages = self._build_request_messages(persistent_messages, user_message)
        prompt_tokens = self.token_counter.count_messages(request_messages)
        projected_total = prompt_tokens + self.config.max_tokens
        report = self._build_preflight_report(
            request_tokens=request_tokens,
            history_tokens_before=history_tokens_before,
            prompt_tokens=prompt_tokens,
            projected_total=projected_total,
            trimmed_messages_count=0,
            overflow_detected=projected_total > self.config.context_window_tokens,
            request_messages=request_messages,
        )

        if projected_total <= self.config.context_window_tokens:
            return RequestPreparation(request_messages, persistent_messages, report)

        policy = self.config.overflow_policy
        if policy == ContextOverflowPolicy.NO_TRIM:
            return RequestPreparation(request_messages, persistent_messages, report)

        if policy == ContextOverflowPolicy.ERROR:
            if dry_run and allow_error_report:
                return RequestPreparation(request_messages, persistent_messages, report)
            raise ContextOverflowError(self._overflow_message(report), report)

        if policy == ContextOverflowPolicy.SLIDING_WINDOW:
            trimmed_messages, trimmed_count = self._trim_messages_sliding_window(request_messages)
            trimmed_prompt_tokens = self.token_counter.count_messages(trimmed_messages)
            trimmed_projected_total = trimmed_prompt_tokens + self.config.max_tokens
            trimmed_report = self._build_preflight_report(
                request_tokens=request_tokens,
                history_tokens_before=history_tokens_before,
                prompt_tokens=trimmed_prompt_tokens,
                projected_total=trimmed_projected_total,
                trimmed_messages_count=trimmed_count,
                overflow_detected=True,
                request_messages=trimmed_messages,
            )

            if trimmed_projected_total > self.config.context_window_tokens:
                if dry_run and allow_error_report:
                    return RequestPreparation(trimmed_messages, persistent_messages, trimmed_report)
                raise ContextOverflowError(self._overflow_message(trimmed_report), trimmed_report)
            trimmed_persistent_messages = [
                message.copy()
                for message in trimmed_messages
                if not self._is_summary_message(message)
            ]
            return RequestPreparation(trimmed_messages, trimmed_persistent_messages, trimmed_report)

        raise ValueError(f"Неизвестная overflow policy: {policy}")

    def _messages_after_optional_summary(self, *, dry_run: bool) -> list[Message]:
        if self.config.summary_mode == "off":
            return [message.copy() for message in self.messages]

        if self.config.summary_mode != "llm":
            raise ValueError(f"Неизвестный summary_mode: {self.config.summary_mode}")

        system_message = self._system_message_from_history(self.messages)
        conversation_messages = [message.copy() for message in self.messages[1:]]
        recent_limit = self.config.recent_messages_limit
        summarizable_count = max(0, len(conversation_messages) - recent_limit)
        if summarizable_count < self.config.summarize_every_messages:
            return [message.copy() for message in self.messages]

        summarizable = conversation_messages[:summarizable_count]
        recent = conversation_messages[summarizable_count:]
        if not dry_run:
            self.summary_memory = self._summarize_messages(summarizable)
            self.messages = [system_message, *recent]
        return [system_message, *recent]

    def _summarize_messages(self, messages: list[Message]) -> SummaryMemory:
        prompt = self._build_summary_prompt(messages)
        summary_config = replace(
            self.config,
            max_tokens=self.config.summary_max_tokens,
            strategy="direct",
            thinking_type="disabled",
        )
        result = self.client.chat(
            [
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            summary_config,
        )
        return SummaryMemory(
            summary=result.content.strip(),
            summarized_message_count=self.summary_memory.summarized_message_count + len(messages),
        )

    def _build_summary_prompt(self, messages: list[Message]) -> str:
        parts = [
            "Обнови summary-память по старой истории диалога.",
            "Верни только готовую summary на русском языке.",
        ]
        if self.summary_memory.active:
            parts.extend(["Текущая summary:", self.summary_memory.summary])
        parts.append("Новые сообщения для сжатия:")
        for index, message in enumerate(messages, start=1):
            parts.append(f"[{index}] {message['role']}: {message['content']}")
        return "\n\n".join(parts)

    def _build_request_messages(
        self,
        persistent_messages: list[Message],
        user_message: Message,
    ) -> list[Message]:
        request_messages = [message.copy() for message in persistent_messages]
        if self.config.summary_mode == "llm" and self.summary_memory.active:
            insert_at = 1 if request_messages and request_messages[0]["role"] == "system" else 0
            request_messages.insert(insert_at, self._summary_message())
        request_messages.append(user_message.copy())
        return request_messages

    def _summary_message(self) -> Message:
        return {
            "role": "system",
            "content": (
                "Summary предыдущей истории диалога. Используй её как память, "
                "но не считай дословной полной историей:\n"
                f"{self.summary_memory.summary}"
            ),
        }

    @staticmethod
    def _is_summary_message(message: Message) -> bool:
        return message.get("role") == "system" and message.get("content", "").startswith(
            "Summary предыдущей истории диалога."
        )

    def _system_message_from_history(self, messages: list[Message]) -> Message:
        if messages and messages[0]["role"] == "system":
            return messages[0].copy()
        return {"role": "system", "content": self.config.system_prompt}

    def _trim_messages_sliding_window(self, messages: list[Message]) -> tuple[list[Message], int]:
        if not messages:
            return [], 0

        trimmed = [message.copy() for message in messages]
        removed = 0

        while (
            self.token_counter.count_messages(trimmed) + self.config.max_tokens
            > self.config.context_window_tokens
        ):
            removable_index = self._oldest_removable_index(trimmed)
            if removable_index is None:
                break
            trimmed.pop(removable_index)
            removed += 1

        return trimmed, removed

    @staticmethod
    def _oldest_removable_index(messages: list[Message]) -> int | None:
        # Preserve the first system message and the newest user request.
        if len(messages) <= 2:
            return None
        for index in range(1, len(messages) - 1):
            if messages[index].get("role") != "system":
                return index
        return None

    def _build_preflight_report(
        self,
        *,
        request_tokens: int,
        history_tokens_before: int,
        prompt_tokens: int,
        projected_total: int,
        trimmed_messages_count: int,
        overflow_detected: bool,
        request_messages: list[Message],
    ) -> TokenReport:
        context_ratio = prompt_tokens / self.config.context_window_tokens
        projected_ratio = projected_total / self.config.context_window_tokens
        return TokenReport(
            request_tokens_estimated=request_tokens,
            history_tokens_before_estimated=history_tokens_before,
            prompt_tokens_estimated=prompt_tokens,
            projected_total_tokens_estimated=projected_total,
            context_window_tokens=self.config.context_window_tokens,
            context_usage_ratio=context_ratio,
            projected_usage_ratio=projected_ratio,
            warn_threshold_reached=projected_ratio >= self.config.warn_context_ratio,
            overflow_detected=overflow_detected,
            overflow_policy=self.config.overflow_policy.value,
            trimmed_messages_count=trimmed_messages_count,
            summary_active=self.config.summary_mode == "llm" and self.summary_memory.active,
            summary_tokens_estimated=self._summary_tokens_in_request(request_messages),
            summarized_messages_count=self.summary_memory.summarized_message_count,
        )

    def _complete_token_report(self, report: TokenReport, result: ChatResult) -> None:
        response_tokens_estimated = self.token_counter.count_text(result.content)
        report.response_tokens_estimated = response_tokens_estimated
        report.history_tokens_after_response_estimated = self.token_counter.count_messages(
            self.messages
        )
        report.prompt_tokens_actual = self._optional_int(result.usage.get("prompt_tokens"))
        report.completion_tokens_actual = self._optional_int(result.usage.get("completion_tokens"))
        report.total_tokens_actual = self._optional_int(result.usage.get("total_tokens"))
        report.elapsed_seconds = result.elapsed_seconds

        input_tokens = report.prompt_tokens_actual or report.prompt_tokens_estimated
        output_tokens = report.completion_tokens_actual or report.response_tokens_estimated or 0
        input_cost = input_tokens * self.config.input_price_per_1m_tokens / 1_000_000
        output_cost = output_tokens * self.config.output_price_per_1m_tokens / 1_000_000
        report.estimated_input_cost_usd = input_cost
        report.estimated_output_cost_usd = output_cost
        report.estimated_total_cost_usd = input_cost + output_cost

    def _save_token_report(self, report: TokenReport) -> None:
        if self.token_report_store is not None:
            self.token_report_store.append(report)

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _summary_tokens_in_request(self, messages: list[Message]) -> int:
        for message in messages:
            if self._is_summary_message(message):
                return self.token_counter.count_message(message)
        return 0

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

    @staticmethod
    def _overflow_message(report: TokenReport) -> str:
        return (
            "Контекст превышает лимит модели: "
            f"projected={report.projected_total_tokens_estimated:,} tokens, "
            f"limit={report.context_window_tokens:,} tokens. "
            "Запрос не отправлен. Используйте /context-mode sliding_window, "
            "очистите историю через /reset или уменьшите входной текст."
        ).replace(",", " ")

    def _to_agent_response(
        self,
        result: ChatResult,
        strategy: AgentStrategy,
        token_report: TokenReport,
    ) -> AgentResponse:
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
            token_report=token_report,
            has_reasoning_content=result.has_reasoning_content,
        )


__all__ = [
    "AgentResponse",
    "ContextOverflowError",
    "ContextStorageError",
    "JsonContextStore",
    "SimpleAgent",
]
