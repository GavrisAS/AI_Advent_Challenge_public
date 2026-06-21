"""Handlers for /config commands."""

from __future__ import annotations

from typing import cast

from ai_advent_agent.config import AgentStrategy, SummaryMode, parse_overflow_policy

from .core import CommandContext, CommandResult, CommandSpec, CommandSuggestion
from .status import handle_config


def command_specs() -> list[CommandSpec]:
    return [
        CommandSpec(
            ("config", "show"),
            "/config show",
            "Показать текущую конфигурацию.",
            handle_config,
            order=10,
        ),
        CommandSpec(
            ("config", "strategy"),
            "/config strategy direct|step_by_step",
            "Изменить response strategy.",
            handle_config_strategy,
            order=20,
            argument_suggestions=(
                CommandSuggestion("direct", "direct", "Быстрый прямой ответ."),
                CommandSuggestion(
                    "step_by_step",
                    "step_by_step",
                    "Пошаговое рассуждение.",
                ),
            ),
        ),
        CommandSpec(
            ("config", "summary"),
            "/config summary off|llm",
            "Изменить summary mode.",
            handle_config_summary,
            order=30,
            argument_suggestions=(
                CommandSuggestion("off", "off", "Не использовать summary memory."),
                CommandSuggestion("llm", "llm", "Использовать LLM summary memory."),
            ),
        ),
        CommandSpec(
            ("config", "overflow"),
            "/config overflow error|no_trim|sliding_window",
            "Изменить overflow policy.",
            handle_config_overflow,
            order=40,
            argument_suggestions=(
                CommandSuggestion("error", "error", "Ошибка при переполнении контекста."),
                CommandSuggestion("no_trim", "no_trim", "Не обрезать контекст."),
                CommandSuggestion(
                    "sliding_window",
                    "sliding_window",
                    "Использовать sliding window при переполнении.",
                ),
            ),
        ),
    ]


def handle_config_strategy(context: CommandContext, argument: str) -> CommandResult:
    value = argument.strip().lower()
    if value not in {"direct", "step_by_step"}:
        print("Использование: /config strategy direct или /config strategy step_by_step\n")
        return CommandResult()
    context.agent.set_strategy(cast(AgentStrategy, value))
    print(f"Стратегия изменена: {context.agent.config.strategy}\n")
    return CommandResult()


def handle_config_summary(context: CommandContext, argument: str) -> CommandResult:
    value = argument.strip().lower()
    if value not in {"off", "llm"}:
        print("Использование: /config summary off|llm\n")
        return CommandResult()
    context.agent.set_summary_mode(cast(SummaryMode, value))
    print(f"Summary mode изменён: {context.agent.config.summary_mode}\n")
    return CommandResult()


def handle_config_overflow(context: CommandContext, argument: str) -> CommandResult:
    value = argument.strip().lower()
    if not value:
        print("Использование: /config overflow error|no_trim|sliding_window\n")
        return CommandResult()
    context.agent.set_overflow_policy(parse_overflow_policy(value))
    print(f"Context overflow policy изменена: {context.agent.config.overflow_policy.value}\n")
    return CommandResult()
