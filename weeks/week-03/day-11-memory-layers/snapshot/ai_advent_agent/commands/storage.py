"""Handlers for /storage commands."""

from __future__ import annotations

from .core import CommandContext, CommandResult, CommandSpec


def command_specs() -> list[CommandSpec]:
    return [
        CommandSpec(
            ("storage", "clear", "context"),
            "/storage clear context",
            "Удалить context/runtime файлы текущего контекста.",
            handle_storage_clear_context,
            order=10,
        ),
        CommandSpec(
            ("storage", "clear", "reports"),
            "/storage clear reports",
            "Удалить token reports.",
            handle_storage_clear_reports,
            order=20,
        ),
        CommandSpec(
            ("storage", "clear", "all"),
            "/storage clear all --yes",
            "Удалить все runtime-файлы агента.",
            handle_storage_clear_all,
            order=30,
        ),
    ]


def handle_storage_clear_context(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /storage clear context\n")
        return CommandResult()
    context.agent.clear_context_file()
    print("Runtime-файлы контекста удалены. Новая сессия начата с system prompt.\n")
    return CommandResult()


def handle_storage_clear_reports(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /storage clear reports\n")
        return CommandResult()
    context.agent.last_token_report = None
    if context.agent.token_report_store is not None:
        context.agent.token_report_store.clear()
    print("Token reports удалены.\n")
    return CommandResult()


def handle_storage_clear_all(context: CommandContext, argument: str) -> CommandResult:
    if argument.strip() != "--yes":
        print("Для удаления всех runtime-файлов используйте: /storage clear all --yes\n")
        return CommandResult()
    agent = context.agent
    agent.clear_context_file()
    agent.short_term_memory.clear()
    agent.working_memory.clear()
    agent.long_term_memory.clear()
    if agent.working_memory_store is not None:
        agent.working_memory_store.clear()
    if agent.long_term_memory_store is not None:
        agent.long_term_memory_store.clear()
    if agent.memory_event_store is not None:
        agent.memory_event_store.clear()
    print("Все runtime-файлы агента удалены.\n")
    return CommandResult()
