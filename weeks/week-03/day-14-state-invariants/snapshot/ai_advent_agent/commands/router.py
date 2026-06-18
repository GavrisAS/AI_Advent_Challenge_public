"""Slash-command routing and dispatch."""

from __future__ import annotations

import sys

from ai_advent_agent.storage import ContextStorageError

from .core import CommandAlias, CommandContext, CommandResult
from .help import print_group_usage
from .registry import CommandRegistry


class CommandRouter:
    """Routes raw slash-command input to a registered handler."""

    def __init__(self, registry: CommandRegistry) -> None:
        self.registry = registry

    def route(
        self,
        raw_command: str,
        context: CommandContext,
    ) -> CommandResult:
        normalized = raw_command.strip()
        if not normalized.startswith("/"):
            return CommandResult(handled=False)
        tokens = normalized[1:].split()
        if not tokens:
            return CommandResult(handled=False)

        lowered_tokens = tuple(token.lower() for token in tokens)
        alias, alias_target, alias_rest = self._resolve_alias(lowered_tokens)
        if alias is not None:
            target_tokens = (*alias_target, *alias_rest)
            if alias.legacy:
                print(f"Deprecated command. Use /{' '.join(target_tokens)} instead.")
            command_path, rest_tokens = self._match_path(target_tokens)
        else:
            command_path, rest_tokens = self._match_path(lowered_tokens)

        spec = self.registry.find(command_path)
        if spec is None:
            return CommandResult(handled=False)
        if spec.handler is None:
            print_group_usage(self.registry, spec.path)
            return CommandResult()

        context.registry = self.registry
        argument = _argument_after_path(normalized, len(tokens) - len(rest_tokens))
        if alias is not None:
            argument = " ".join(tokens[len(tokens) - len(alias_rest) :])
        try:
            return spec.handler(context, argument)
        except ContextStorageError as error:
            print(f"Ошибка контекста: {error}\n", file=sys.stderr)
            return CommandResult()
        except (OSError, UnicodeDecodeError) as error:
            print(f"Ошибка файла: {error}\n", file=sys.stderr)
            return CommandResult()
        except ValueError as error:
            print(f"Ошибка команды: {error}\n", file=sys.stderr)
            return CommandResult()

    def _resolve_alias(
        self,
        tokens: tuple[str, ...],
    ) -> tuple[CommandAlias | None, tuple[str, ...], tuple[str, ...]]:
        if (
            len(tokens) > 1
            and tokens[0] == "branch"
            and tokens[1]
            not in {
                "list",
                "checkpoint",
                "create",
                "switch",
            }
        ):
            return CommandAlias(("branch",), ("branch", "create")), ("branch", "create"), tokens[1:]
        return self.registry.resolve_alias(tokens)

    def _match_path(self, tokens: tuple[str, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
        for size in range(len(tokens), 0, -1):
            path = tokens[:size]
            if self.registry.find(path) is not None:
                return path, tokens[size:]
        return tokens, ()


def _argument_after_path(command: str, path_size: int) -> str:
    body = command.strip()[1:]
    parts = body.split(maxsplit=path_size)
    if len(parts) <= path_size:
        return ""
    return parts[path_size].strip()
