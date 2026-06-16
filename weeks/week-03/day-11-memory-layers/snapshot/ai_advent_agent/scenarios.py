"""Offline token scenarios for Day 8, Day 9 and Day 10 demonstrations.

These scenarios do not call the LLM API. They show how estimated context tokens
grow for short/long dialogs and for a large file such as skills-all.md.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai_advent_agent.config import DEFAULT_CONTEXT_WINDOW_TOKENS, DEFAULT_SYSTEM_PROMPT
from ai_advent_agent.context_management import (
    BranchMemory,
    BranchSnapshot,
    JsonBranchesStore,
    JsonFactsStore,
    StickyFacts,
)
from ai_advent_agent.llm_client import Message
from ai_advent_agent.memory_layers import (
    JsonKeyValueMemoryStore,
    JsonShortTermMemoryStore,
    KeyValueMemory,
    MemoryEventStore,
    ShortTermMemory,
    build_memory_prompt_messages,
)
from ai_advent_agent.token_counter import ApproxTokenCounter
from ai_advent_agent.token_report import TokenReport, TokenReportStore


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

    context = subparsers.add_parser(
        "context-strategies-comparison",
        help="Day 10: offline comparison of sliding_window, sticky_facts and branching.",
    )
    context.add_argument("--recent-messages-limit", type=int, default=6)
    context.add_argument("--context-window-tokens", type=int, default=DEFAULT_CONTEXT_WINDOW_TOKENS)
    context.add_argument("--max-tokens", type=int, default=1000)
    context.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Куда сохранить демонстрационные JSON/JSONL артефакты.",
    )

    memory = subparsers.add_parser(
        "memory-layers-demo",
        help="Day 11: offline demo of short-term, working and long-term memory layers.",
    )
    memory.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Куда сохранить memory layer artifacts.",
    )
    memory.add_argument(
        "--results-file",
        type=Path,
        default=None,
        help="Куда сохранить Markdown-отчёт Day 11.",
    )
    memory.add_argument("--context-window-tokens", type=int, default=DEFAULT_CONTEXT_WINDOW_TOKENS)
    memory.add_argument("--max-tokens", type=int, default=1000)

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


def build_day10_dialog() -> list[Message]:
    system: Message = {"role": "system", "content": DEFAULT_SYSTEM_PROMPT}
    turns = [
        (
            "Цель: собрать ТЗ на AI-агента для поддержки инженера в репозитории. "
            "Важное имя проекта: Atlas Agent.",
            "Зафиксировал цель и название проекта.",
        ),
        (
            "Ограничение: агент не должен отправлять приватные файлы наружу и не должен делать "
            "commit без подтверждения.",
            "Добавил ограничения безопасности и git workflow.",
        ),
        (
            "Предпочтение: ответы на русском, коротко, с конкретными командами.",
            "Запомнил предпочтение по стилю ответов.",
        ),
        (
            "Решение: основной интерфейс будет CLI, а состояние хранится в JSON.",
            "Зафиксировал CLI и JSON-хранилище.",
        ),
        (
            "Нужно добавить команду для проверки токенов и отчёты JSONL.",
            "Добавил token report как часть требований.",
        ),
        (
            "Договорённость: offline-сценарии не требуют API key.",
            "Зафиксировал offline-режим без API key.",
        ),
        (
            "В ветке A сравним простой deterministic planner.",
            "Ветка A будет про deterministic planner.",
        ),
        (
            "В ветке B сравним planner с LLM-based extraction фактов.",
            "Ветка B будет про LLM-based extraction.",
        ),
    ]
    messages = [system]
    for user, assistant in turns:
        messages.append({"role": "user", "content": user})
        messages.append({"role": "assistant", "content": assistant})
    return messages


def scenario_context_strategies_comparison(
    *,
    recent_messages_limit: int,
    context_window: int,
    max_tokens: int,
    output_dir: Path,
) -> None:
    counter = ApproxTokenCounter()
    output_dir.mkdir(parents=True, exist_ok=True)
    dialog = build_day10_dialog()
    next_user: Message = {
        "role": "user",
        "content": "Собери итоговое ТЗ и не потеряй ранние ограничения проекта.",
    }

    facts = StickyFacts(
        {
            "goal": (
                "Собрать ТЗ на AI-агента для поддержки инженера в репозитории; проект Atlas Agent."
            ),
            "constraints": (
                "Не отправлять приватные файлы наружу; не делать commit без подтверждения."
            ),
            "preferences": "Ответы на русском, коротко, с конкретными командами.",
            "decisions": (
                "Основной интерфейс CLI; состояние хранится в JSON; token reports в JSONL."
            ),
            "agreements": "Offline-сценарии не требуют API key.",
            "user_data": "",
        }
    )

    sliding_request = [dialog[0], *dialog[1:][-recent_messages_limit:], next_user]
    facts_message: Message = {
        "role": "system",
        "content": "Sticky facts:\n"
        + "\n".join(f"- {key}: {value}" for key, value in facts.normalized().items() if value),
    }
    sticky_request = [dialog[0], facts_message, *dialog[1:][-recent_messages_limit:], next_user]

    checkpoint = BranchSnapshot(
        name="requirements-base", messages=dialog[:13], facts=facts.normalized()
    )
    branch_a = BranchSnapshot(
        name="deterministic-planner",
        messages=[*checkpoint.messages, dialog[13], dialog[14], next_user],
        facts=facts.normalized(),
    )
    branch_b = BranchSnapshot(
        name="llm-facts-planner",
        messages=[*checkpoint.messages, dialog[15], dialog[16], next_user],
        facts=facts.normalized(),
    )
    branching_request = [dialog[0], facts_message, *branch_b.messages[1:][-recent_messages_limit:]]

    rows = [
        ("sliding_window", sliding_request, "Среднее", "Ранние цель и ограничения потеряны"),
        ("sticky_facts", sticky_request, "Высокое", "Ранние факты сохранены в facts"),
        ("branching", branching_request, "Высокое", "Ветки изолируют альтернативные решения"),
    ]

    JsonFactsStore(output_dir / "facts.json").save(facts)
    branches_store = JsonBranchesStore(output_dir / "branches.json")
    branches_store.save(
        BranchMemory(
            active_branch="llm-facts-planner",
            latest_checkpoint="requirements-base",
            branches={
                "deterministic-planner": branch_a,
                "llm-facts-planner": branch_b,
            },
            checkpoints={"requirements-base": checkpoint},
        )
    )
    write_messages(output_dir / "sliding_window_messages.json", sliding_request)
    write_messages(output_dir / "sticky_facts_messages.json", sticky_request)
    write_messages(output_dir / "branching_active_messages.json", branching_request)

    report_store = TokenReportStore(output_dir / "token_reports.jsonl")
    report_store.clear()

    print("# Day 10 context strategies comparison")
    print()
    print("| strategy | prompt tokens | projected tokens | quality | stability |")
    print("|---|---:|---:|---|---|")
    for strategy, messages, quality, stability in rows:
        prompt_tokens = counter.count_messages(messages)
        projected = prompt_tokens + max_tokens
        report_store.append(
            TokenReport(
                request_tokens_estimated=counter.count_text(next_user["content"]),
                history_tokens_before_estimated=counter.count_messages(dialog),
                prompt_tokens_estimated=prompt_tokens,
                projected_total_tokens_estimated=projected,
                context_window_tokens=context_window,
                context_usage_ratio=prompt_tokens / context_window,
                projected_usage_ratio=projected / context_window,
                warn_threshold_reached=projected / context_window >= 0.8,
                overflow_detected=projected > context_window,
                overflow_policy="error",
                summary_active=False,
            )
        )
        print(
            f"| {strategy} | {format_number(prompt_tokens)} | "
            f"{format_number(projected)} | {quality} | {stability} |"
        )

    print()
    print(f"Artifacts: {output_dir}")
    print("Summary mode: off; API calls: 0")


def build_day11_demo_memory() -> tuple[ShortTermMemory, KeyValueMemory, KeyValueMemory, Message]:
    short_term = ShortTermMemory(
        notes=["Пользователь уже уточнил, что важна демонстрация разделения файлов памяти."],
        recent_messages=[
            {
                "role": "user",
                "content": "Нужно показать short-term, working и long-term memory отдельно.",
            },
            {
                "role": "assistant",
                "content": "Соберу prompt так, чтобы каждый слой был виден отдельно.",
            },
        ],
    )
    working = KeyValueMemory(
        {
            "task": "спроектировать memory layers для AI Advent агента",
            "constraint": "хранить short-term, working и long-term memory в отдельных файлах",
            "checklist": "показать prompt assembly, token reports и memory events",
        }
    )
    long_term = KeyValueMemory(
        {
            "language": "русский",
            "style": "кратко и технически",
            "preference": "показывать проверяемые артефакты и команды запуска",
        }
    )
    next_user: Message = {
        "role": "user",
        "content": "Сформулируй следующий шаг реализации ассистента с учётом моей памяти.",
    }
    return short_term, working, long_term, next_user


def scenario_memory_layers_demo(
    *,
    output_dir: Path,
    results_file: Path,
    context_window: int,
    max_tokens: int,
) -> None:
    counter = ApproxTokenCounter()
    output_dir.mkdir(parents=True, exist_ok=True)
    results_file.parent.mkdir(parents=True, exist_ok=True)

    short_term, working, long_term, next_user = build_day11_demo_memory()
    JsonShortTermMemoryStore(output_dir / "short_term_memory.json").save(short_term)
    JsonKeyValueMemoryStore(output_dir / "working_memory.json", layer="working").save(working)
    JsonKeyValueMemoryStore(output_dir / "long_term_memory.json", layer="long_term").save(long_term)

    event_store = MemoryEventStore(output_dir / "memory_events.jsonl")
    event_store.clear()
    event_store.append(
        action="remember",
        layer="long_term",
        key="language",
        value="русский",
    )
    event_store.append(
        action="remember",
        layer="long_term",
        key="style",
        value="кратко и технически",
    )
    event_store.append(
        action="remember",
        layer="working",
        key="task",
        value="спроектировать memory layers для AI Advent агента",
    )
    event_store.append(
        action="remember",
        layer="short_term",
        text="Пользователь уточнил важность раздельных файлов памяти.",
    )

    base_system: Message = {"role": "system", "content": DEFAULT_SYSTEM_PROMPT}
    no_memory_prompt = [base_system, next_user]
    working_blocks, working_metadata = build_memory_prompt_messages(
        short_term=ShortTermMemory(),
        working=working,
        long_term=KeyValueMemory(),
        token_counter=counter,
    )
    working_prompt = [base_system, *working_blocks, next_user]
    all_blocks, all_metadata = build_memory_prompt_messages(
        short_term=short_term,
        working=working,
        long_term=long_term,
        token_counter=counter,
    )
    all_prompt = [base_system, *all_blocks, next_user]

    variants = [
        ("no_memory", no_memory_prompt, None),
        ("working_only", working_prompt, working_metadata),
        ("all_layers", all_prompt, all_metadata),
    ]

    write_messages(output_dir / "prompt_no_memory.json", no_memory_prompt)
    write_messages(output_dir / "prompt_working_memory.json", working_prompt)
    write_messages(output_dir / "prompt_all_memory_layers.json", all_prompt)

    report_store = TokenReportStore(output_dir / "token_reports.jsonl")
    report_store.clear()

    rows: list[tuple[str, int, int, str]] = []
    decisions: dict[str, str] = {}
    for name, messages, metadata in variants:
        prompt_tokens = counter.count_messages(messages)
        projected = prompt_tokens + max_tokens
        decision = deterministic_memory_decision(messages)
        decisions[name] = decision
        rows.append((name, prompt_tokens, projected, decision))
        report_store.append(
            TokenReport(
                request_tokens_estimated=counter.count_text(next_user["content"]),
                history_tokens_before_estimated=counter.count_messages(messages[:-1]),
                prompt_tokens_estimated=prompt_tokens,
                projected_total_tokens_estimated=projected,
                context_window_tokens=context_window,
                context_usage_ratio=prompt_tokens / context_window,
                projected_usage_ratio=projected / context_window,
                warn_threshold_reached=projected / context_window >= 0.8,
                overflow_detected=projected > context_window,
                overflow_policy="error",
                summary_active=False,
                memory_layers_active=bool(metadata and metadata.layers_active),
                memory_layer_entries={} if metadata is None else metadata.layer_entries,
                memory_layer_tokens_estimated={}
                if metadata is None
                else metadata.layer_tokens_estimated,
                memory_prompt_tokens_estimated=0
                if metadata is None
                else metadata.prompt_tokens_estimated,
                prompt_assembly_order=["system", "current_user"]
                if metadata is None
                else ["system", *metadata.assembly_order, "current_user"],
            )
        )

    results_file.write_text(
        build_day11_results_markdown(rows, decisions, output_dir),
        encoding="utf-8",
    )

    print("# Day 11 memory layers demo")
    print()
    print("| variant | prompt tokens | projected tokens | deterministic decision |")
    print("|---|---:|---:|---|")
    for name, prompt_tokens, projected, decision in rows:
        print(
            f"| {name} | {format_number(prompt_tokens)} | {format_number(projected)} | {decision} |"
        )
    print()
    print(f"Artifacts: {output_dir}")
    print(f"Results: {results_file}")
    print("API calls: 0")


def deterministic_memory_decision(messages: list[Message]) -> str:
    prompt = "\n".join(message["content"] for message in messages)
    has_long = "language: русский" in prompt and "style: кратко и технически" in prompt
    has_working = "спроектировать memory layers" in prompt and "отдельных файлах" in prompt
    has_short = "текущий диалог" in prompt or "разделения файлов памяти" in prompt

    if has_long and has_working and has_short:
        return "ответ на русском, краткий, с учётом задачи и последних уточнений"
    if has_working:
        return "ответ учитывает текущую задачу, но без профиля и последних уточнений"
    return "общий ответ без персонализации и без состояния текущей задачи"


def build_day11_results_markdown(
    rows: list[tuple[str, int, int, str]],
    decisions: dict[str, str],
    output_dir: Path,
) -> str:
    table_rows = "\n".join(
        f"| `{name}` | {format_number(prompt_tokens)} | {format_number(projected)} | {decision} |"
        for name, prompt_tokens, projected, decision in rows
    )
    return f"""# Day 11 — Memory Layers

