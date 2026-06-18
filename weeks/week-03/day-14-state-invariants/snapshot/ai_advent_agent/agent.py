"""Stateful minimal LLM agent with persistent context and token tracking."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any

from ai_advent_agent.config import AgentConfig, AgentStrategy, ContextOverflowPolicy, SummaryMode
from ai_advent_agent.context_management import (
    FACT_KEYS,
    BranchMemory,
    BranchSnapshot,
    JsonBranchesStore,
    JsonFactsStore,
    StickyFacts,
)
from ai_advent_agent.invariants import (
    Invariant,
    InvariantConflict,
    InvariantEventStore,
    InvariantSet,
    JsonInvariantStore,
    build_invariant_refusal,
    build_invariants_prompt_message,
)
from ai_advent_agent.llm_client import ChatClient, ChatResult, DeepSeekError, Message
from ai_advent_agent.memory_layers import (
    JsonKeyValueMemoryStore,
    JsonShortTermMemoryStore,
    KeyValueMemory,
    MemoryEventStore,
    MemoryPromptMetadata,
    ShortTermMemory,
    build_memory_prompt_messages,
    normalize_memory_key,
)
from ai_advent_agent.storage import (
    ContextStorageError,
    JsonContextStore,
    JsonSummaryStore,
    SummaryMemory,
)
from ai_advent_agent.task_state import (
    NEXT_TASK_STAGE,
    JsonTaskStateStore,
    TaskEventStore,
    TaskState,
    build_task_state_prompt_message,
    now_utc,
    validate_task_stage,
)
from ai_advent_agent.token_counter import ApproxTokenCounter, TokenBreakdown
from ai_advent_agent.token_report import TokenReport, TokenReportStore
from ai_advent_agent.user_profile import (
    JsonUserProfileStore,
    UserProfileEventStore,
    UserProfiles,
    build_profile_prompt_message,
)

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

FACTS_EXTRACTION_SYSTEM_PROMPT = (
    "Ты модуль извлечения sticky facts внутри AI-агента. "
    "Извлекай только устойчивые важные факты из нового сообщения пользователя. "
    "Верни строго JSON-объект с ключами: goal, constraints, preferences, decisions, "
    "agreements, user_data. Значение ключа — краткая строка на русском языке или пустая строка. "
    "Не добавляй факты, которых нет в сообщении."
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
        facts_store: JsonFactsStore | None = None,
        branches_store: JsonBranchesStore | None = None,
        short_term_memory_store: JsonShortTermMemoryStore | None = None,
        working_memory_store: JsonKeyValueMemoryStore | None = None,
        long_term_memory_store: JsonKeyValueMemoryStore | None = None,
        memory_event_store: MemoryEventStore | None = None,
        user_profile_store: JsonUserProfileStore | None = None,
        profile_event_store: UserProfileEventStore | None = None,
        invariant_store: JsonInvariantStore | None = None,
        invariant_event_store: InvariantEventStore | None = None,
        task_state_store: JsonTaskStateStore | None = None,
        task_event_store: TaskEventStore | None = None,
        token_report_store: TokenReportStore | None = None,
        token_counter: ApproxTokenCounter | None = None,
        load_context: bool = True,
    ) -> None:
        self.client = client
        self.config = config
        self.config.validate()
        self.context_store = context_store
        self.summary_store = summary_store
        self.facts_store = facts_store
        self.branches_store = branches_store
        self.short_term_memory_store = short_term_memory_store
        self.working_memory_store = working_memory_store
        self.long_term_memory_store = long_term_memory_store
        self.memory_event_store = memory_event_store
        self.user_profile_store = user_profile_store
        self.profile_event_store = profile_event_store
        self.invariant_store = invariant_store
        self.invariant_event_store = invariant_event_store
        self.task_state_store = task_state_store
        self.task_event_store = task_event_store
        self.token_report_store = token_report_store
        self.token_counter = token_counter or ApproxTokenCounter()
        self.last_token_report: TokenReport | None = None
        self.summary_memory = SummaryMemory()
        self.facts_memory = StickyFacts({key: "" for key in FACT_KEYS})
        self.branch_memory = BranchMemory()
        self.short_term_memory = ShortTermMemory()
        self.working_memory = KeyValueMemory()
        self.long_term_memory = KeyValueMemory()
        self.user_profiles = UserProfiles()
        self.invariants = InvariantSet()
        self.task_state = TaskState()
        self.messages: list[Message] = []

        if self.context_store is not None and load_context:
            self.messages = self._load_or_init_context()
        else:
            self.reset(save=False, clear_reports=False)
        if self.summary_store is not None and load_context:
            self.summary_memory = self.summary_store.load()
        if self.facts_store is not None and load_context:
            self.facts_memory = self.facts_store.load()
        if self.branches_store is not None and load_context:
            self.branch_memory = self.branches_store.load()
            if self.branch_memory.active_branch in self.branch_memory.branches:
                active = self.branch_memory.branches[self.branch_memory.active_branch]
                self.messages = [message.copy() for message in active.messages]
                self.facts_memory.values = dict(active.facts)
            else:
                self._save_active_branch()
        if self.short_term_memory_store is not None and load_context:
            self.short_term_memory = self.short_term_memory_store.load()
        if self.working_memory_store is not None and load_context:
            self.working_memory = self.working_memory_store.load()
        if self.long_term_memory_store is not None and load_context:
            self.long_term_memory = self.long_term_memory_store.load()
        if self.user_profile_store is not None and load_context:
            self.user_profiles = self.user_profile_store.load()
        if self.invariant_store is not None and load_context:
            self.invariants = self.invariant_store.load()
        if self.task_state_store is not None and load_context:
            self.task_state = self.task_state_store.load()

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

    @property
    def facts_path(self) -> str | None:
        if self.facts_store is None:
            return None
        return str(self.facts_store.path)

    @property
    def branches_path(self) -> str | None:
        if self.branches_store is None:
            return None
        return str(self.branches_store.path)

    @property
    def short_term_memory_path(self) -> str | None:
        if self.short_term_memory_store is None:
            return None
        return str(self.short_term_memory_store.path)

    @property
    def working_memory_path(self) -> str | None:
        if self.working_memory_store is None:
            return None
        return str(self.working_memory_store.path)

    @property
    def long_term_memory_path(self) -> str | None:
        if self.long_term_memory_store is None:
            return None
        return str(self.long_term_memory_store.path)

    @property
    def memory_events_path(self) -> str | None:
        if self.memory_event_store is None:
            return None
        return str(self.memory_event_store.path)

    @property
    def user_profiles_path(self) -> str | None:
        if self.user_profile_store is None:
            return None
        return str(self.user_profile_store.path)

    @property
    def profile_events_path(self) -> str | None:
        if self.profile_event_store is None:
            return None
        return str(self.profile_event_store.path)

    @property
    def invariants_path(self) -> str | None:
        if self.invariant_store is None:
            return None
        return str(self.invariant_store.path)

    @property
    def invariant_events_path(self) -> str | None:
        if self.invariant_event_store is None:
            return None
        return str(self.invariant_event_store.path)

    @property
    def task_state_path(self) -> str | None:
        if self.task_state_store is None:
            return None
        return str(self.task_state_store.path)

    @property
    def task_events_path(self) -> str | None:
        if self.task_event_store is None:
            return None
        return str(self.task_event_store.path)

    def ask(self, user_input: str, *, strategy: AgentStrategy | None = None) -> AgentResponse:
        """Send a user request to the LLM, save answer and update token report."""

        cleaned_input = user_input.strip()
        if not cleaned_input:
            raise ValueError("user_input не должен быть пустым")

        active_strategy = strategy or self.config.strategy
        if active_strategy not in {"direct", "step_by_step"}:
            raise ValueError("strategy должен быть direct или step_by_step")

        conflicts = self.check_invariant_conflicts(cleaned_input)
        if conflicts:
            return self._build_invariant_conflict_response(
                cleaned_input,
                active_strategy,
                conflicts,
            )

        user_message = self._build_user_message(cleaned_input, active_strategy)
        original_messages = self.get_history()
        original_summary = SummaryMemory(
            summary=self.summary_memory.summary,
            summarized_message_count=self.summary_memory.summarized_message_count,
            updated_at=self.summary_memory.updated_at,
        )
        original_facts = StickyFacts(
            values=dict(self.facts_memory.values),
            updated_at=self.facts_memory.updated_at,
        )

        try:
            self._update_facts_from_user_message(cleaned_input)
            preparation = self._prepare_messages_for_request(user_message)
            result = self.client.chat(preparation.request_messages, self.config)
        except (ContextOverflowError, DeepSeekError) as _error:
            self.messages = original_messages
            self.summary_memory = original_summary
            self.facts_memory = original_facts
            raise

        self.messages = preparation.persistent_messages
        self.messages.append(user_message.copy())
        self.messages.append({"role": "assistant", "content": result.content})
        self._refresh_short_term_recent_messages()
        self._complete_token_report(preparation.report, result)
        self.last_token_report = preparation.report
        self._save_token_report(preparation.report)
        self.save_context()
        self.save_summary()
        self.save_facts()
        self.save_short_term_memory()
        self._save_active_branch()
        return self._to_agent_response(result, active_strategy, preparation.report)

    def reset(self, *, save: bool = True, clear_reports: bool = True) -> None:
        """Clear session state and keep only the current system prompt."""

        self.messages = [{"role": "system", "content": self.config.system_prompt}]
        self.summary_memory = SummaryMemory()
        self.facts_memory.clear()
        self.short_term_memory.clear()
        self.task_state = TaskState()
        self.last_token_report = None
        if clear_reports and self.token_report_store is not None:
            self.token_report_store.clear()
        if save:
            self.save_context()
            self.save_summary()
            self.save_facts()
            self.save_short_term_memory()
            self.save_task_state()
            self._save_active_branch()

    def clear_context_file(self) -> None:
        """Delete persisted context and reset in-memory state to system prompt."""

        self.messages = [{"role": "system", "content": self.config.system_prompt}]
        self.summary_memory = SummaryMemory()
        self.facts_memory.clear()
        self.short_term_memory.clear()
        self.task_state = TaskState()
        self.last_token_report = None
        if self.context_store is not None:
            self.context_store.clear()
        if self.summary_store is not None:
            self.summary_store.clear()
        if self.facts_store is not None:
            self.facts_store.clear()
        if self.short_term_memory_store is not None:
            self.short_term_memory_store.clear()
        if self.task_state_store is not None:
            self.task_state_store.clear()
        if self.branches_store is not None:
            self.branches_store.clear()
            self.branch_memory = BranchMemory()
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

    def save_facts(self) -> None:
        """Persist current sticky facts if a facts store is configured."""

        if self.facts_store is not None:
            self.facts_store.save(self.facts_memory)

    def save_short_term_memory(self) -> None:
        """Persist short-term memory if a store is configured."""

        if self.short_term_memory_store is not None:
            self.short_term_memory_store.save(self.short_term_memory)

    def save_working_memory(self) -> None:
        """Persist working memory if a store is configured."""

        if self.working_memory_store is not None:
            self.working_memory_store.save(self.working_memory)

    def save_long_term_memory(self) -> None:
        """Persist long-term memory if a store is configured."""

        if self.long_term_memory_store is not None:
            self.long_term_memory_store.save(self.long_term_memory)

    def save_user_profiles(self) -> None:
        """Persist user profiles if a store is configured."""

        if self.user_profile_store is not None:
            self.user_profile_store.save(self.user_profiles)

    def save_task_state(self) -> None:
        """Persist task state if a store is configured."""

        if self.task_state_store is not None:
            self.task_state_store.save(self.task_state)

    def save_invariants(self) -> None:
        """Persist invariants if a store is configured."""

        if self.invariant_store is not None:
            self.invariant_store.save(self.invariants)

    def add_invariant(self, category: str, text: str) -> Invariant:
        """Create a new hard invariant."""

        invariant = self.invariants.add(category, text)
        self.save_invariants()
        self._append_invariant_event(action="add_invariant", invariant=invariant)
        return invariant

    def remove_invariant(self, invariant_id: str) -> Invariant:
        """Remove an invariant by id."""

        invariant = self.invariants.remove(invariant_id)
        self.save_invariants()
        self._append_invariant_event(action="remove_invariant", invariant=invariant)
        return invariant

    def enable_invariant(self, invariant_id: str) -> Invariant:
        """Enable an invariant."""

        invariant = self.invariants.set_enabled(invariant_id, True)
        self.save_invariants()
        self._append_invariant_event(action="enable_invariant", invariant=invariant)
        return invariant

    def disable_invariant(self, invariant_id: str) -> Invariant:
        """Disable an invariant."""

        invariant = self.invariants.set_enabled(invariant_id, False)
        self.save_invariants()
        self._append_invariant_event(action="disable_invariant", invariant=invariant)
        return invariant

    def set_invariant_rationale(self, invariant_id: str, text: str) -> Invariant:
        """Set rationale for an invariant."""

        invariant = self.invariants.set_rationale(invariant_id, text)
        self.save_invariants()
        self._append_invariant_event(
            action="set_rationale",
            invariant=invariant,
            value=invariant.rationale,
        )
        return invariant

    def add_invariant_pattern(self, invariant_id: str, pattern: str) -> Invariant:
        """Add a deterministic reject pattern to an invariant."""

        invariant = self.invariants.add_reject_pattern(invariant_id, pattern)
        self.save_invariants()
        self._append_invariant_event(
            action="add_reject_pattern",
            invariant=invariant,
            value=pattern.strip(),
        )
        return invariant

    def remove_invariant_pattern(self, invariant_id: str, pattern: str) -> bool:
        """Remove a deterministic reject pattern from an invariant."""

        invariant = self.invariants.require(invariant_id)
        removed = self.invariants.remove_reject_pattern(invariant_id, pattern)
        self.save_invariants()
        self._append_invariant_event(
            action="remove_reject_pattern",
            invariant=invariant,
            value=pattern.strip(),
        )
        return removed

    def reset_invariants(self) -> None:
        """Clear all invariants while preserving the event log."""

        self.invariants.reset()
        self.save_invariants()
        self._append_invariant_event(action="reset_invariants")

    def check_invariant_conflicts(self, text: str) -> list[InvariantConflict]:
        """Return deterministic conflicts for active invariants."""

        conflicts = self.invariants.check_conflicts(text)
        self._append_invariant_event(action="check_conflict", conflicts=conflicts)
        return conflicts

    def start_task(self, title: str) -> None:
        """Start a new task at the canonical planning stage."""

        checked_title = title.strip()
        if not checked_title:
            raise ValueError("Название задачи не должно быть пустым")
        self.task_state = TaskState(stage="planning", title=checked_title, updated_at=now_utc())
        self.save_task_state()
        self._append_task_event(action="start_task")

    def set_task_stage(self, stage: str) -> None:
        """Explicitly set task stage."""

        self._require_active_task()
        checked_stage = validate_task_stage(stage)
        self.task_state.stage = checked_stage
        self.task_state.done = checked_stage == "done"
        if self.task_state.done:
            self.task_state.paused = False
        self.task_state.updated_at = now_utc()
        self.save_task_state()
        self._append_task_event(action="set_stage")

    def set_task_step(self, text: str) -> None:
        """Set current task step."""

        self._require_active_task()
        checked = text.strip()
        if not checked:
            raise ValueError("Текущий шаг не должен быть пустым")
        self.task_state.current_step = checked
        self.task_state.updated_at = now_utc()
        self.save_task_state()
        self._append_task_event(action="set_step")

    def set_task_expected_action(self, text: str) -> None:
        """Set expected next action."""

        self._require_active_task()
        checked = text.strip()
        if not checked:
            raise ValueError("Ожидаемое действие не должно быть пустым")
        self.task_state.expected_action = checked
        self.task_state.updated_at = now_utc()
        self.save_task_state()
        self._append_task_event(action="set_expected_action")

    def advance_task(self) -> None:
        """Advance through planning -> execution -> validation -> done."""

        self._require_active_task()
        stage = self.task_state.stage
        if stage == "done":
            raise ValueError("Задача уже завершена")
        if stage not in NEXT_TASK_STAGE:
            raise ValueError("Для /task next задача должна быть на planning/execution/validation")
        self.set_task_stage(NEXT_TASK_STAGE[stage])

    def pause_task(self) -> None:
        """Pause active task without changing stage."""

        self._require_active_task()
        if self.task_state.done:
            raise ValueError("Завершённую задачу нельзя поставить на паузу")
        self.task_state.paused = True
        self.task_state.updated_at = now_utc()
        self.save_task_state()
        self._append_task_event(action="pause_task")

    def resume_task(self) -> None:
        """Resume active task without changing stage."""

        self._require_active_task()
        self.task_state.paused = False
        self.task_state.updated_at = now_utc()
        self.save_task_state()
        self._append_task_event(action="resume_task")

    def complete_task(self) -> None:
        """Complete active task."""

        self._require_active_task()
        self.task_state.stage = "done"
        self.task_state.done = True
        self.task_state.paused = False
        self.task_state.updated_at = now_utc()
        self.save_task_state()
        self._append_task_event(action="complete_task")

    def reset_task(self) -> None:
        """Clear current task state while keeping the event log."""

        self.task_state = TaskState(updated_at=now_utc())
        self.save_task_state()
        self._append_task_event(action="reset_task")

    def set_task_metadata(self, key: str, value: str) -> None:
        """Set a task metadata key-value entry."""

        self._require_active_task()
        checked_key = key.strip()
        checked_value = value.strip()
        if not checked_key:
            raise ValueError("metadata key не должен быть пустым")
        if not checked_value:
            raise ValueError("metadata value не должен быть пустым")
        self.task_state.metadata[checked_key] = checked_value
        self.task_state.updated_at = now_utc()
        self.save_task_state()
        self._append_task_event(action="set_metadata", key=checked_key, value=checked_value)

    def create_profile(self, name: str) -> None:
        """Create a named personalization profile and make it active."""

        profile = self.user_profiles.create(name)
        self.save_user_profiles()
        self._append_profile_event(action="create_profile", profile=profile.name)

    def use_profile(self, name: str) -> None:
        """Switch active personalization profile."""

        profile = self.user_profiles.use(name)
        self.save_user_profiles()
        self._append_profile_event(action="use_profile", profile=profile.name)

    def set_profile_field(self, field_name: str, value: str) -> None:
        """Set a scalar field on the active personalization profile."""

        profile = self.user_profiles.require_active()
        profile.set_field(field_name, value)
        self.save_user_profiles()
        self._append_profile_event(
            action="set_profile_field",
            profile=profile.name,
            field=field_name,
            value=value.strip(),
        )

    def set_profile_preference(self, key: str, value: str) -> None:
        """Set a preference entry on the active personalization profile."""

        profile = self.user_profiles.require_active()
        profile.set_preference(key, value)
        self.save_user_profiles()
        self._append_profile_event(
            action="set_profile_preference",
            profile=profile.name,
            key=key.strip(),
            value=value.strip(),
        )

    def set_profile_constraint(self, key: str, value: str) -> None:
        """Set a constraint entry on the active personalization profile."""

        profile = self.user_profiles.require_active()
        profile.set_constraint(key, value)
        self.save_user_profiles()
        self._append_profile_event(
            action="set_profile_constraint",
            profile=profile.name,
            key=key.strip(),
            value=value.strip(),
        )

    def reset_active_profile(self) -> None:
        """Clear active profile fields while keeping the profile record active."""

        profile = self.user_profiles.reset_active()
        self.save_user_profiles()
        self._append_profile_event(action="reset_profile", profile=profile.name)

    def reset_all_profiles(self) -> None:
        """Clear every profile while preserving the append-only event log."""

        self.user_profiles.reset_all()
        self.save_user_profiles()
        self._append_profile_event(action="reset_all_profiles")

    def remember_short(self, text: str) -> None:
        """Explicitly save a note into short-term memory."""

        self.short_term_memory.add_note(text)
        self.save_short_term_memory()
        self._append_memory_event(action="remember", layer="short_term", text=text.strip())

    def remember_working(self, key: str, value: str) -> None:
        """Explicitly save a key-value entry into working memory."""

        checked_key = normalize_memory_key(key)
        self.working_memory.set(checked_key, value)
        self.save_working_memory()
        self._append_memory_event(
            action="remember",
            layer="working",
            key=checked_key,
            value=value.strip(),
        )

    def remember_long(self, key: str, value: str) -> None:
        """Explicitly save a key-value entry into long-term memory."""

        checked_key = normalize_memory_key(key)
        self.long_term_memory.set(checked_key, value)
        self.save_long_term_memory()
        self._append_memory_event(
            action="remember",
            layer="long_term",
            key=checked_key,
            value=value.strip(),
        )

    def forget_working(self, key: str) -> bool:
        """Remove a key from working memory."""

        checked_key = normalize_memory_key(key)
        removed = self.working_memory.forget(checked_key)
        self.save_working_memory()
        self._append_memory_event(action="forget", layer="working", key=checked_key)
        return removed

    def forget_long(self, key: str) -> bool:
        """Remove a key from long-term memory."""

        checked_key = normalize_memory_key(key)
        removed = self.long_term_memory.forget(checked_key)
        self.save_long_term_memory()
        self._append_memory_event(action="forget", layer="long_term", key=checked_key)
        return removed

    def reset_working_memory(self) -> None:
        """Clear only the working memory layer."""

        self.working_memory.clear()
        self.save_working_memory()
        self._append_memory_event(action="reset", layer="working")

    def reset_all_memory_layers(self) -> None:
        """Clear all explicit memory layers."""

        self.short_term_memory.clear()
        self.working_memory.clear()
        self.long_term_memory.clear()
        self.save_short_term_memory()
        self.save_working_memory()
        self.save_long_term_memory()
        self._append_memory_event(action="reset", layer="all")

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

    def create_checkpoint(self, name: str) -> None:
        """Create or replace a checkpoint from current messages and facts."""

        checked_name = self._validate_branch_name(name)
        snapshot = self._current_branch_snapshot(checked_name)
        self.branch_memory.checkpoints[checked_name] = snapshot
        self.branch_memory.latest_checkpoint = checked_name
        self._save_branches()

    def create_branch(self, name: str) -> None:
        """Create a branch from latest checkpoint or current state."""

        checked_name = self._validate_branch_name(name)
        if checked_name in self.branch_memory.branches:
            raise ValueError(f"Ветка уже существует: {checked_name}")
        self._save_active_branch()

        source = None
        latest = self.branch_memory.latest_checkpoint
        if latest:
            source = self.branch_memory.checkpoints.get(latest)

        if source is None:
            source = self._current_branch_snapshot(checked_name)

        self.branch_memory.branches[checked_name] = BranchSnapshot(
            name=checked_name,
            messages=[message.copy() for message in source.messages],
            facts=dict(source.facts),
        )
        self.branch_memory.active_branch = checked_name
        self.messages = [message.copy() for message in source.messages]
        self.facts_memory.values = dict(source.facts)
        self.save_context()
        self.save_facts()
        self._save_branches()

    def switch_branch(self, name: str) -> None:
        """Switch active branch and restore its state."""

        checked_name = self._validate_branch_name(name)
        if checked_name not in self.branch_memory.branches:
            raise ValueError(f"Ветка не найдена: {checked_name}")
        self._save_active_branch()
        snapshot = self.branch_memory.branches[checked_name]
        self.branch_memory.active_branch = checked_name
        self.messages = [message.copy() for message in snapshot.messages]
        self.facts_memory.values = dict(snapshot.facts)
        self.save_context()
        self.save_facts()
        self._save_branches()

    def _prepare_messages_for_request(
        self,
        user_message: Message,
        *,
        dry_run: bool = False,
        allow_error_report: bool = False,
    ) -> RequestPreparation:
        pre_strategy_messages = self._messages_after_optional_summary(dry_run=dry_run)
        persistent_messages = self._apply_persistent_context_strategy(pre_strategy_messages)
        strategy_trimmed_count = max(0, len(pre_strategy_messages) - len(persistent_messages))
        history_tokens_before = self.token_counter.count_messages(self.messages)
        request_tokens = self.token_counter.count_text(user_message["content"])
        (
            request_messages,
            memory_metadata,
            task_prompt_tokens,
            invariants_prompt_tokens,
            invariants_count,
        ) = self._build_request_messages(persistent_messages, user_message)
        prompt_tokens = self.token_counter.count_messages(request_messages)
        projected_total = prompt_tokens + self.config.max_tokens
        report = self._build_preflight_report(
            request_tokens=request_tokens,
            history_tokens_before=history_tokens_before,
            prompt_tokens=prompt_tokens,
            projected_total=projected_total,
            trimmed_messages_count=strategy_trimmed_count,
            overflow_detected=projected_total > self.config.context_window_tokens,
            request_messages=request_messages,
            memory_metadata=memory_metadata,
            task_prompt_tokens=task_prompt_tokens,
            invariants_prompt_tokens=invariants_prompt_tokens,
            invariants_count=invariants_count,
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
                memory_metadata=memory_metadata,
                task_prompt_tokens=task_prompt_tokens,
                invariants_prompt_tokens=invariants_prompt_tokens,
                invariants_count=invariants_count,
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
    ) -> tuple[list[Message], MemoryPromptMetadata, int, int, int]:
        request_messages = self._apply_request_context_strategy(persistent_messages)
        invariants_message, invariants_prompt_tokens, invariants_count = (
            build_invariants_prompt_message(self.invariants, self.token_counter)
        )
        if invariants_message is not None:
            insert_at = 1 if request_messages and request_messages[0]["role"] == "system" else 0
            request_messages.insert(insert_at, invariants_message)
        if self.config.summary_mode == "llm" and self.summary_memory.active:
            insert_at = 1 if request_messages and request_messages[0]["role"] == "system" else 0
            if invariants_message is not None:
                insert_at += 1
            request_messages.insert(insert_at, self._summary_message())
        profile_message, profile_fields_count, profile_tokens = build_profile_prompt_message(
            self.user_profiles,
            self.token_counter,
        )
        if profile_message is not None:
            insert_at = 1 if request_messages and request_messages[0]["role"] == "system" else 0
            if invariants_message is not None:
                insert_at += 1
            request_messages.insert(insert_at, profile_message)
        memory_messages, memory_metadata = self._build_memory_prompt_messages(persistent_messages)
        task_message, task_prompt_tokens = build_task_state_prompt_message(
            self.task_state,
            self.token_counter,
        )
        if memory_messages:
            insert_at = 1 if request_messages and request_messages[0]["role"] == "system" else 0
            if invariants_message is not None:
                insert_at += 1
            if profile_message is not None:
                insert_at += 1
            request_messages[insert_at:insert_at] = memory_messages
        if task_message is not None:
            insert_at = 1 if request_messages and request_messages[0]["role"] == "system" else 0
            if invariants_message is not None:
                insert_at += 1
            if profile_message is not None:
                insert_at += 1
            if memory_messages:
                insert_at += len(memory_messages)
                for index, message in enumerate(request_messages):
                    if self._is_working_memory_message(message):
                        insert_at = index + 1
                    if self._is_short_term_memory_message(message):
                        insert_at = index
                        break
            request_messages.insert(insert_at, task_message)
        request_messages.append(user_message.copy())
        memory_metadata.assembly_order = self._prompt_assembly_order(request_messages)
        if profile_message is not None:
            memory_metadata.profile_active = True
            memory_metadata.active_profile_name = self.user_profiles.active_profile
            memory_metadata.profile_fields_count = profile_fields_count
            memory_metadata.profile_prompt_tokens_estimated = profile_tokens
        return (
            request_messages,
            memory_metadata,
            task_prompt_tokens,
            invariants_prompt_tokens,
            invariants_count,
        )

    def _apply_persistent_context_strategy(self, messages: list[Message]) -> list[Message]:
        if self.config.context_strategy != "sliding_window":
            return [message.copy() for message in messages]
        return self._keep_recent_messages(messages, self.config.recent_messages_limit)

    def _apply_request_context_strategy(self, messages: list[Message]) -> list[Message]:
        if self.config.context_strategy == "sliding_window":
            return [message.copy() for message in messages]

        request_messages = self._keep_recent_messages(messages, self.config.recent_messages_limit)
        if (
            self.config.context_strategy in {"sticky_facts", "branching"}
            and self.facts_memory.active
        ):
            insert_at = 1 if request_messages and request_messages[0]["role"] == "system" else 0
            request_messages.insert(insert_at, self._facts_message())
        return request_messages

    def _build_memory_prompt_messages(
        self,
        persistent_messages: list[Message],
    ) -> tuple[list[Message], MemoryPromptMetadata]:
        if not self._memory_layers_enabled():
            return [], MemoryPromptMetadata()

        recent_messages = self._recent_dialog_messages(persistent_messages)
        short_term = ShortTermMemory(
            notes=self.short_term_memory.normalized_notes(),
            recent_messages=recent_messages,
            updated_at=self.short_term_memory.updated_at,
        )
        return build_memory_prompt_messages(
            short_term=short_term,
            working=self.working_memory,
            long_term=self.long_term_memory,
            token_counter=self.token_counter,
        )

    def _memory_layers_enabled(self) -> bool:
        return any(
            (
                self.short_term_memory_store is not None,
                self.working_memory_store is not None,
                self.long_term_memory_store is not None,
                self.short_term_memory.active,
                self.working_memory.active,
                self.long_term_memory.active,
            )
        )

    def _recent_dialog_messages(self, messages: list[Message]) -> list[Message]:
        conversation = [
            message.copy() for message in messages if message.get("role") in {"user", "assistant"}
        ]
        limit = self.config.recent_messages_limit
        return conversation[-limit:] if limit > 0 else []

    def _refresh_short_term_recent_messages(self) -> None:
        if not self._memory_layers_enabled():
            return
        self.short_term_memory.set_recent_messages(self._recent_dialog_messages(self.messages))

    def _non_memory_prompt_order(self, messages: list[Message]) -> list[str]:
        order: list[str] = []
        if messages and messages[0].get("role") == "system":
            order.append("system")
        if any(self._is_invariants_message(message) for message in messages):
            order.append("invariants")
        if any(self._is_profile_message(message) for message in messages):
            order.append("user_profile")
        if any(self._is_task_state_message(message) for message in messages):
            order.append("task_state")
        if any(self._is_summary_message(message) for message in messages):
            order.append("summary_memory")
        if any(self._is_facts_message(message) for message in messages):
            order.append("sticky_facts")
        if any(message.get("role") in {"user", "assistant"} for message in messages):
            order.append("conversation")
        return order

    def _prompt_assembly_order(self, messages: list[Message]) -> list[str]:
        order: list[str] = []
        if messages and messages[0].get("role") == "system":
            order.append("system")
        if any(self._is_invariants_message(message) for message in messages):
            order.append("invariants")
        if any(self._is_profile_message(message) for message in messages):
            order.append("user_profile")
        if any(self._is_summary_message(message) for message in messages):
            order.append("summary_memory")
        if any(self._is_facts_message(message) for message in messages):
            order.append("sticky_facts")
        if any(self._is_long_term_memory_message(message) for message in messages):
            order.append("long_term_memory")
        if any(self._is_working_memory_message(message) for message in messages):
            order.append("working_memory")
        if any(self._is_task_state_message(message) for message in messages):
            order.append("task_state")
        if any(self._is_short_term_memory_message(message) for message in messages):
            order.append("short_term_memory")
        if any(message.get("role") in {"user", "assistant"} for message in messages[:-1]):
            order.append("conversation")
        if messages and messages[-1].get("role") == "user":
            order.append("current_user")
        return order

    def _keep_recent_messages(self, messages: list[Message], limit: int) -> list[Message]:
        if not messages:
            return []
        system_message = self._system_message_from_history(messages)
        conversation = [message.copy() for message in messages[1:]]
        recent = conversation[-limit:] if limit > 0 else []
        return [system_message, *recent]

    def _facts_message(self) -> Message:
        facts = self.facts_memory.normalized()
        lines = [f"- {key}: {value}" for key, value in facts.items() if value.strip()]
        return {
            "role": "system",
            "content": "Sticky facts пользователя и проекта:\n" + "\n".join(lines),
        }

    @staticmethod
    def _is_facts_message(message: Message) -> bool:
        return message.get("role") == "system" and message.get("content", "").startswith(
            "Sticky facts"
        )

    def _update_facts_from_user_message(self, user_input: str) -> None:
        if self.config.context_strategy not in {"sticky_facts", "branching"}:
            return
        if self.facts_store is None and self.config.context_strategy == "sticky_facts":
            return

        prompt = self._build_facts_extraction_prompt(user_input)
        facts_config = replace(
            self.config,
            temperature=0,
            max_tokens=400,
            strategy="direct",
            thinking_type="disabled",
            summary_mode="off",
        )
        result = self.client.chat(
            [
                {"role": "system", "content": FACTS_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            facts_config,
        )
        self.facts_memory.merge(self._parse_facts_response(result.content))

    def _build_facts_extraction_prompt(self, user_input: str) -> str:
        return (
            "Текущие sticky facts:\n"
            f"{json.dumps(self.facts_memory.normalized(), ensure_ascii=False, indent=2)}\n\n"
            "Новое сообщение пользователя:\n"
            f"{user_input}\n\n"
            "Верни только JSON с обновлениями. Если ключ не изменился, верни пустую строку."
        )

    @staticmethod
    def _parse_facts_response(content: str) -> dict[str, str]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as error:
            raise DeepSeekError(
                f"LLM facts extraction вернул невалидный JSON: {content}"
            ) from error
        if not isinstance(payload, dict):
            raise DeepSeekError("LLM facts extraction должен вернуть JSON-объект")
        updates: dict[str, str] = {}
        for key in FACT_KEYS:
            value = payload.get(key, "")
            if value is None:
                value = ""
            if not isinstance(value, str):
                raise DeepSeekError(f"facts.{key} должен быть строкой")
            updates[key] = value
        return updates

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
        memory_metadata: MemoryPromptMetadata,
        task_prompt_tokens: int,
        invariants_prompt_tokens: int,
        invariants_count: int,
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
            memory_layers_active=memory_metadata.layers_active,
            memory_layer_entries=dict(memory_metadata.layer_entries),
            memory_layer_tokens_estimated=dict(memory_metadata.layer_tokens_estimated),
            memory_prompt_tokens_estimated=memory_metadata.prompt_tokens_estimated,
            profile_active=memory_metadata.profile_active,
            active_profile_name=memory_metadata.active_profile_name,
            profile_fields_count=memory_metadata.profile_fields_count,
            profile_prompt_tokens_estimated=memory_metadata.profile_prompt_tokens_estimated,
            invariants_active=invariants_count > 0,
            invariants_count=invariants_count,
            invariants_prompt_tokens_estimated=invariants_prompt_tokens,
            task_state_active=self.task_state.active,
            task_stage=self.task_state.stage or None,
            task_done=self.task_state.done,
            task_paused=self.task_state.paused,
            task_prompt_tokens_estimated=task_prompt_tokens,
            prompt_assembly_order=list(memory_metadata.assembly_order),
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

    def _build_invariant_conflict_response(
        self,
        user_input: str,
        strategy: AgentStrategy,
        conflicts: list[InvariantConflict],
    ) -> AgentResponse:
        refusal = build_invariant_refusal(conflicts)
        system_message = self._system_message_from_history(self.messages)
        invariants_message, invariants_prompt_tokens, invariants_count = (
            build_invariants_prompt_message(self.invariants, self.token_counter)
        )
        request_messages = [system_message]
        if invariants_message is not None:
            request_messages.append(invariants_message)
        request_messages.append(self._build_user_message(user_input, strategy))
        prompt_tokens = self.token_counter.count_messages(request_messages)
        projected_total = prompt_tokens
        context_ratio = prompt_tokens / self.config.context_window_tokens
        report = TokenReport(
            request_tokens_estimated=self.token_counter.count_text(user_input),
            history_tokens_before_estimated=self.token_counter.count_messages(self.messages),
            prompt_tokens_estimated=prompt_tokens,
            projected_total_tokens_estimated=projected_total,
            context_window_tokens=self.config.context_window_tokens,
            context_usage_ratio=context_ratio,
            projected_usage_ratio=context_ratio,
            warn_threshold_reached=context_ratio >= self.config.warn_context_ratio,
            overflow_detected=False,
            overflow_policy=self.config.overflow_policy.value,
            invariants_active=invariants_count > 0,
            invariants_count=invariants_count,
            invariants_prompt_tokens_estimated=invariants_prompt_tokens,
            invariant_conflict=True,
            invariant_conflict_count=len(conflicts),
            prompt_assembly_order=self._prompt_assembly_order(request_messages),
            response_tokens_estimated=self.token_counter.count_text(refusal),
            history_tokens_after_response_estimated=self.token_counter.count_messages(
                self.messages
            ),
            prompt_tokens_actual=0,
            completion_tokens_actual=0,
            total_tokens_actual=0,
            estimated_input_cost_usd=0.0,
            estimated_output_cost_usd=0.0,
            estimated_total_cost_usd=0.0,
            elapsed_seconds=0.0,
        )
        self.last_token_report = report
        self._save_token_report(report)
        result = ChatResult(
            content=refusal,
            finish_reason="invariant_conflict",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            elapsed_seconds=0.0,
            model=self.config.model,
            raw={"local_refusal": True, "api_calls": 0},
        )
        return self._to_agent_response(result, strategy, report)

    def _append_invariant_event(
        self,
        *,
        action: str,
        invariant: Invariant | None = None,
        conflicts: list[InvariantConflict] | None = None,
        value: str | None = None,
    ) -> None:
        if self.invariant_event_store is not None:
            self.invariant_event_store.append(
                action=action,
                invariant=invariant,
                conflicts=conflicts,
                value=value,
            )

    def _append_memory_event(
        self,
        *,
        action: str,
        layer: str,
        key: str | None = None,
        value: str | None = None,
        text: str | None = None,
    ) -> None:
        if self.memory_event_store is not None:
            self.memory_event_store.append(
                action=action,
                layer=layer,
                key=key,
                value=value,
                text=text,
            )

    def _append_profile_event(
        self,
        *,
        action: str,
        profile: str | None = None,
        field: str | None = None,
        key: str | None = None,
        value: str | None = None,
    ) -> None:
        if self.profile_event_store is not None:
            self.profile_event_store.append(
                action=action,
                profile=profile,
                field=field,
                key=key,
                value=value,
            )

    def _append_task_event(
        self,
        *,
        action: str,
        key: str | None = None,
        value: str | None = None,
    ) -> None:
        if self.task_event_store is not None:
            self.task_event_store.append(
                action=action,
                state=self.task_state,
                key=key,
                value=value,
            )

    def _require_active_task(self) -> None:
        if not self.task_state.active or not self.task_state.stage:
            raise ValueError("Сначала создайте задачу: /task start <title>")

    @staticmethod
    def _is_invariants_message(message: Message) -> bool:
        return message.get("role") == "system" and message.get("content", "").startswith(
            "State invariants:"
        )

    @staticmethod
    def _is_profile_message(message: Message) -> bool:
        return message.get("role") == "system" and message.get("content", "").startswith(
            "User profile preferences."
        )

    @staticmethod
    def _is_task_state_message(message: Message) -> bool:
        return message.get("role") == "system" and message.get("content", "").startswith(
            "Task state:"
        )

    @staticmethod
    def _is_long_term_memory_message(message: Message) -> bool:
        return message.get("role") == "system" and message.get("content", "").startswith(
            "Long-term memory:"
        )

    @staticmethod
    def _is_working_memory_message(message: Message) -> bool:
        return message.get("role") == "system" and message.get("content", "").startswith(
            "Working memory:"
        )

    @staticmethod
    def _is_short_term_memory_message(message: Message) -> bool:
        return message.get("role") == "system" and message.get("content", "").startswith(
            "Short-term memory:"
        )

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError) as _error:
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

    def _current_branch_snapshot(self, name: str | None = None) -> BranchSnapshot:
        return BranchSnapshot(
            name=name or self.branch_memory.active_branch,
            messages=self.get_history(),
            facts=self.facts_memory.normalized(),
        )

    def _save_active_branch(self) -> None:
        if self.branches_store is None:
            return
        active = self.branch_memory.active_branch or "main"
        self.branch_memory.active_branch = active
        self.branch_memory.branches[active] = self._current_branch_snapshot(active)
        self._save_branches()

    def _save_branches(self) -> None:
        if self.branches_store is not None:
            self.branches_store.save(self.branch_memory)

    @staticmethod
    def _validate_branch_name(name: str) -> str:
        checked = name.strip()
        if not checked:
            raise ValueError("Имя ветки/checkpoint не должно быть пустым")
        if any(char.isspace() for char in checked):
            raise ValueError("Имя ветки/checkpoint не должно содержать пробелы")
        return checked

    @staticmethod
    def _overflow_message(report: TokenReport) -> str:
        return (
            "Контекст превышает лимит модели: "
            f"projected={report.projected_total_tokens_estimated:,} tokens, "
            f"limit={report.context_window_tokens:,} tokens. "
            "Запрос не отправлен. Используйте /config overflow sliding_window, "
            "очистите сессию через /session reset или уменьшите входной текст."
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
    "InvariantEventStore",
    "JsonBranchesStore",
    "JsonContextStore",
    "JsonFactsStore",
    "JsonInvariantStore",
    "JsonKeyValueMemoryStore",
    "JsonShortTermMemoryStore",
    "JsonUserProfileStore",
    "MemoryEventStore",
    "SimpleAgent",
    "UserProfileEventStore",
]
