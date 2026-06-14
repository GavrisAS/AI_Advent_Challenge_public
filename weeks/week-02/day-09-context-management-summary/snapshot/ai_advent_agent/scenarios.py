"""Offline token scenarios for Day 8 and Day 9 demonstrations.

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
    overflow.add_argument(
        "--context-window-tokens", type=int, default=DEFAULT_CONTEXT_WINDOW_TOKENS
    )
    overflow.add_argument("--max-tokens", type=int, default=1000)

    summary = subparsers.add_parser(
        "summary-comparison",
        help="Day 9: сравнить длинный диалог без сжатия и с synthetic summary.",
    )
    summary.add_argument("--turns", type=int, default=24)
    summary.add_argument("--recent-messages-limit", type=int, default=6)
    summary.add_argument("--max-tokens", type=int, default=1000)

    return parser.parse_args(argv)


def format_number(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def print_row(
    step: str,
    messages: list[Message],
    counter: ApproxTokenCounter,
    *,
    context_window: int,
    max_tokens: int,
) -> None:
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
        (
            "Объясни, что такое context management.",
            "Context management — это управление тем, что модель видит в текущем запросе.",
        ),
        (
            "Чем он отличается от memory management?",
            "Memory management отвечает за сохранение и восстановление данных между сессиями.",
        ),
        (
            "Дай короткий практический пример.",
            "Пример: хранить messages в JSON и загружать их при следующем запуске агента.",
        ),
    ]

    print("Scenario: short dialog")
    print_row("start", messages, counter, context_window=context_window, max_tokens=max_tokens)
    for index, (user, assistant) in enumerate(turns, start=1):
        messages.append({"role": "user", "content": user})
        print_row(
            f"turn {index} user",
            messages,
            counter,
            context_window=context_window,
            max_tokens=max_tokens,
        )
        messages.append({"role": "assistant", "content": assistant})
        print_row(
            f"turn {index} done",
            messages,
            counter,
            context_window=context_window,
            max_tokens=max_tokens,
        )


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
            print_row(
                f"turn {index}",
                messages,
                counter,
                context_window=context_window,
                max_tokens=max_tokens,
            )


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


def build_synthetic_long_dialog(turns: int) -> list[Message]:
    messages: list[Message] = [{"role": "system", "content": DEFAULT_SYSTEM_PROMPT}]
    for index in range(1, turns + 1):
        if index == 1:
            user = (
                "Важный ранний факт: пользователя зовут Алексей, проект называется "
                "AI Advent Challenge, кодовое слово amber."
            )
        else:
            user = (
                "Продолжи обсуждение context management. Нужно учитывать persistent context, "
                "подсчёт токенов, лимиты, команды CLI и тесты. "
                f"Это синтетическое сообщение номер {index}."
            )
        assistant = (
            "Зафиксировал требования и продолжаю проектировать агент. "
            "Нужно отделять storage, token accounting, CLI и поведение при переполнении. "
            f"Это синтетический ответ номер {index}."
        )
        messages.append({"role": "user", "content": user})
        messages.append({"role": "assistant", "content": assistant})
    return messages


def scenario_summary_comparison(
    *,
    turns: int,
    recent_messages_limit: int,
    max_tokens: int,
) -> None:
    counter = ApproxTokenCounter()
    full_history = build_synthetic_long_dialog(turns)
    next_user: Message = {
        "role": "user",
        "content": "Что мы решили в начале и какой следующий шаг?",
    }
    full_request = [*full_history, next_user]
    full_prompt_tokens = counter.count_messages(full_request)

    conversation = full_history[1:]
    replaced_messages = max(0, len(conversation) - recent_messages_limit)
    early_fact = "Пользователя зовут Алексей; проект AI Advent Challenge; кодовое слово amber."
    summary_text = (
        "Summary старой истории: "
        f"{early_fact} Агент должен развивать context management, storage, token accounting, "
        "CLI-команды и тесты."
    )
    compressed_request: list[Message] = [
        full_history[0],
        {"role": "system", "content": f"Summary предыдущей истории диалога:\n{summary_text}"},
        *conversation[replaced_messages:],
        next_user,
    ]
    compressed_prompt_tokens = counter.count_messages(compressed_request)
    saved_tokens = full_prompt_tokens - compressed_prompt_tokens
    kept_early_fact = all(part in summary_text for part in ["Алексей", "AI Advent", "amber"])

    print("# Day 09 summary comparison")
    print()
    print(f"- turns: {turns}")
    print(f"- full_messages: {len(full_request)}")
    print(f"- compressed_messages: {len(compressed_request)}")
    print(f"- replaced_messages: {replaced_messages}")
    print(f"- recent_messages_limit: {recent_messages_limit}")
    print(f"- full_prompt_tokens_estimated: {format_number(full_prompt_tokens)}")
    print(f"- compressed_prompt_tokens_estimated: {format_number(compressed_prompt_tokens)}")
    print(f"- saved_prompt_tokens_estimated: {format_number(saved_tokens)}")
    print(f"- projected_full_with_max_tokens: {format_number(full_prompt_tokens + max_tokens)}")
    print(
        "- projected_compressed_with_max_tokens: "
        f"{format_number(compressed_prompt_tokens + max_tokens)}"
    )
    print(f"- early_important_fact_preserved: {kept_early_fact}")
    print()
    print("## Summary")
    print()
    print(summary_text)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.scenario == "short":
        scenario_short(args.context_window_tokens, args.max_tokens)
    elif args.scenario == "long":
        scenario_long(args.turns, args.context_window_tokens, args.max_tokens)
    elif args.scenario == "overflow-file":
        scenario_overflow_file(args.path, args.context_window_tokens, args.max_tokens)
    elif args.scenario == "summary-comparison":
        scenario_summary_comparison(
            turns=args.turns,
            recent_messages_limit=args.recent_messages_limit,
            max_tokens=args.max_tokens,
        )
    else:
        raise SystemExit(f"Unknown scenario: {args.scenario}")


if __name__ == "__main__":
    main()
