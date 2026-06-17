"""Factories for command registry and completer."""

from __future__ import annotations

from . import branch, config, file, help, memory, session, status, storage
from .completer import CommandCompleter
from .legacy import LEGACY_ALIASES
from .registry import CommandRegistry


def build_command_registry() -> CommandRegistry:
    registry = CommandRegistry()
    for name, description in [
        ("help", "Справка по slash-командам."),
        ("status", "Диагностика текущего состояния агента."),
        ("config", "Изменение runtime-настроек."),
        ("session", "Управление текущей сессией."),
        ("storage", "Очистка runtime-файлов."),
        ("memory", "Memory layers, summary и sticky facts."),
        ("branch", "Checkpoints и branches."),
        ("file", "Анализ файла и отправка файла в модель."),
        ("exit", "Выйти из интерактивного режима."),
    ]:
        registry.register_group(name, description)

    for module in [
        help,
        status,
        config,
        session,
        storage,
        memory,
        branch,
        file,
    ]:
        for spec in module.command_specs():
            registry.register(spec)

    for old, new in LEGACY_ALIASES:
        registry.add_alias(old, new, legacy=True)
    return registry


def build_command_completer(registry: CommandRegistry) -> CommandCompleter:
    return CommandCompleter(registry)
