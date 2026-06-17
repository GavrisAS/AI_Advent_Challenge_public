"""Handlers for /session and /exit commands."""

from __future__ import annotations

from .core import CommandContext, CommandResult, CommandSpec


def command_specs() -> list[CommandSpec]:
    return [
        CommandSpec(
            ("session", "reset"),
            "/session reset",
            "Начать новую сессию и сохранить system prompt.",
            handle_session_reset,
        ),
        CommandSpec(("exit",), "/exit", "Выйти из интерактивного режима.", handle_exit),
    ]


def handle_session_reset(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /session reset\n")
        return CommandResult()
    context.agent.reset()
    print("Новая сессия начата. В JSON сохранён system prompt, token reports очищены.\n")
    return CommandResult()


def handle_exit(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /exit\n")
        return CommandResult()
    _ = context
    return CommandResult(exit_requested=True)
