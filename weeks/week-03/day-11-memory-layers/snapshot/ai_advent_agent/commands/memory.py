"""Handlers for /memory commands."""

from __future__ import annotations

from ai_advent_agent.memory_layers import parse_key_value_argument

from .context import print_memory_layer, print_memory_summary
from .core import CommandContext, CommandResult, CommandSpec, CommandSuggestion
from .help import print_group_usage


def command_specs() -> list[CommandSpec]:
    return [
        CommandSpec(
            ("memory",),
            "/memory",
            "Показать сводку memory subsystem.",
            handle_memory,
            order=60,
        ),
        CommandSpec(
            ("memory", "short"),
            "/memory short",
            "Показать short-term memory.",
            handle_memory_short,
            order=10,
        ),
        CommandSpec(
            ("memory", "working"),
            "/memory working",
            "Показать working memory.",
            handle_memory_working,
            order=20,
        ),
        CommandSpec(
            ("memory", "long"),
            "/memory long",
            "Показать long-term memory.",
            handle_memory_long,
            order=30,
        ),
        CommandSpec(
            ("memory", "summary"),
            "/memory summary",
            "Показать summary memory.",
            handle_memory_summary_command,
            order=40,
        ),
        CommandSpec(
            ("memory", "facts"),
            "/memory facts",
            "Показать sticky facts.",
            handle_memory_facts,
            order=50,
        ),
        CommandSpec(
            ("memory", "add"),
            "/memory add",
            "Добавить данные в memory layer.",
            order=60,
            argument_suggestions=(
                CommandSuggestion("short ", "short", "Добавить short-term note."),
            ),
        ),
        CommandSpec(
            ("memory", "add", "short"),
            "/memory add short <text>",
            "Добавить short-term note.",
            handle_memory_add_short,
            order=60,
        ),
        CommandSpec(
            ("memory", "set"),
            "/memory set",
            "Сохранить key-value в memory layer.",
            order=70,
            argument_suggestions=(
                CommandSuggestion("working ", "working", "Сохранить key-value в working memory."),
                CommandSuggestion("long ", "long", "Сохранить key-value в long-term memory."),
            ),
        ),
        CommandSpec(
            ("memory", "set", "working"),
            "/memory set working <key>: <value>",
            "Записать working memory.",
            handle_memory_set_working,
            order=70,
        ),
        CommandSpec(
            ("memory", "set", "long"),
            "/memory set long <key>: <value>",
            "Записать long-term memory.",
            handle_memory_set_long,
            order=80,
        ),
        CommandSpec(
            ("memory", "forget"),
            "/memory forget",
            "Удалить key из memory layer.",
            order=90,
            argument_suggestions=(
                CommandSuggestion("working ", "working", "Удалить key из working memory."),
                CommandSuggestion("long ", "long", "Удалить key из long-term memory."),
            ),
        ),
        CommandSpec(
            ("memory", "forget", "working"),
            "/memory forget working <key>",
            "Удалить working memory entry.",
            handle_memory_forget_working,
            order=90,
        ),
        CommandSpec(
            ("memory", "forget", "long"),
            "/memory forget long <key>",
            "Удалить long-term memory entry.",
            handle_memory_forget_long,
            order=100,
        ),
        CommandSpec(
            ("memory", "reset"),
            "/memory reset",
            "Очистить memory layer.",
            order=110,
            argument_suggestions=(
                CommandSuggestion("working", "working", "Очистить working memory."),
                CommandSuggestion("all --yes", "all --yes", "Очистить все memory layers."),
            ),
        ),
        CommandSpec(
            ("memory", "reset", "working"),
            "/memory reset working",
            "Очистить working memory.",
            handle_memory_reset_working,
            order=110,
        ),
        CommandSpec(
            ("memory", "reset", "all"),
            "/memory reset all --yes",
            "Очистить все memory layers.",
            handle_memory_reset_all,
            order=120,
        ),
    ]


