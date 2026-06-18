"""Handlers for /task state machine commands."""

from __future__ import annotations

from ai_advent_agent.task_state import (
    VALID_TASK_STAGES,
    TaskState,
    parse_task_metadata_argument,
)

from .core import CommandContext, CommandResult, CommandSpec, CommandSuggestion
from .help import print_group_usage


def command_specs() -> list[CommandSpec]:
    stage_suggestions = tuple(
        CommandSuggestion(stage, stage, "Этап task state machine.") for stage in VALID_TASK_STAGES
    )
    return [
        CommandSpec(("task",), "/task", "Task state machine.", handle_task, order=68),
        CommandSpec(
            ("task", "status"),
            "/task status",
            "Показать task state.",
            handle_task_status,
            order=10,
        ),
        CommandSpec(
            ("task", "start"),
            "/task start <title>",
            "Создать задачу на этапе planning.",
            handle_task_start,
            order=20,
        ),
        CommandSpec(
            ("task", "stage"),
            "/task stage <planning|execution|validation|done>",
            "Явно задать этап задачи.",
            handle_task_stage,
            order=30,
            argument_suggestions=stage_suggestions,
        ),
        CommandSpec(
            ("task", "step"),
            "/task step <text>",
            "Задать текущий шаг задачи.",
            handle_task_step,
            order=40,
        ),
        CommandSpec(
            ("task", "expected-action"),
            "/task expected-action <text>",
            "Задать ожидаемое действие.",
            handle_task_expected_action,
            order=50,
        ),
        CommandSpec(
            ("task", "next"),
            "/task next",
            "Перейти к следующему этапу.",
            handle_task_next,
            order=60,
        ),
        CommandSpec(
            ("task", "pause"),
            "/task pause",
            "Поставить задачу на паузу без смены stage.",
            handle_task_pause,
            order=70,
        ),
        CommandSpec(
            ("task", "resume"),
            "/task resume",
            "Продолжить задачу с текущего stage.",
            handle_task_resume,
            order=80,
        ),
        CommandSpec(
            ("task", "complete"),
            "/task complete",
            "Завершить задачу.",
            handle_task_complete,
            order=90,
        ),
        CommandSpec(
            ("task", "reset"),
            "/task reset",
            "Очистить task state.",
            handle_task_reset,
            order=100,
            argument_suggestions=(CommandSuggestion("--yes", "--yes", "Подтвердить reset."),),
        ),
        CommandSpec(
            ("task", "metadata"),
            "/task metadata <key>: <value>",
            "Сохранить metadata задачи.",
            handle_task_metadata,
            order=110,
        ),
    ]


def handle_task(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        if context.registry is not None:
            print_group_usage(context.registry, ("task",))
        else:
            print("Использование: /task\n")
        return CommandResult()
    print_task_state(context.agent.task_state)
    return CommandResult()


def handle_task_status(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /task status\n")
        return CommandResult()
    print_task_state(context.agent.task_state)
    return CommandResult()


def handle_task_start(context: CommandContext, argument: str) -> CommandResult:
    title = argument.strip()
    if not title:
        print("Использование: /task start <title>\n")
        return CommandResult()
    context.agent.start_task(title)
    print("Задача создана: planning\n")
    return CommandResult()


def handle_task_stage(context: CommandContext, argument: str) -> CommandResult:
    stage = argument.strip()
    if not stage:
        print("Использование: /task stage <planning|execution|validation|done>\n")
        return CommandResult()
    context.agent.set_task_stage(stage)
    print(f"Task stage: {context.agent.task_state.stage}\n")
    return CommandResult()


def handle_task_step(context: CommandContext, argument: str) -> CommandResult:
    if not argument.strip():
        print("Использование: /task step <text>\n")
        return CommandResult()
    context.agent.set_task_step(argument)
    print("Текущий шаг обновлён.\n")
    return CommandResult()


def handle_task_expected_action(context: CommandContext, argument: str) -> CommandResult:
    if not argument.strip():
        print("Использование: /task expected-action <text>\n")
        return CommandResult()
    context.agent.set_task_expected_action(argument)
    print("Ожидаемое действие обновлено.\n")
    return CommandResult()


def handle_task_next(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /task next\n")
        return CommandResult()
    context.agent.advance_task()
    print(f"Task stage: {context.agent.task_state.stage}\n")
    return CommandResult()


def handle_task_pause(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /task pause\n")
        return CommandResult()
    before = context.agent.task_state.stage
    context.agent.pause_task()
    print(f"Задача на паузе. Stage сохранён: {before}\n")
    return CommandResult()


def handle_task_resume(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /task resume\n")
        return CommandResult()
    context.agent.resume_task()
    print(f"Задача продолжена. Stage: {context.agent.task_state.stage}\n")
    return CommandResult()


def handle_task_complete(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /task complete\n")
        return CommandResult()
    context.agent.complete_task()
    print("Задача завершена: done\n")
    return CommandResult()


def handle_task_reset(context: CommandContext, argument: str) -> CommandResult:
    if argument.strip() != "--yes":
        print("Для очистки task state используйте: /task reset --yes\n")
        return CommandResult()
    context.agent.reset_task()
    print("Task state очищен.\n")
    return CommandResult()


def handle_task_metadata(context: CommandContext, argument: str) -> CommandResult:
    if not argument.strip():
        print("Использование: /task metadata <key>: <value>\n")
        return CommandResult()
    key, value = parse_task_metadata_argument(argument)
    context.agent.set_task_metadata(key, value)
    print(f"Task metadata сохранена: {key}\n")
    return CommandResult()


def print_task_state(state: TaskState) -> None:
    if not state.active:
        print("Task state пустой: активной задачи нет.\n")
        return
    print("Task state:")
    print(f"  stage: {state.stage or '-'}")
    print(f"  title: {state.title or '-'}")
    print(f"  current_step: {state.current_step or '-'}")
    print(f"  expected_action: {state.expected_action or '-'}")
    print(f"  done: {state.done}")
    print(f"  paused: {state.paused}")
    if state.metadata:
        print("  metadata:")
        for key, value in sorted(state.metadata.items()):
            print(f"    {key}: {value}")
    else:
        print("  metadata: -")
    print()
