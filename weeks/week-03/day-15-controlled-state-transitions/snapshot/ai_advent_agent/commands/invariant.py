"""Handlers for /invariant hard constraint commands."""

from __future__ import annotations

from ai_advent_agent.invariants import (
    VALID_INVARIANT_CATEGORIES,
    Invariant,
    parse_invariant_add_argument,
    parse_invariant_id_text_argument,
)

from .core import CommandContext, CommandResult, CommandSpec, CommandSuggestion
from .help import print_group_usage


def command_specs() -> list[CommandSpec]:
    category_suggestions = tuple(
        CommandSuggestion(
            f"{category}: ",
            f"{category}: ",
            "Категория invariant.",
        )
        for category in VALID_INVARIANT_CATEGORIES
    )
    id_provider = invariant_id_suggestions
    return [
        CommandSpec(
            ("invariant",),
            "/invariant",
            "Hard state invariants.",
            handle_invariant,
            order=69,
        ),
        CommandSpec(
            ("invariant", "list"),
            "/invariant list",
            "Показать список invariants.",
            handle_invariant_list,
            order=10,
        ),
        CommandSpec(
            ("invariant", "show"),
            "/invariant show <id>",
            "Показать invariant по id.",
            handle_invariant_show,
            order=20,
            argument_provider=id_provider,
        ),
        CommandSpec(
            ("invariant", "add"),
            "/invariant add <category>: <text>",
            "Добавить hard invariant.",
            handle_invariant_add,
            order=30,
            argument_suggestions=category_suggestions,
        ),
        CommandSpec(
            ("invariant", "rationale"),
            "/invariant rationale <id>: <text>",
            "Добавить rationale к invariant.",
            handle_invariant_rationale,
            order=40,
            argument_provider=id_colon_suggestions,
        ),
        CommandSpec(
            ("invariant", "pattern"),
            "/invariant pattern <id>: <pattern>",
            "Добавить reject pattern.",
            handle_invariant_pattern,
            order=50,
            argument_provider=id_colon_suggestions,
        ),
        CommandSpec(
            ("invariant", "check"),
            "/invariant check <text>",
            "Проверить текст на конфликт без API.",
            handle_invariant_check,
            order=60,
        ),
        CommandSpec(
            ("invariant", "enable"),
            "/invariant enable <id>",
            "Включить invariant.",
            handle_invariant_enable,
            order=70,
            argument_provider=id_provider,
        ),
        CommandSpec(
            ("invariant", "disable"),
            "/invariant disable <id>",
            "Отключить invariant.",
            handle_invariant_disable,
            order=80,
            argument_provider=id_provider,
        ),
        CommandSpec(
            ("invariant", "remove"),
            "/invariant remove <id>",
            "Удалить invariant.",
            handle_invariant_remove,
            order=90,
            argument_provider=id_provider,
        ),
        CommandSpec(
            ("invariant", "reset"),
            "/invariant reset",
            "Очистить все invariants.",
            handle_invariant_reset,
            order=100,
            argument_suggestions=(CommandSuggestion("--yes", "--yes", "Подтвердить reset."),),
        ),
    ]


def invariant_id_suggestions(
    context: CommandContext | None,
    prefix: str,
) -> list[CommandSuggestion]:
    if context is None:
        return []
    suggestions = []
    for invariant in context.agent.invariants.all():
        if prefix and not invariant.id.lower().startswith(prefix.lower()):
            continue
        suggestions.append(
            CommandSuggestion(
                invariant.id,
                invariant.id,
                f"{invariant.category}: {invariant.text[:48]}",
            )
        )
    return suggestions


def id_colon_suggestions(
    context: CommandContext | None,
    prefix: str,
) -> list[CommandSuggestion]:
    return [
        CommandSuggestion(
            f"{suggestion.insert_text}: ",
            f"{suggestion.display_text}:",
            suggestion.description,
        )
        for suggestion in invariant_id_suggestions(context, prefix)
    ]