def handle_memory(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        if context.registry is not None:
            print_group_usage(context.registry, ("memory",))
        else:
            print("Использование: /memory\n")
        return CommandResult()
    print_memory_summary(context.agent)
    return CommandResult()


def handle_memory_short(context: CommandContext, argument: str = "") -> CommandResult:
    return _memory_layer_command(context, argument, "short")


def handle_memory_working(context: CommandContext, argument: str = "") -> CommandResult:
    return _memory_layer_command(context, argument, "working")


def handle_memory_long(context: CommandContext, argument: str = "") -> CommandResult:
    return _memory_layer_command(context, argument, "long")


def _memory_layer_command(context: CommandContext, argument: str, layer: str) -> CommandResult:
    if argument.strip():
        print(f"Использование: /memory {layer}\n")
        return CommandResult()
    print_memory_layer(context.agent, layer)
    return CommandResult()


def handle_memory_summary_command(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip() == "clear":
        context.agent.summary_memory.summary = ""
        context.agent.summary_memory.summarized_message_count = 0
        context.agent.summary_memory.updated_at = ""
        context.agent.save_summary()
        print("Summary memory очищена.\n")
        return CommandResult()
    if argument.strip():
        print("Использование: /memory summary\n")
        return CommandResult()
    if not context.agent.summary_memory.active:
        print("Summary memory пустая.\n")
    else:
        print(
            "Summary memory:\n"
            f"{context.agent.summary_memory.summary}\n\n"
            f"Сжато сообщений: {context.agent.summary_memory.summarized_message_count}\n"
        )
    return CommandResult()


def handle_memory_facts(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /memory facts\n")
        return CommandResult()
    facts = context.agent.facts_memory.normalized()
    if not context.agent.facts_memory.active:
        print("Sticky facts пустые.\n")
    else:
        print("Sticky facts:")
        for key, value in facts.items():
            if value.strip():
                print(f"  {key}: {value}")
        print()
    return CommandResult()


def handle_memory_add_short(context: CommandContext, argument: str) -> CommandResult:
    if not argument.strip():
        print("Использование: /memory add short <text>\n")
        return CommandResult()
    context.agent.remember_short(argument.strip())
    print("Сохранено в short-term memory.\n")
    return CommandResult()


def handle_memory_set_working(context: CommandContext, argument: str) -> CommandResult:
    if not argument.strip():
        print("Использование: /memory set working <key>: <value>\n")
        return CommandResult()
    key, value = parse_key_value_argument(argument)
    context.agent.remember_working(key, value)
    print(f"Сохранено в working memory: {key}\n")
    return CommandResult()


def handle_memory_set_long(context: CommandContext, argument: str) -> CommandResult:
    if not argument.strip():
        print("Использование: /memory set long <key>: <value>\n")
        return CommandResult()
    key, value = parse_key_value_argument(argument)
    context.agent.remember_long(key, value)
    print(f"Сохранено в long-term memory: {key}\n")
    return CommandResult()


def handle_memory_forget_working(context: CommandContext, argument: str) -> CommandResult:
    key = argument.strip()
    if not key:
        print("Использование: /memory forget working <key>\n")
        return CommandResult()
    removed = context.agent.forget_working(key)
    print(("Удалено" if removed else "Ключ не найден") + f" в working memory: {key}\n")
    return CommandResult()


def handle_memory_forget_long(context: CommandContext, argument: str) -> CommandResult:
    key = argument.strip()
    if not key:
        print("Использование: /memory forget long <key>\n")
        return CommandResult()
    removed = context.agent.forget_long(key)
    print(("Удалено" if removed else "Ключ не найден") + f" в long-term memory: {key}\n")
    return CommandResult()


def handle_memory_reset_working(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /memory reset working\n")
        return CommandResult()
    context.agent.reset_working_memory()
    print("Working memory очищена.\n")
    return CommandResult()


def handle_memory_reset_all(context: CommandContext, argument: str) -> CommandResult:
    if argument.strip() != "--yes":
        print("Для очистки всех memory layers используйте: /memory reset all --yes\n")
        return CommandResult()
    context.agent.reset_all_memory_layers()
    print("Все memory layers очищены.\n")
    return CommandResult()
