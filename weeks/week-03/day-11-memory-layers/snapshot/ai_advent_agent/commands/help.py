"""Handlers and helpers for /help."""

from __future__ import annotations

from .core import CommandContext, CommandResult, CommandSpec
from .registry import CommandRegistry


def command_specs() -> list[CommandSpec]:
    return [CommandSpec(("help",), "/help [group|legacy]", "Показать справку.", handle_help)]


def print_group_usage(registry: CommandRegistry, path: tuple[str, ...]) -> None:
    commands = registry.children_for(path)
    if not commands:
        print(f"Использование: /{' '.join(path)}\n")
        return
    print(f"Команды /{' '.join(path)}:")
    for spec in commands:
        print(f"  {spec.usage:<36} — {spec.description}")
    print()


def handle_help(context: CommandContext, argument: str) -> CommandResult:
    if context.registry is None:
        from .builders import build_command_registry

        registry = build_command_registry()
    else:
        registry = context.registry
    topic = argument.strip().lower()
    if topic == "legacy":
        print("Legacy aliases:")
        for old, new in registry.legacy_help():
            print(f"  {old:<28} -> {new}")
        print()
        return CommandResult()
    if topic:
        specs = registry.group_help(topic)
        if not specs:
            print(f"Нет справки для группы: {topic}\n")
            return CommandResult()
        print(f"Команды /{topic}:")
        for spec in specs:
            if spec.handler is not None:
                print(f"  {spec.usage:<40} — {spec.description}")
        print()
        return CommandResult()

    print("Slash-команды:")
    for spec in registry.top_level():
        print(f"  {spec.usage:<16} — {spec.description}")
    print("\nИспользуйте /help <group> или /help legacy.\n")
    return CommandResult()