def handle_invariant(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        if context.registry is not None:
            print_group_usage(context.registry, ("invariant",))
        else:
            print("Использование: /invariant\n")
        return CommandResult()
    print_invariant_list(context.agent.invariants.all())
    return CommandResult()


def handle_invariant_list(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /invariant list\n")
        return CommandResult()
    print_invariant_list(context.agent.invariants.all())
    return CommandResult()


def handle_invariant_show(context: CommandContext, argument: str) -> CommandResult:
    invariant_id = argument.strip()
    if not invariant_id:
        print("Использование: /invariant show <id>\n")
        return CommandResult()
    print_invariant(context.agent.invariants.require(invariant_id))
    return CommandResult()


def handle_invariant_add(context: CommandContext, argument: str) -> CommandResult:
    if not argument.strip():
        print("Использование: /invariant add <category>: <text>\n")
        return CommandResult()
    category, text = parse_invariant_add_argument(argument)
    invariant = context.agent.add_invariant(category, text)
    print(f"Invariant добавлен: {invariant.id}\n")
    return CommandResult()


def handle_invariant_rationale(context: CommandContext, argument: str) -> CommandResult:
    if not argument.strip():
        print("Использование: /invariant rationale <id>: <text>\n")
        return CommandResult()
    invariant_id, text = parse_invariant_id_text_argument(argument)
    context.agent.set_invariant_rationale(invariant_id, text)
    print(f"Rationale обновлён: {invariant_id}\n")
    return CommandResult()


def handle_invariant_pattern(context: CommandContext, argument: str) -> CommandResult:
    if not argument.strip():
        print("Использование: /invariant pattern <id>: <pattern>\n")
        return CommandResult()
    invariant_id, pattern = parse_invariant_id_text_argument(argument)
    context.agent.add_invariant_pattern(invariant_id, pattern)
    print(f"Reject pattern добавлен: {invariant_id}\n")
    return CommandResult()


def handle_invariant_check(context: CommandContext, argument: str) -> CommandResult:
    text = argument.strip()
    if not text:
        print("Использование: /invariant check <text>\n")
        return CommandResult()
    conflicts = context.agent.check_invariant_conflicts(text)
    if not conflicts:
        print("Конфликтов с active invariants не найдено.\n")
        return CommandResult()
    print("Найдены конфликты:")
    for conflict in conflicts:
        print(
            f"  {conflict.invariant_id} [{conflict.category}] "
            f"pattern={conflict.matched_pattern}: {conflict.invariant_text}"
        )
    print()
    return CommandResult()


def handle_invariant_enable(context: CommandContext, argument: str) -> CommandResult:
    invariant_id = argument.strip()
    if not invariant_id:
        print("Использование: /invariant enable <id>\n")
        return CommandResult()
    context.agent.enable_invariant(invariant_id)
    print(f"Invariant включён: {invariant_id}\n")
    return CommandResult()


def handle_invariant_disable(context: CommandContext, argument: str) -> CommandResult:
    invariant_id = argument.strip()
    if not invariant_id:
        print("Использование: /invariant disable <id>\n")
        return CommandResult()
    context.agent.disable_invariant(invariant_id)
    print(f"Invariant отключён: {invariant_id}\n")
    return CommandResult()


def handle_invariant_remove(context: CommandContext, argument: str) -> CommandResult:
    invariant_id = argument.strip()
    if not invariant_id:
        print("Использование: /invariant remove <id>\n")
        return CommandResult()
    context.agent.remove_invariant(invariant_id)
    print(f"Invariant удалён: {invariant_id}\n")
    return CommandResult()


def handle_invariant_reset(context: CommandContext, argument: str) -> CommandResult:
    if argument.strip() != "--yes":
        print("Для очистки invariants используйте: /invariant reset --yes\n")
        return CommandResult()
    context.agent.reset_invariants()
    print("Invariants очищены.\n")
    return CommandResult()


def print_invariant_list(invariants: list[Invariant]) -> None:
    if not invariants:
        print("Invariants не заданы.\n")
        return
    print("Invariants:")
    for invariant in invariants:
        status = "enabled" if invariant.enabled else "disabled"
        pattern_count = len(invariant.reject_patterns)
        print(f"  {invariant.id} [{invariant.category}] {status}, patterns={pattern_count}")
        print(f"    {invariant.text}")
    print()


def print_invariant(invariant: Invariant) -> None:
    print(f"Invariant: {invariant.id}")
    print(f"  category: {invariant.category}")
    print(f"  enabled: {invariant.enabled}")
    print(f"  text: {invariant.text}")
    print(f"  rationale: {invariant.rationale or '-'}")
    if invariant.reject_patterns:
        print("  reject_patterns:")
        for pattern in invariant.reject_patterns:
            print(f"    - {pattern}")
    else:
        print("  reject_patterns: -")
    print(f"  created_at: {invariant.created_at}")
    print(f"  updated_at: {invariant.updated_at}\n")
