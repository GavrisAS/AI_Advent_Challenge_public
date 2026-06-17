"""Handlers for /file commands."""

from __future__ import annotations

from .context import analyze_file, ask_file, extract_path_argument
from .core import CommandContext, CommandResult, CommandSpec


def command_specs() -> list[CommandSpec]:
    return [
        CommandSpec(
            ("file", "analyze"),
            "/file analyze <path>",
            "Dry-run token report для файла.",
            handle_file_analyze,
        ),
        CommandSpec(
            ("file", "ask"), "/file ask <path>", "Отправить файл в модель.", handle_file_ask
        ),
    ]


def handle_file_analyze(context: CommandContext, argument: str) -> CommandResult:
    path = extract_path_argument(argument)
    if path is None:
        print("Использование: /file analyze path/to/skills-all.md\n")
        return CommandResult()
    analyze_file(path, context.agent)
    return CommandResult()


def handle_file_ask(context: CommandContext, argument: str) -> CommandResult:
    path = extract_path_argument(argument)
    if path is None:
        print("Использование: /file ask path/to/skills-all.md\n")
        return CommandResult()
    ask_file(path, context.agent, show_metadata=context.show_metadata)
    return CommandResult()
