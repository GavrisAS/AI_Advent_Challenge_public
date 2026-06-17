"""CLI interface for the current AI Advent Challenge training agent."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from ai_advent_agent.agent import AgentResponse, ContextOverflowError, SimpleAgent
from ai_advent_agent.commands import (
    CommandCompleter,
    CommandContext,
    CommandRegistry,
    CommandRouter,
    build_command_registry,
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
    DEFAULT_RECENT_MESSAGES_LIMIT,
    DEFAULT_SHORT_TERM_MEMORY_FILE,
    DEFAULT_SUMMARIZE_EVERY_MESSAGES,
    DEFAULT_SUMMARY_FILE,
    DEFAULT_SUMMARY_MAX_TOKENS,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TOKEN_REPORT_FILE,
    DEFAULT_WARN_CONTEXT_RATIO,
    DEFAULT_WORKING_MEMORY_FILE,
    AgentConfig,
    ContextOverflowPolicy,
    parse_overflow_policy,
)
from ai_advent_agent.context_management import JsonBranchesStore, JsonFactsStore
from ai_advent_agent.env import load_env_file
from ai_advent_agent.llm_client import DeepSeekError, LLMClient, Message
from ai_advent_agent.memory_layers import (
    JsonKeyValueMemoryStore,
    JsonShortTermMemoryStore,
    MemoryEventStore,
)
from ai_advent_agent.storage import ContextStorageError, JsonContextStore, JsonSummaryStore
from ai_advent_agent.token_report import TokenReport, TokenReportStore

EXIT_COMMANDS = {"/exit", "/quit", "exit", "quit"}


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


def print_config(agent: SimpleAgent) -> None:
    config = agent.config
    print(
        "Текущая конфигурация:\n"
        f"  model: {config.model}\n"
        f"  strategy: {config.strategy}\n"
        f"  temperature: {config.temperature}\n"
        f"  max_tokens: {config.max_tokens}\n"
        f"  thinking: {config.thinking_type}\n"
        f"  reasoning_effort: {config.reasoning_effort or '-'}\n"
        f"  context_window_tokens: {format_number(config.context_window_tokens)}\n"
        f"  warn_context_ratio: {config.warn_context_ratio:.2f}\n"
        f"  overflow_policy: {config.overflow_policy.value}\n"
        f"  context_strategy: {config.context_strategy}\n"
        f"  summary_mode: {config.summary_mode}\n"
        f"  recent_messages_limit: {config.recent_messages_limit}\n"
        f"  summarize_every_messages: {config.summarize_every_messages}\n"
        f"  summary_max_tokens: {config.summary_max_tokens}\n"
        f"  input_price_per_1m_tokens: {config.input_price_per_1m_tokens}\n"
        f"  output_price_per_1m_tokens: {config.output_price_per_1m_tokens}\n"
        f"  context_file: {agent.context_path or 'disabled'}\n"
        f"  facts_file: {agent.facts_path or 'disabled'}\n"
        f"  branches_file: {agent.branches_path or 'disabled'}\n"
        f"  summary_file: {agent.summary_path or 'disabled'}\n"
        f"  short_term_memory_file: {agent.short_term_memory_path or 'disabled'}\n"
        f"  working_memory_file: {agent.working_memory_path or 'disabled'}\n"
        f"  long_term_memory_file: {agent.long_term_memory_path or 'disabled'}\n"
        f"  memory_events_file: {agent.memory_events_path or 'disabled'}\n"
        f"  token_report_file: {agent.token_report_path or 'disabled'}\n"
    )


def print_metadata(response: AgentResponse) -> None:
    usage = response.usage or {}
    print(
        "\n--- metadata ---\n"
        f"model: {response.model}\n"
        f"strategy: {response.strategy}\n"
        f"finish_reason: {response.finish_reason}\n"
        f"elapsed_seconds: {response.elapsed_seconds:.2f}\n"
        f"message_count: {response.message_count}\n"
        f"summary_active: {response.summary_active}\n"
        f"context_saved: {response.context_saved}\n"
        f"context_path: {response.context_path or '-'}\n"
        f"prompt_tokens_actual: {usage.get('prompt_tokens', '-')}\n"
        f"completion_tokens_actual: {usage.get('completion_tokens', '-')}\n"
        f"total_tokens_actual: {usage.get('total_tokens', '-')}"
    )
    print_token_report(response.token_report)


def print_token_report(report: TokenReport) -> None:
    history_tokens = format_number(report.history_tokens_before_estimated)
    projected_tokens = format_number(report.projected_total_tokens_estimated)
    print(
        "\n--- token report ---\n"
        f"request_tokens_estimated: {format_number(report.request_tokens_estimated)}\n"
        f"history_tokens_before_estimated: {history_tokens}\n"
        f"prompt_tokens_estimated: {format_number(report.prompt_tokens_estimated)}\n"
        f"projected_total_tokens_estimated: {projected_tokens}\n"
        f"context_window_tokens: {format_number(report.context_window_tokens)}\n"
        f"context_usage: {report.context_usage_percent:.2f}%\n"
        f"projected_usage: {report.projected_usage_percent:.2f}%\n"
        f"warning: {report.warn_threshold_reached}\n"
        f"overflow_detected: {report.overflow_detected}\n"
        f"overflow_policy: {report.overflow_policy}\n"
        f"trimmed_messages_count: {report.trimmed_messages_count}\n"
        f"summary_active: {report.summary_active}\n"
        f"summary_tokens_estimated: {format_number(report.summary_tokens_estimated)}\n"
        f"summarized_messages_count: {format_number(report.summarized_messages_count)}"
    )

    if report.memory_layers_active:
        print(
            "memory_layers_active: true\n"
            f"memory_layer_entries: {report.memory_layer_entries}\n"
            f"memory_layer_tokens_estimated: {report.memory_layer_tokens_estimated}\n"
            "memory_prompt_tokens_estimated: "
            f"{format_number(report.memory_prompt_tokens_estimated)}\n"
            f"prompt_assembly_order: {', '.join(report.prompt_assembly_order)}"
        )

    if report.response_tokens_estimated is not None:
        print(f"response_tokens_estimated: {format_number(report.response_tokens_estimated)}")
    if report.history_tokens_after_response_estimated is not None:
        print(
            "history_tokens_after_response_estimated: "
            f"{format_number(report.history_tokens_after_response_estimated)}"
        )

    print(
        f"prompt_tokens_actual: {format_optional_number(report.prompt_tokens_actual)}\n"
        f"completion_tokens_actual: {format_optional_number(report.completion_tokens_actual)}\n"
        f"total_tokens_actual: {format_optional_number(report.total_tokens_actual)}"
    )

    if report.estimated_total_cost_usd is not None:
        print(
            "estimated_cost_usd: "
            f"input={report.estimated_input_cost_usd:.8f}, "
            f"output={report.estimated_output_cost_usd:.8f}, "
            f"total={report.estimated_total_cost_usd:.8f}"
        )
    if report.elapsed_seconds is not None:
        print(f"elapsed_seconds: {report.elapsed_seconds:.2f}")


def print_token_breakdown(agent: SimpleAgent) -> None:
    breakdown = agent.get_token_breakdown()
    config = agent.config
    ratio = breakdown.total / config.context_window_tokens
    projected_ratio = (breakdown.total + config.max_tokens) / config.context_window_tokens
    print(
        "Token breakdown текущей истории:\n"
        f"  messages: {breakdown.message_count}\n"
        f"  total_estimated: {format_number(breakdown.total)}\n"
        f"  system: {format_number(breakdown.system)}\n"
        f"  user: {format_number(breakdown.user)}\n"
        f"  assistant: {format_number(breakdown.assistant)}\n"
        f"  tool: {format_number(breakdown.tool)}\n"
        f"  context_window_tokens: {format_number(config.context_window_tokens)}\n"
        f"  current_context_usage: {ratio * 100:.2f}%\n"
        f"  projected_with_max_tokens: {projected_ratio * 100:.2f}%\n"
    )


def print_history_summary(messages: list[Message]) -> None:
    role_counts: dict[str, int] = {}
    for message in messages:
        role = message.get("role", "unknown")
        role_counts[role] = role_counts.get(role, 0) + 1

    print(f"Сообщений в истории: {len(messages)}")
    for role, count in sorted(role_counts.items()):
        print(f"  {role}: {count}")
    print()


def print_history_full(messages: list[Message]) -> None:
    for index, message in enumerate(messages, start=1):
        content = message.get("content", "")
        print(f"[{index}] {message.get('role', 'unknown')}\n{content}\n")


def print_memory_summary(agent: SimpleAgent) -> None:
    short_notes = agent.short_term_memory.normalized_notes()
    recent_messages = agent.short_term_memory.recent_messages
    working = agent.working_memory.normalized()
    long_term = agent.long_term_memory.normalized()
    print("Memory layers:")
    print(
        f"  short-term: notes={len(short_notes)}, "
        f"recent_messages={len(recent_messages)}, file={agent.short_term_memory_path or 'disabled'}"
    )
    print(f"  working: entries={len(working)}, file={agent.working_memory_path or 'disabled'}")
    print(
        f"  long-term: entries={len(long_term)}, file={agent.long_term_memory_path or 'disabled'}"
    )
    print(f"  events: {agent.memory_events_path or 'disabled'}\n")


def print_memory_layer(agent: SimpleAgent, layer: str) -> None:
    if layer == "short":
        notes = agent.short_term_memory.normalized_notes()
        recent_messages = agent.short_term_memory.recent_messages
        print("Short-term memory:")
        if not notes and not recent_messages:
            print("  пусто\n")
            return
        if notes:
            print("  Явные notes:")
            for note in notes:
                print(f"    - {note}")
        if recent_messages:
            print("  Последние сообщения:")
            for message in recent_messages:
                print(f"    - {message['role']}: {message['content']}")
        print()
        return

    if layer == "working":
        print_key_value_memory("Working memory", agent.working_memory.normalized())
        return

    if layer == "long":
        print_key_value_memory("Long-term memory", agent.long_term_memory.normalized())
        return

    raise ValueError("memory layer должен быть short, working или long")


def print_key_value_memory(title: str, entries: dict[str, str]) -> None:
    print(f"{title}:")
    if not entries:
        print("  пусто\n")
        return
    for key, value in entries.items():
        print(f"  {key}: {value}")
    print()


def handle_command(command: str, agent: SimpleAgent, show_metadata: bool = True) -> bool:
    registry = build_command_registry()
    result = CommandRouter(registry).route(
        command,
        CommandContext(agent=agent, show_metadata=show_metadata),
    )
    if result.exit_requested:
        print("Выход.")
    return result.handled


def extract_path_argument(command: str, prefix: str) -> Path | None:
    argument = command[len(prefix) :].strip()
    if not argument:
        return None
    return Path(argument.strip('"').strip("'"))


def analyze_file(path: Path, agent: SimpleAgent) -> None:
    text = path.expanduser().read_text(encoding="utf-8")
    report = agent.build_file_token_report(text)
    print(f"Файл: {path}")
    print(f"Размер: {format_number(len(text))} символов")
    print_token_report(report)
    print("\nDry-run: содержимое файла не отправлялось в API и не сохранялось в history.\n")


def ask_file(path: Path, agent: SimpleAgent, *, show_metadata: bool) -> None:
    text = path.expanduser().read_text(encoding="utf-8")
    print(
        f"Файл {path} будет отправлен в модель как одно user message "
        f"({format_number(agent.estimate_text_tokens(text))} estimated tokens)."
    )
    response = agent.ask(text)
    print(f"\nAgent:\n{response.content.strip()}")
    if show_metadata:
        print_metadata(response)
    print()


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
        token_report_store=token_report_store,
        load_context=not args.no_load_context,
    )


def format_number(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def format_optional_number(value: int | None) -> str:
    return "-" if value is None else format_number(value)


def read_user_input(registry: CommandRegistry, *, plain_input: bool = False) -> str:
    if plain_input:
        return input("Вы: ")
    try:
        from prompt_toolkit import prompt
    except ImportError:
        return input("Вы: ")
    return prompt("Вы: ", completer=CommandCompleter(registry), complete_while_typing=True)


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

    print("Day 11. Агент с явными memory layers")
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
    print(f"Файл token reports: {agent.token_report_path or 'логирование отключено'}")
    print(f"Загружено сообщений: {len(history)}")
    print("Введите / для меню команд или /help для справки.\n")

    while True:
        try:
            user_text = read_user_input(command_registry, plain_input=args.plain_input).strip()
        except (EOFError, KeyboardInterrupt) as _error:
            print("\nВыход.")
            break

        if not user_text:
            continue

        command_result = command_router.route(
            user_text,
            CommandContext(agent=agent, show_metadata=show_metadata),
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
