"""Factories for command registry and completer."""

from __future__ import annotations

from . import branch, config, file, help, memory, profile, session, status, storage
from .completer import CommandCompleter
from .legacy import LEGACY_ALIASES
from .registry import CommandRegistry


def build_command_registry() -> CommandRegistry:
    registry = CommandRegistry()
    for name, description, order in [
        ("help", "Справка по slash-командам.", 10),
        ("status", "Диагностика текущего состояния агента.", 20),
        ("config", "Изменение runtime-настроек.", 30),
        ("session", "Управление текущей сессией.", 40),
        ("storage", "Очистка runtime-файлов.", 50),
        ("memory", "Memory layers, summary и sticky facts.", 60),
        ("profile", "Assistant personalization profiles.", 65),
        ("branch", "Checkpoints и branches.", 70),
        ("file", "Анализ файла и отправка файла в модель.", 80),
        ("exit", "Выйти из интерактивного режима.", 90),
    ]:
        registry.register_group(name, description, order=order)

    for module in [
        help,
        status,
        config,
        session,
        storage,
        memory,
        profile,
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
