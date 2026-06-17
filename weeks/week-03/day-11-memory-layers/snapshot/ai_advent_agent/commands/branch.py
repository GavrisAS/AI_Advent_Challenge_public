"""Handlers for /branch commands."""

from __future__ import annotations

from .core import CommandContext, CommandResult, CommandSpec


def command_specs() -> list[CommandSpec]:
    return [
        CommandSpec(
            ("branch", "list"),
            "/branch list",
            "Показать branches и checkpoints.",
            handle_branch_list,
            order=10,
        ),
        CommandSpec(
            ("branch", "checkpoint"),
            "/branch checkpoint <name>",
            "Создать checkpoint.",
            handle_branch_checkpoint,
            order=20,
        ),
        CommandSpec(
            ("branch", "create"),
            "/branch create <name>",
            "Создать branch.",
            handle_branch_create,
            order=30,
        ),
        CommandSpec(
            ("branch", "switch"),
            "/branch switch <name>",
            "Переключиться на branch.",
            handle_branch_switch,
            order=40,
        ),
    ]


def handle_branch_list(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /branch list\n")
        return CommandResult()
    agent = context.agent
    print(f"Active branch: {agent.branch_memory.active_branch}")
    print("Branches:")
    if not agent.branch_memory.branches:
        print("  -")
    for name, branch in sorted(agent.branch_memory.branches.items()):
        marker = "*" if name == agent.branch_memory.active_branch else " "
        print(f"  {marker} {name}: messages={len(branch.messages)}")
    print("Checkpoints:")
    if not agent.branch_memory.checkpoints:
        print("  -")
    for name, checkpoint in sorted(agent.branch_memory.checkpoints.items()):
        latest = " latest" if name == agent.branch_memory.latest_checkpoint else ""
        print(f"  {name}: messages={len(checkpoint.messages)}{latest}")
    print()
    return CommandResult()


def handle_branch_checkpoint(context: CommandContext, argument: str) -> CommandResult:
    name = argument.strip()
    if not name:
        print("Использование: /branch checkpoint <name>\n")
        return CommandResult()
    context.agent.create_checkpoint(name)
    print(f"Checkpoint создан: {name}\n")
    return CommandResult()


def handle_branch_create(context: CommandContext, argument: str) -> CommandResult:
    name = argument.strip()
    if not name:
        print("Использование: /branch create <name>\n")
        return CommandResult()
    context.agent.create_branch(name)
    print(f"Ветка создана и активирована: {name}\n")
    return CommandResult()


def handle_branch_switch(context: CommandContext, argument: str) -> CommandResult:
    name = argument.strip()
    if not name:
        print("Использование: /branch switch <name>\n")
        return CommandResult()
    context.agent.switch_branch(name)
    print(f"Активная ветка: {name}\n")
    return CommandResult()
