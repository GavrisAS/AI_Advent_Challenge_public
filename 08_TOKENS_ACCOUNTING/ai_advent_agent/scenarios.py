"""Offline token scenarios for Day 8 demonstrations.

These scenarios do not call the LLM API. They show how estimated context tokens
grow for short/long dialogs and for a large file such as skills-all.md.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ai_advent_agent.config import DEFAULT_CONTEXT_WINDOW_TOKENS, DEFAULT_SYSTEM_PROMPT
from ai_advent_agent.llm_client import Message
from ai_advent_agent.token_counter import ApproxTokenCounter


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Day 8 token growth scenarios.")
    subparsers = parser.add_subparsers(dest="scenario", required=True)

    short = subparsers.add_parser("short", help="Короткий диалог: 3 коротких user/assistant turn.")
    short.add_argument("--context-window-tokens", type=int, default=DEFAULT_CONTEXT_WINDOW_TOKENS)
    short.add_argument("--max-tokens", type=int, default=1000)

    long = subparsers.add_parser("long", help="Длинный синтетический диалог без API-вызовов.")
    long.add_argument("--turns", type=int, default=50)
    long.add_argument("--context-window-tokens", type=int, default=DEFAULT_CONTEXT_WINDOW_TOKENS)
    long.add_argument("--max-tokens", type=int, default=1000)

    overflow = subparsers.add_parser(
        "overflow-file",
        help="Dry-run для большого файла, например skills-all.md. Файл не отправляется в API.",
    )
    overflow.add_argument("path", type=Path)
    overflow.add_argument("--context-window-tokens", type=int, default=DEFAULT_CONTEXT_WINDOW_TOKENS)
    overflow.add_argument("--max-tokens", type=int, default=1000)

    return parser.parse_args(argv)


def format_number(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def print_row(step: str, messages: list[Message], counter: ApproxTokenCounter, *, context_window: int, max_tokens: int) -> None:
    prompt_tokens = counter.count_messages(messages)
    projected_total = prompt_tokens + max_tokens
    usage = projected_total / context_window * 100
    print(
        f"{step:<16} messages={len(messages):>3} "
        f"prompt≈{format_number(prompt_tokens):>10} "
        f"projected≈{format_number(projected_total):>10} "
        f"usage={usage:>7.2f}%"
    )


def scenario_short(context_window: int, max_tokens: int) -> None:
    counter = ApproxTokenCounter()
    messages: list[Message] = [{"role": "system", "content": DEFAULT_SYSTEM_PROMPT}]
    turns = [
        ("Объясни, что такое context management.", "Context management — это управление тем, что модель видит в текущем запросе."),
        ("Чем он отличается от memory management?", "Memory management отвечает за сохранение и восстановление данных между сессиями."),
        ("Дай короткий практический пример.", "Пример: хранить messages в JSON и загружать их при следующем запуске агента."),
    ]

    print("Scenario: short dialog")
    print_row("start", messages, counter, context_window=context_window, max_tokens=max_tokens)
    for index, (user, assistant) in enumerate(turns, start=1):
        messages.append({"role": "user", "content": user})
        print_row(f"turn {index} user", messages, counter, context_window=context_window, max_tokens=max_tokens)
        messages.append({"role": "assistant", "content": assistant})
        print_row(f"turn {index} done", messages, counter, context_window=context_window, max_tokens=max_tokens)


def scenario_long(turns: int, context_window: int, max_tokens: int) -> None:
    counter = ApproxTokenCounter()
    messages: list[Message] = [{"role": "system", "content": DEFAULT_SYSTEM_PROMPT}]
    user_template = (
        "Продолжи проект агента. Нужно учитывать context management, persistent storage, "
        "подсчёт токенов, предупреждения о лимите и аккуратное поведение при переполнении. "
        "Это синтетическое сообщение номер {index}."
    )
    assistant_template = (
        "На шаге {index} агент сохраняет историю, оценивает токены текущего запроса, "
        "считает весь контекст, показывает projected usage и продолжает диалог. "
        "Это демонстрационный ответ для накопления контекста."
    )

    print(f"Scenario: long dialog, turns={turns}")
    print_row("start", messages, counter, context_window=context_window, max_tokens=max_tokens)
    for index in range(1, turns + 1):
        messages.append({"role": "user", "content": user_template.format(index=index)})
        messages.append({"role": "assistant", "content": assistant_template.format(index=index)})
        if index <= 5 or index % 10 == 0 or index == turns:
            print_row(f"turn {index}", messages, counter, context_window=context_window, max_tokens=max_tokens)


def scenario_overflow_file(path: Path, context_window: int, max_tokens: int) -> None:
    counter = ApproxTokenCounter()
    text = path.expanduser().read_text(encoding="utf-8")
    messages: list[Message] = [
        {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]
    file_tokens = counter.count_text(text)
    prompt_tokens = counter.count_messages(messages)
    projected_total = prompt_tokens + max_tokens
    usage = projected_total / context_window * 100

    print("Scenario: overflow-file dry-run")
    print(f"file: {path}")
    print(f"chars: {format_number(len(text))}")
    print(f"file_tokens_estimated: {format_number(file_tokens)}")
    print(f"prompt_tokens_estimated: {format_number(prompt_tokens)}")
    print(f"max_tokens: {format_number(max_tokens)}")
    print(f"projected_total_tokens_estimated: {format_number(projected_total)}")
    print(f"context_window_tokens: {format_number(context_window)}")
    print(f"projected_usage: {usage:.2f}%")
    print(f"overflow: {projected_total > context_window}")
    print("Файл не отправлялся в API. Это безопасная проверка перед реальным запросом.")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.scenario == "short":
        scenario_short(args.context_window_tokens, args.max_tokens)
    elif args.scenario == "long":
        scenario_long(args.turns, args.context_window_tokens, args.max_tokens)
    elif args.scenario == "overflow-file":
        scenario_overflow_file(args.path, args.context_window_tokens, args.max_tokens)
    else:
        raise SystemExit(f"Unknown scenario: {args.scenario}")


if __name__ == "__main__":
    main()