Сценарий выполнен offline, без API-вызовов:

```bash
uv run --project packages/ai_advent_agent ai-advent-scenarios memory-layers-demo
```

## Таблица memory layers

| Слой | Что хранит | Файл |
|---|---|---|
| Short-term | Последние реплики и явные short notes | `short_term_memory.json` |
| Working | Текущая задача, ограничения и checklist | `working_memory.json` |
| Long-term | Профиль, предпочтения, решения и знания | `long_term_memory.json` |
| Memory events | Журнал явных операций remember/forget/reset | `memory_events.jsonl` |

## Примеры данных

- Long-term: язык `русский`, стиль `кратко и технически`.
- Working: задача, отдельные файлы памяти, checklist по reports.
- Short-term: последние реплики о демонстрации разделения файлов памяти.

## Prompt assembly

Сборка prompt в варианте `all_layers`:

1. system prompt;
2. long-term memory;
3. working memory;
4. short-term memory;
5. текущее сообщение пользователя.

Файлы prompt сохранены в `{output_dir}`:

- `prompt_no_memory.json`
- `prompt_working_memory.json`
- `prompt_all_memory_layers.json`

## Сравнение поведения

| Вариант | Prompt tokens | Projected tokens | Иллюстрируемое поведение |
|---|---:|---:|---|
{table_rows}

