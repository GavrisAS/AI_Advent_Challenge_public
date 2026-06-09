"""CLI interface for the Day 6 agent."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from ai_advent_agent.agent import AgentResponse, SimpleAgent
from ai_advent_agent.config import (
    DEFAULT_API_URL,
    DEFAULT_MODEL,
    DEFAULT_SYSTEM_PROMPT,
    AgentConfig,
    AgentStrategy,
)
from ai_advent_agent.env import load_env_file
from ai_advent_agent.llm_client import DeepSeekError, LLMClient

EXIT_COMMANDS = {"/exit", "/quit", "exit", "quit"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Day 6: первый stateful LLM-агент через DeepSeek API."
    )
    parser.add_argument("--model", default=os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL))
    parser.add_argument("--api-url", default=os.getenv("DEEPSEEK_API_URL", DEFAULT_API_URL))
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=1000)
    parser.add_argument("--strategy", choices=["direct", "step_by_step"], default="direct")
    parser.add_argument("--thinking", choices=["disabled", "enabled"], default="disabled")
    parser.add_argument("--reasoning-effort", default=None)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Путь к .env. По умолчанию ищется .env в корне проекта.",
    )
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Не выводить токены, время и finish_reason после ответа.",
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
        "  /help                  — показать подсказку\n"
        "  /reset                 — очистить историю сессии агента\n"
        "  /history               — показать количество сообщений в истории\n"
        "  /config                — показать текущие настройки\n"
        "  /strategy direct       — переключить стратегию на прямой ответ\n"
        "  /strategy step_by_step — переключить стратегию на пошаговый ответ\n"
        "  /exit                  — выйти\n"
    )


def print_config(config: AgentConfig) -> None:
    print(
        "Текущая конфигурация:\n"
        f"  model: {config.model}\n"
        f"  strategy: {config.strategy}\n"
        f"  temperature: {config.temperature}\n"
        f"  max_tokens: {config.max_tokens}\n"
        f"  thinking: {config.thinking_type}\n"
        f"  reasoning_effort: {config.reasoning_effort or '-'}\n"
    )


def print_metadata(response: AgentResponse) -> None:
    print("\n--- metadata ---")
    print(f"model: {response.model}")
    print(f"strategy: {response.strategy}")
    print(f"finish_reason: {response.finish_reason}")
    print(f"elapsed_seconds: {response.elapsed_seconds:.3f}")
    print(f"prompt_tokens: {response.prompt_tokens}")
    print(f"completion_tokens: {response.completion_tokens}")
    print(f"total_tokens: {response.total_tokens}")
    print(f"messages_in_session: {response.message_count}")
    if response.has_reasoning_content:
        print("has_reasoning_content: true")


def handle_command(command: str, agent: SimpleAgent) -> bool:
    """Handle CLI commands. Returns True when command was handled."""

    normalized = command.strip().lower()

    if normalized == "/help":
        print_help()
        return True

    if normalized == "/reset":
        agent.reset()
        print("История сессии очищена.\n")
        return True

    if normalized == "/history":
        history = agent.get_history()
        print(f"Сообщений в истории: {len(history)}")
        print(f"Из них пользовательских: {sum(1 for item in history if item['role'] == 'user')}\n")
        return True

    if normalized == "/config":
        print_config(agent.config)
        return True

    if normalized.startswith("/strategy"):
        parts = normalized.split(maxsplit=1)
        if len(parts) != 2 or parts[1] not in {"direct", "step_by_step"}:
            print("Использование: /strategy direct или /strategy step_by_step\n")
            return True

        agent.set_strategy(parts[1])  # type: ignore[arg-type]
        print(f"Стратегия изменена: {agent.config.strategy}\n")
        return True

    return False


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
    )
    client = LLMClient(
        api_key=api_key,
        api_url=args.api_url,
        timeout_seconds=args.timeout,
    )
    return SimpleAgent(client=client, config=config)


def main(argv: list[str] | None = None) -> None:
    # Load default .env first, then optionally explicit .env. Existing variables win.
    load_env_file()
    args = parse_args(argv)
    if args.env_file:
        load_env_file(args.env_file)

    try:
        agent = build_agent(args)
    except ValueError as error:
        print(f"Ошибка конфигурации: {error}", file=sys.stderr)
        sys.exit(1)

    show_metadata = not args.no_metadata

    print("Day 6. Первый агент")
    print(f"Модель: {agent.config.model}")
    print(f"Стратегия: {agent.config.strategy}")
    print("Введите запрос. Команды: /help, /reset, /strategy direct, /strategy step_by_step, /exit.\n")

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

        if handle_command(user_text, agent):
            continue

        try:
            response = agent.ask(user_text)
        except (DeepSeekError, ValueError) as error:
            print(f"\nОшибка: {error}\n", file=sys.stderr)
            continue

        print(f"\nAgent:\n{response.content.strip()}")
        if show_metadata:
            print_metadata(response)
        print()


if __name__ == "__main__":
    main()
