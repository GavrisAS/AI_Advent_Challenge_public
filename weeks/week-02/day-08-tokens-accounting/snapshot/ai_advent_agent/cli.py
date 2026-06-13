"""CLI interface for the Day 8 token-aware persistent-context agent."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from ai_advent_agent.agent import AgentResponse, ContextOverflowError, SimpleAgent
from ai_advent_agent.config import (
    DEFAULT_API_URL,
    DEFAULT_CONTEXT_FILE,
    DEFAULT_CONTEXT_WINDOW_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TOKEN_REPORT_FILE,
    DEFAULT_WARN_CONTEXT_RATIO,
    AgentConfig,
    ContextOverflowPolicy,
    parse_overflow_policy,
)
from ai_advent_agent.env import load_env_file
from ai_advent_agent.llm_client import DeepSeekError, LLMClient, Message
from ai_advent_agent.storage import ContextStorageError, JsonContextStore
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
    token_report_file_default = os.getenv("AI_ADVENT_TOKEN_REPORT_FILE") or str(DEFAULT_TOKEN_REPORT_FILE)

    parser = argparse.ArgumentParser(
        description="Day 8: LLM-агент с persistent context и подсчётом токенов."
    )
    parser.add_argument("--model", default=os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL))
    parser.add_argument("--api-url", default=os.getenv("DEEPSEEK_API_URL", DEFAULT_API_URL))
    parser.add_argument("--temperature", type=float, default=_env_float("AGENT_TEMPERATURE", 0.7))
    parser.add_argument("--max-tokens", type=int, default=_env_int("AGENT_MAX_TOKENS", 1000))
    parser.add_argument("--strategy", choices=["direct", "step_by_step"], default=os.getenv("AGENT_STRATEGY", "direct"))
    parser.add_argument("--thinking", choices=["disabled", "enabled"], default=os.getenv("AGENT_THINKING", "disabled"))
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
    return parser.parse_args(argv)


def require_api_key() -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print(
            "Ошибка: не найдена переменная окружения DEEPSEEK_API_KEY.\n"
            "Скопируйте .env.example в .env и добавьте ключ или экспортируйте переменную в терминале.",
            file=sys.stderr,
        )
        sys.exit(1)
    return api_key


def print_help() -> None:
    print(
        "Команды:\n"
        "  /help                         — показать подсказку\n"
        "  /reset                        — очистить историю, context JSON и token reports\n"
        "  /clear-context                — удалить JSON-файл контекста и token reports\n"
        "  /history                      — показать количество сообщений в истории\n"
        "  /history full                 — показать сохранённую историю сообщений\n"
        "  /context                      — показать путь к JSON-файлу контекста\n"
        "  /tokens                       — показать token breakdown текущей истории\n"
        "  /last-report                  — показать последний token report\n"
        "  /analyze-file <path>          — dry-run: оценить токены файла без отправки в API\n"
        "  /ask-file <path>              — отправить содержимое файла в модель как user message\n"
        "  /config                       — показать текущие настройки\n"
        "  /strategy direct              — переключить стратегию на прямой ответ\n"
        "  /strategy step_by_step        — переключить стратегию на пошаговый ответ\n"
        "  /context-mode error           — не отправлять запрос при переполнении\n"
        "  /context-mode no_trim         — отправить как есть и показать ошибку API, если она будет\n"
        "  /context-mode sliding_window  — удалять старые сообщения при переполнении\n"
        "  /exit                         — выйти\n"
    )


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
        f"  input_price_per_1m_tokens: {config.input_price_per_1m_tokens}\n"
        f"  output_price_per_1m_tokens: {config.output_price_per_1m_tokens}\n"
        f"  context_file: {agent.context_path or 'disabled'}\n"
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
        f"context_saved: {response.context_saved}\n"
        f"context_path: {response.context_path or '-'}\n"
        f"prompt_tokens_actual: {usage.get('prompt_tokens', '-')}\n"
        f"completion_tokens_actual: {usage.get('completion_tokens', '-')}\n"
        f"total_tokens_actual: {usage.get('total_tokens', '-')}"
    )
    print_token_report(response.token_report)


def print_token_report(report: TokenReport) -> None:
    print(
        "\n--- token report ---\n"
        f"request_tokens_estimated: {format_number(report.request_tokens_estimated)}\n"
        f"history_tokens_before_estimated: {format_number(report.history_tokens_before_estimated)}\n"
        f"prompt_tokens_estimated: {format_number(report.prompt_tokens_estimated)}\n"
        f"projected_total_tokens_estimated: {format_number(report.projected_total_tokens_estimated)}\n"
        f"context_window_tokens: {format_number(report.context_window_tokens)}\n"
        f"context_usage: {report.context_usage_percent:.2f}%\n"
        f"projected_usage: {report.projected_usage_percent:.2f}%\n"
        f"warning: {report.warn_threshold_reached}\n"
        f"overflow_detected: {report.overflow_detected}\n"
        f"overflow_policy: {report.overflow_policy}\n"
        f"trimmed_messages_count: {report.trimmed_messages_count}"
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


def handle_command(command: str, agent: SimpleAgent, show_metadata: bool = True) -> bool:
    normalized = command.strip()
    lowered = normalized.lower()

    try:
        if lowered == "/help":
            print_help()
            return True

        if lowered == "/reset":
            agent.reset()
            print("История и token reports очищены. В JSON сохранён system prompt.\n")
            return True

        if lowered == "/clear-context":
            agent.clear_context_file()
            print("Файл контекста и token reports удалены. Новая сессия начата с system prompt.\n")
            return True

        if lowered == "/history":
            print_history_summary(agent.get_history())
            return True

        if lowered == "/history full":
            print_history_full(agent.get_history())
            return True

        if lowered == "/context":
            print(f"Файл контекста: {agent.context_path or 'сохранение отключено'}")
            print(f"Файл token reports: {agent.token_report_path or 'логирование отключено'}\n")
            return True

        if lowered == "/tokens":
            print_token_breakdown(agent)
            return True

        if lowered == "/last-report":
            if agent.last_token_report is None:
                print("За текущий запуск ещё нет token report.\n")
            else:
                print_token_report(agent.last_token_report)
                print()
            return True

        if lowered == "/config":
            print_config(agent)
            return True

        if lowered.startswith("/strategy"):
            parts = lowered.split(maxsplit=1)
            if len(parts) != 2 or parts[1] not in {"direct", "step_by_step"}:
                print("Использование: /strategy direct или /strategy step_by_step\n")
                return True

            agent.set_strategy(parts[1])  # type: ignore[arg-type]
            print(f"Стратегия изменена: {agent.config.strategy}\n")
            return True

        if lowered.startswith("/context-mode"):
            parts = lowered.split(maxsplit=1)
            if len(parts) != 2:
                print("Использование: /context-mode error|no_trim|sliding_window\n")
                return True
            agent.set_overflow_policy(parse_overflow_policy(parts[1]))
            print(f"Context overflow policy изменена: {agent.config.overflow_policy.value}\n")
            return True

        if lowered.startswith("/analyze-file"):
            path = extract_path_argument(normalized, "/analyze-file")
            if path is None:
                print("Использование: /analyze-file path/to/skills-all.md\n")
                return True
            analyze_file(path, agent)
            return True

        if lowered.startswith("/ask-file"):
            path = extract_path_argument(normalized, "/ask-file")
            if path is None:
                print("Использование: /ask-file path/to/skills-all.md\n")
                return True
            ask_file(path, agent, show_metadata=show_metadata)
            return True
    except ContextStorageError as error:
        print(f"Ошибка контекста: {error}\n", file=sys.stderr)
        return True
    except (OSError, UnicodeDecodeError) as error:
        print(f"Ошибка файла: {error}\n", file=sys.stderr)
        return True
    except ValueError as error:
        print(f"Ошибка команды: {error}\n", file=sys.stderr)
        return True

    return False


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
    )
    client = LLMClient(
        api_key=api_key,
        api_url=args.api_url,
        timeout_seconds=args.timeout,
    )
    context_store = None if args.no_persist else JsonContextStore(args.context_file)
    token_report_store = None if args.no_token_report_log else TokenReportStore(args.token_report_file)
    return SimpleAgent(
        client=client,
        config=config,
        context_store=context_store,
        token_report_store=token_report_store,
        load_context=not args.no_load_context,
    )


def format_number(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def format_optional_number(value: int | None) -> str:
    return "-" if value is None else format_number(value)


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

    print("Day 8. Агент с сохранением контекста и подсчётом токенов")
    print(f"Модель: {agent.config.model}")
    print(f"Стратегия: {agent.config.strategy}")
    print(f"Context window: {format_number(agent.config.context_window_tokens)} tokens")
    print(f"Overflow policy: {agent.config.overflow_policy.value}")
    print(f"Файл контекста: {agent.context_path or 'сохранение отключено'}")
    print(f"Файл token reports: {agent.token_report_path or 'логирование отключено'}")
    print(f"Загружено сообщений: {len(history)}")
    print(
        "Введите запрос. Команды: /help, /tokens, /analyze-file <path>, "
        "/context-mode sliding_window, /exit.\n"
    )

    while True:
        try:
            user_text = input("Вы: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            break

        if not user_text:
            continue

        if user_text.lower() in EXIT_COMMANDS:
            print("Выход.")
            break

        if handle_command(user_text, agent, show_metadata=show_metadata):
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