## Как слои влияют на ответ

- Без memory layers агент отвечает обобщённо.
- С working memory агент учитывает текущую задачу и ограничения.
- Со всеми слоями агент учитывает профиль, задачу и последние уточнения.

## Артефакты

- `artifacts/agent-context/short_term_memory.json`
- `artifacts/agent-context/working_memory.json`
- `artifacts/agent-context/long_term_memory.json`
- `artifacts/agent-context/memory_events.jsonl`
- `artifacts/agent-context/token_reports.jsonl`

## Выводы

Memory layers делают stateful-поведение наблюдаемым: разные типы данных физически разделены,
сохраняются только явными командами и отдельно участвуют в prompt assembly. Это снижает риск
memory pollution и позволяет объяснить, почему ответ агента изменился.
"""


def write_messages(path: Path, messages: list[Message]) -> None:
    payload = {"message_count": len(messages), "messages": messages}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def default_context_artifacts_dir() -> Path:
    cwd = Path.cwd()
    if cwd.name == "snapshot":
        return Path("../artifacts/agent-context")
    return Path("artifacts/agent-context")


def default_day11_context_artifacts_dir() -> Path:
    cwd = Path.cwd()
    if cwd.name == "snapshot":
        return Path("../artifacts/agent-context")
    day_dir = Path("weeks/week-03/day-11-memory-layers")
    if day_dir.exists():
        return day_dir / "artifacts/agent-context"
    return Path("artifacts/agent-context")


def default_day11_results_file() -> Path:
    cwd = Path.cwd()
    if cwd.name == "snapshot":
        return Path("../results/day-11-memory-layers.md")
    day_dir = Path("weeks/week-03/day-11-memory-layers")
    if day_dir.exists():
        return day_dir / "results/day-11-memory-layers.md"
    return Path("results/day-11-memory-layers.md")


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
    elif args.scenario == "context-strategies-comparison":
        scenario_context_strategies_comparison(
            recent_messages_limit=args.recent_messages_limit,
            context_window=args.context_window_tokens,
            max_tokens=args.max_tokens,
            output_dir=args.output_dir or default_context_artifacts_dir(),
        )
    elif args.scenario == "memory-layers-demo":
        scenario_memory_layers_demo(
            output_dir=args.output_dir or default_day11_context_artifacts_dir(),
            results_file=args.results_file or default_day11_results_file(),
            context_window=args.context_window_tokens,
            max_tokens=args.max_tokens,
        )
    else:
        raise SystemExit(f"Unknown scenario: {args.scenario}")


if __name__ == "__main__":
    main()
