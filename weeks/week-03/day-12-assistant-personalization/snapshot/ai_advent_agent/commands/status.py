"""Handlers for /status commands."""

from __future__ import annotations

from .context import (
    print_config,
    print_history_full,
    print_history_summary,
    print_token_breakdown,
    print_token_report,
)
from .core import CommandContext, CommandResult, CommandSpec
from .help import print_group_usage


def command_specs() -> list[CommandSpec]:
    return [
        CommandSpec(
            ("status",),
            "/status",
            "Краткая диагностика состояния.",
            handle_status,
            order=20,
        ),
        CommandSpec(
            ("status", "config"),
            "/status config",
            "Показать настройки.",
            handle_config,
            order=10,
        ),
        CommandSpec(
            ("status", "context"),
            "/status context",
            "Показать контекстные файлы.",
            handle_context_status,
            order=20,
        ),
        CommandSpec(
            ("status", "tokens"),
            "/status tokens",
            "Показать token breakdown.",
            handle_tokens,
            order=30,
        ),
        CommandSpec(
            ("status", "report"),
            "/status report",
            "Показать последний token report.",
            handle_last_report,
            order=40,
        ),
        CommandSpec(
            ("status", "history"),
            "/status history",
            "Показать сводку history.",
            handle_history,
            order=50,
        ),
        CommandSpec(
            ("status", "history", "full"),
            "/status history full",
            "Показать полную history.",
            handle_history_full,
            order=60,
        ),
    ]


def handle_status(context: CommandContext, argument: str) -> CommandResult:
    if argument.strip():
        if context.registry is not None:
            print_group_usage(context.registry, ("status",))
        else:
            print("Использование: /status\n")
        return CommandResult()
    agent = context.agent
    print("Status:")
    print(f"  messages: {len(agent.get_history())}")
    print(f"  strategy: {agent.config.strategy}")
    print(f"  overflow_policy: {agent.config.overflow_policy.value}")
    print(f"  context_strategy: {agent.config.context_strategy}")
    print(f"  summary_mode: {agent.config.summary_mode}")
    print(f"  active_branch: {agent.branch_memory.active_branch}")
    print(f"  active_profile: {agent.user_profiles.active_profile or '-'}")
    memory_layers_active = (
        agent.short_term_memory.active
        or agent.working_memory.active
        or agent.long_term_memory.active
    )
    print(f"  memory_layers_active: {memory_layers_active}")
    print()
    return CommandResult()


def handle_config(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        if context.registry is not None:
            print_group_usage(context.registry, ("config",))
        else:
            print("Использование: /config show\n")
        return CommandResult()
    print_config(context.agent)
    return CommandResult()


def handle_context_status(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /status context\n")
        return CommandResult()
    agent = context.agent
    print(f"Файл контекста: {agent.context_path or 'сохранение отключено'}")
    print(f"Context strategy: {agent.config.context_strategy}")
    print(f"Recent messages limit: {agent.config.recent_messages_limit}")
    print(f"Файл facts: {agent.facts_path or 'сохранение отключено'}")
    print(f"Файл branches: {agent.branches_path or 'сохранение отключено'}")
    print(f"Active branch: {agent.branch_memory.active_branch}")
    print(f"Файл summary: {agent.summary_path or 'сохранение отключено'}")
    print(f"Summary mode: {agent.config.summary_mode}")
    print(f"Summary active: {agent.summary_memory.active}")
    print(f"Summarized messages: {agent.summary_memory.summarized_message_count}")
    print(f"Файл short-term memory: {agent.short_term_memory_path or 'сохранение отключено'}")
    print(f"Файл working memory: {agent.working_memory_path or 'сохранение отключено'}")
    print(f"Файл long-term memory: {agent.long_term_memory_path or 'сохранение отключено'}")
    print(f"Файл memory events: {agent.memory_events_path or 'логирование отключено'}")
    print(f"Файл user profiles: {agent.user_profiles_path or 'сохранение отключено'}")
    print(f"Файл profile events: {agent.profile_events_path or 'логирование отключено'}")
    print(f"Файл token reports: {agent.token_report_path or 'логирование отключено'}\n")
    return CommandResult()


def handle_tokens(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /status tokens\n")
        return CommandResult()
    print_token_breakdown(context.agent)
    return CommandResult()


def handle_last_report(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /status report\n")
        return CommandResult()
    if context.agent.last_token_report is None:
        print("За текущий запуск ещё нет token report.\n")
    else:
        print_token_report(context.agent.last_token_report)
        print()
    return CommandResult()


def handle_history(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /status history или /status history full\n")
        return CommandResult()
    print_history_summary(context.agent.get_history())
    return CommandResult()


def handle_history_full(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /status history full\n")
        return CommandResult()
    print_history_full(context.agent.get_history())
    return CommandResult()
