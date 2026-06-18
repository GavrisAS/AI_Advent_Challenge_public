"""CLI interface for the current AI Advent Challenge training agent."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from ai_advent_agent.agent import ContextOverflowError, SimpleAgent
from ai_advent_agent.commands import (
    CommandCompleter,
    CommandContext,
    CommandRegistry,
    CommandRouter,
    build_command_key_bindings,
    build_command_registry,
    format_number,
    print_metadata,
    print_token_report,
)
from ai_advent_agent.config import (
    DEFAULT_API_URL,
    DEFAULT_BRANCHES_FILE,
    DEFAULT_CONTEXT_FILE,
    DEFAULT_CONTEXT_WINDOW_TOKENS,
    DEFAULT_FACTS_FILE,
    DEFAULT_LONG_TERM_MEMORY_FILE,
    DEFAULT_MEMORY_EVENTS_FILE,
    DEFAULT_MODEL,
    DEFAULT_PROFILE_EVENTS_FILE,
    DEFAULT_RECENT_MESSAGES_LIMIT,
    DEFAULT_SHORT_TERM_MEMORY_FILE,
    DEFAULT_SUMMARIZE_EVERY_MESSAGES,
    DEFAULT_SUMMARY_FILE,
    DEFAULT_SUMMARY_MAX_TOKENS,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TASK_EVENTS_FILE,
    DEFAULT_TASK_STATE_FILE,
    DEFAULT_TOKEN_REPORT_FILE,
    DEFAULT_USER_PROFILES_FILE,
    DEFAULT_WARN_CONTEXT_RATIO,
    DEFAULT_WORKING_MEMORY_FILE,
    AgentConfig,
    ContextOverflowPolicy,
    parse_overflow_policy,
)
from ai_advent_agent.context_management import JsonBranchesStore, JsonFactsStore
from ai_advent_agent.env import load_env_file
from ai_advent_agent.llm_client import DeepSeekError, LLMClient
from ai_advent_agent.memory_layers import (
    JsonKeyValueMemoryStore,
    JsonShortTermMemoryStore,
    MemoryEventStore,
)
from ai_advent_agent.storage import ContextStorageError, JsonContextStore, JsonSummaryStore
from ai_advent_agent.task_state import JsonTaskStateStore, TaskEventStore
from ai_advent_agent.token_report import TokenReportStore
from ai_advent_agent.user_profile import JsonUserProfileStore, UserProfileEventStore


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    context_file_default = os.getenv("AI_ADVENT_CONTEXT_FILE") or str(DEFAULT_CONTEXT_FILE)
    token_report_file_default = os.getenv("AI_ADVENT_TOKEN_REPORT_FILE") or str(
        DEFAULT_TOKEN_REPORT_FILE
    )
    summary_file_default = os.getenv("AI_ADVENT_SUMMARY_FILE") or str(DEFAULT_SUMMARY_FILE)
    facts_file_default = os.getenv("AI_ADVENT_FACTS_FILE") or str(DEFAULT_FACTS_FILE)
    branches_file_default = os.getenv("AI_ADVENT_BRANCHES_FILE") or str(DEFAULT_BRANCHES_FILE)
    short_term_memory_file_default = os.getenv("AI_ADVENT_SHORT_TERM_MEMORY_FILE") or str(
        DEFAULT_SHORT_TERM_MEMORY_FILE
    )
    working_memory_file_default = os.getenv("AI_ADVENT_WORKING_MEMORY_FILE") or str(
        DEFAULT_WORKING_MEMORY_FILE
    )
    long_term_memory_file_default = os.getenv("AI_ADVENT_LONG_TERM_MEMORY_FILE") or str(
        DEFAULT_LONG_TERM_MEMORY_FILE
    )
    memory_events_file_default = os.getenv("AI_ADVENT_MEMORY_EVENTS_FILE") or str(
        DEFAULT_MEMORY_EVENTS_FILE
    )
    user_profiles_file_default = os.getenv("AI_ADVENT_USER_PROFILES_FILE") or str(
        DEFAULT_USER_PROFILES_FILE
    )
    profile_events_file_default = os.getenv("AI_ADVENT_PROFILE_EVENTS_FILE") or str(
        DEFAULT_PROFILE_EVENTS_FILE
    )
    task_state_file_default = os.getenv("AI_ADVENT_TASK_STATE_FILE") or str(DEFAULT_TASK_STATE_FILE)
    task_events_file_default = os.getenv("AI_ADVENT_TASK_EVENTS_FILE") or str(
        DEFAULT_TASK_EVENTS_FILE
    )

    parser = argparse.ArgumentParser(
        description="Актуальный учебный LLM-агент AI Advent Challenge."
    )
    parser.add_argument("--model", default=os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL))
    parser.add_argument("--api-url", default=os.getenv("DEEPSEEK_API_URL", DEFAULT_API_URL))
    parser.add_argument("--temperature", type=float, default=_env_float("AGENT_TEMPERATURE", 0.7))
    parser.add_argument("--max-tokens", type=int, default=_env_int("AGENT_MAX_TOKENS", 1000))
    parser.add_argument(
        "--strategy",
        choices=["direct", "step_by_step"],
        default=os.getenv("AGENT_STRATEGY", "direct"),
    )
    parser.add_argument(
        "--thinking",
        choices=["disabled", "enabled"],
        default=os.getenv("AGENT_THINKING", "disabled"),
    )
    parser.add_argument("--reasoning-effort", default=os.getenv("AGENT_REASONING_EFFORT") or None)
    parser.add_argument("--timeout", type=int, default=_env_int("AGENT_TIMEOUT_SECONDS", 120))
    parser.add_argument(
        "--context-file",
        type=Path,
        default=Path(context_file_default),
        help="JSON-файл для сохранения messages. По умолчанию .agent_context/messages.json.",
    )
    parser.add_argument(
        "--token-report-file",
        type=Path,
        default=Path(token_report_file_default),
        help="JSONL-файл для token reports. По умолчанию .agent_context/token_reports.jsonl.",
    )
    parser.add_argument(
        "--summary-file",
        type=Path,
        default=Path(summary_file_default),
        help="JSON-файл для summary memory. По умолчанию .agent_context/summary.json.",
    )
    parser.add_argument(
        "--facts-file",
        type=Path,
        default=Path(facts_file_default),
        help="JSON-файл для sticky facts. По умолчанию .agent_context/facts.json.",
    )
    parser.add_argument(
        "--branches-file",
        type=Path,
        default=Path(branches_file_default),
        help="JSON-файл для checkpoints и branches. По умолчанию .agent_context/branches.json.",
    )
    parser.add_argument(
        "--short-term-memory-file",
        type=Path,
        default=Path(short_term_memory_file_default),
        help="JSON-файл short-term memory. По умолчанию .agent_context/short_term_memory.json.",
    )
    parser.add_argument(
        "--working-memory-file",
        type=Path,
        default=Path(working_memory_file_default),
        help="JSON-файл working memory. По умолчанию .agent_context/working_memory.json.",
    )
    parser.add_argument(
        "--long-term-memory-file",
        type=Path,
        default=Path(long_term_memory_file_default),
        help="JSON-файл long-term memory. По умолчанию .agent_context/long_term_memory.json.",
    )
    parser.add_argument(
        "--memory-events-file",
        type=Path,
        default=Path(memory_events_file_default),
        help="JSONL-файл memory events. По умолчанию .agent_context/memory_events.jsonl.",
    )
    parser.add_argument(
        "--user-profiles-file",
        type=Path,
        default=Path(user_profiles_file_default),
        help="JSON-файл user profiles. По умолчанию .agent_context/user_profiles.json.",
    )
    parser.add_argument(
        "--profile-events-file",
        type=Path,
        default=Path(profile_events_file_default),
        help="JSONL-файл profile events. По умолчанию .agent_context/profile_events.jsonl.",
    )
    parser.add_argument(
        "--task-state-file",
        type=Path,
        default=Path(task_state_file_default),
        help="JSON-файл task state. По умолчанию .agent_context/task_state.json.",
    )
    parser.add_argument(
        "--task-events-file",
        type=Path,
        default=Path(task_events_file_default),
        help="JSONL-файл task events. По умолчанию .agent_context/task_events.jsonl.",
    )
    parser.add_argument(
        "--context-window-tokens",
        type=int,
        default=_env_int("CONTEXT_WINDOW_TOKENS", DEFAULT_CONTEXT_WINDOW_TOKENS),
        help="Лимит контекстного окна модели. По умолчанию 1_000_000.",
    )
    parser.add_argument(
        "--warn-context-ratio",
        type=float,
        default=_env_float("WARN_CONTEXT_RATIO", DEFAULT_WARN_CONTEXT_RATIO),
        help="Порог warning по projected context usage. По умолчанию 0.80.",
    )
    parser.add_argument(
        "--overflow-policy",
        choices=[item.value for item in ContextOverflowPolicy],
        default=os.getenv("CONTEXT_OVERFLOW_POLICY", ContextOverflowPolicy.ERROR.value),
        help="Что делать при превышении контекстного окна: error, no_trim, sliding_window.",
    )
    parser.add_argument(
        "--summary-mode",
        choices=["off", "llm"],
        default=os.getenv("SUMMARY_MODE", "off"),
        help="Режим summary memory: off или llm. По умолчанию off.",
    )
    parser.add_argument(
        "--context-strategy",
        choices=["sliding_window", "sticky_facts", "branching"],
        default=os.getenv("CONTEXT_STRATEGY", "sliding_window"),
        help="Day 10 context strategy: sliding_window, sticky_facts или branching.",
    )
    parser.add_argument(
        "--recent-messages-limit",
        type=int,
        default=_env_int("RECENT_MESSAGES_LIMIT", DEFAULT_RECENT_MESSAGES_LIMIT),
        help="Сколько последних сообщений оставлять без сжатия.",
    )
    parser.add_argument(
        "--summarize-every-messages",
        type=int,
        default=_env_int("SUMMARIZE_EVERY_MESSAGES", DEFAULT_SUMMARIZE_EVERY_MESSAGES),
        help="Минимум старых сообщений для очередного summary-сжатия.",
    )
    parser.add_argument(
        "--summary-max-tokens",
        type=int,
        default=_env_int("SUMMARY_MAX_TOKENS", DEFAULT_SUMMARY_MAX_TOKENS),
        help="max_tokens для отдельного LLM-вызова summary.",
    )
    parser.add_argument(
        "--input-price-per-1m-tokens",
        type=float,
        default=_env_float("INPUT_PRICE_PER_1M_TOKENS", 0.0),
        help="Цена input tokens за 1M токенов. По умолчанию 0, чтобы не хардкодить тарифы.",
    )
    parser.add_argument(
        "--output-price-per-1m-tokens",
        type=float,
        default=_env_float("OUTPUT_PRICE_PER_1M_TOKENS", 0.0),
        help="Цена output tokens за 1M токенов. По умолчанию 0, чтобы не хардкодить тарифы.",
    )
    parser.add_argument(
        "--no-load-context",
        action="store_true",
        help="Не загружать историю из JSON при старте, начать новую сессию.",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Отключить сохранение контекста в JSON для текущего запуска.",
    )
    parser.add_argument(
        "--no-token-report-log",
        action="store_true",
        help="Не сохранять token reports в JSONL.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Путь к .env. По умолчанию ищется .env в корне проекта.",
    )
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Не выводить metadata после ответа.",
    )
    parser.add_argument(
        "--plain-input",
        action="store_true",
        help="Использовать обычный input без slash-command autocomplete menu.",
    )
    return parser.parse_args(argv)


def require_api_key() -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print(
            "Ошибка: не найдена переменная окружения DEEPSEEK_API_KEY.\n"
            "Скопируйте .env.example в .env и добавьте ключ "
            "или экспортируйте переменную в терминале.",
            file=sys.stderr,
        )
        sys.exit(1)
    return api_key


def handle_command(command: str, agent: SimpleAgent, show_metadata: bool = True) -> bool:
    registry = build_command_registry()
    context = CommandContext(agent=agent, show_metadata=show_metadata)
    result = CommandRouter(registry).route(
        command,
        context,
    )
    if result.exit_requested:
        print("Выход.")
    return result.handled


def build_agent(args: argparse.Namespace) -> SimpleAgent:
    api_key = require_api_key()

    config = AgentConfig(
        model=args.model,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        strategy=args.strategy,
        thinking_type=args.thinking,
        reasoning_effort=args.reasoning_effort,
        context_window_tokens=args.context_window_tokens,
        warn_context_ratio=args.warn_context_ratio,
        overflow_policy=parse_overflow_policy(args.overflow_policy),
        input_price_per_1m_tokens=args.input_price_per_1m_tokens,
        output_price_per_1m_tokens=args.output_price_per_1m_tokens,
        summary_mode=args.summary_mode,
        recent_messages_limit=args.recent_messages_limit,
        summarize_every_messages=args.summarize_every_messages,
        summary_max_tokens=args.summary_max_tokens,
        context_strategy=args.context_strategy,
    )
    client = LLMClient(
        api_key=api_key,
        api_url=args.api_url,
        timeout_seconds=args.timeout,
    )
    context_store = None if args.no_persist else JsonContextStore(args.context_file)
    summary_store = None if args.no_persist else JsonSummaryStore(args.summary_file)
    facts_store = None if args.no_persist else JsonFactsStore(args.facts_file)
    branches_store = None if args.no_persist else JsonBranchesStore(args.branches_file)
    short_term_memory_store = (
        None if args.no_persist else JsonShortTermMemoryStore(args.short_term_memory_file)
    )
    working_memory_store = (
        None
        if args.no_persist
        else JsonKeyValueMemoryStore(args.working_memory_file, layer="working")
    )
    long_term_memory_store = (
        None
        if args.no_persist
        else JsonKeyValueMemoryStore(args.long_term_memory_file, layer="long_term")
    )
    memory_event_store = None if args.no_persist else MemoryEventStore(args.memory_events_file)
    user_profile_store = None if args.no_persist else JsonUserProfileStore(args.user_profiles_file)
    profile_event_store = (
        None if args.no_persist else UserProfileEventStore(args.profile_events_file)
    )
    task_state_store = None if args.no_persist else JsonTaskStateStore(args.task_state_file)
    task_event_store = None if args.no_persist else TaskEventStore(args.task_events_file)
    token_report_store = (
        None if args.no_token_report_log else TokenReportStore(args.token_report_file)
    )
    return SimpleAgent(
        client=client,
        config=config,
        context_store=context_store,
        summary_store=summary_store,
        facts_store=facts_store,
        branches_store=branches_store,
        short_term_memory_store=short_term_memory_store,
        working_memory_store=working_memory_store,
        long_term_memory_store=long_term_memory_store,
        memory_event_store=memory_event_store,
        user_profile_store=user_profile_store,
        profile_event_store=profile_event_store,
        task_state_store=task_state_store,
        task_event_store=task_event_store,
        token_report_store=token_report_store,
        load_context=not args.no_load_context,
    )


def read_user_input(
    registry: CommandRegistry,
    *,
    plain_input: bool = False,
    context: CommandContext | None = None,
) -> str:
    if plain_input:
        return input("Вы: ")
    try:
        from prompt_toolkit import prompt
        from prompt_toolkit.shortcuts import CompleteStyle
    except ImportError:
        return input("Вы: ")
    return prompt(
        "Вы: ",
        completer=CommandCompleter(registry, context),
        complete_style=CompleteStyle.COLUMN,
        complete_while_typing=True,
        key_bindings=build_command_key_bindings(registry),
    )


def main(argv: list[str] | None = None) -> None:
    # Load default .env first, then optionally explicit .env. Existing variables win.
    load_env_file()
    args = parse_args(argv)
    if args.env_file:
        load_env_file(args.env_file)

    try:
        agent = build_agent(args)
    except (ValueError, ContextStorageError) as error:
        print(f"Ошибка конфигурации: {error}", file=sys.stderr)
        sys.exit(1)

    show_metadata = not args.no_metadata
    history = agent.get_history()
    command_registry = build_command_registry()
    command_router = CommandRouter(command_registry)
    command_context = CommandContext(agent=agent, show_metadata=show_metadata)

    print("Day 13. Агент с task state machine")
    print(f"Модель: {agent.config.model}")
    print(f"Стратегия: {agent.config.strategy}")
    print(f"Context window: {format_number(agent.config.context_window_tokens)} tokens")
    print(f"Overflow policy: {agent.config.overflow_policy.value}")
    print(f"Context strategy: {agent.config.context_strategy}")
    print(f"Summary mode: {agent.config.summary_mode}")
    print(f"Файл контекста: {agent.context_path or 'сохранение отключено'}")
    print(f"Файл facts: {agent.facts_path or 'сохранение отключено'}")
    print(f"Файл branches: {agent.branches_path or 'сохранение отключено'}")
    print(f"Файл summary: {agent.summary_path or 'сохранение отключено'}")
    print(f"Файл short-term memory: {agent.short_term_memory_path or 'сохранение отключено'}")
    print(f"Файл working memory: {agent.working_memory_path or 'сохранение отключено'}")
    print(f"Файл long-term memory: {agent.long_term_memory_path or 'сохранение отключено'}")
    print(f"Файл memory events: {agent.memory_events_path or 'логирование отключено'}")
    print(f"Файл user profiles: {agent.user_profiles_path or 'сохранение отключено'}")
    print(f"Файл profile events: {agent.profile_events_path or 'логирование отключено'}")
    print(f"Файл task state: {agent.task_state_path or 'сохранение отключено'}")
    print(f"Файл task events: {agent.task_events_path or 'логирование отключено'}")
    print(f"Файл token reports: {agent.token_report_path or 'логирование отключено'}")
    print(f"Загружено сообщений: {len(history)}")
    print("Введите / для меню команд или /help для справки.\n")

    while True:
        try:
            user_text = read_user_input(
                command_registry,
                plain_input=args.plain_input,
                context=command_context,
            ).strip()
        except (EOFError, KeyboardInterrupt) as _error:
            print("\nВыход.")
            break

        if not user_text:
            continue

        command_result = command_router.route(
            user_text,
            command_context,
        )
        if command_result.exit_requested:
            print("Выход.")
            break
        if command_result.handled:
            continue

        try:
            response = agent.ask(user_text)
        except ContextOverflowError as error:
            print(f"\nОшибка: {error}\n", file=sys.stderr)
            print_token_report(error.report)
            print()
            continue
        except (DeepSeekError, ValueError, ContextStorageError) as error:
            print(f"\nОшибка: {error}\n", file=sys.stderr)
            continue

        print(f"\nAgent:\n{response.content.strip()}")
        if show_metadata:
            print_metadata(response)
        print()


if __name__ == "__main__":
    main()
