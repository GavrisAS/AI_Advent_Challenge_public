"""Core models for the slash-command subsystem."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_advent_agent.agent import SimpleAgent

    from .registry import CommandRegistry


CommandHandler = Callable[["CommandContext", str], "CommandResult"]


class CommandError(RuntimeError):
    """Raised when a slash-command cannot be parsed or executed."""


@dataclass(slots=True)
class CommandContext:
    """Runtime objects available to command handlers."""

    agent: SimpleAgent
    show_metadata: bool = True
    registry: CommandRegistry | None = None


@dataclass(slots=True)
class CommandResult:
    """Result of routing a command."""

    handled: bool = True
    exit_requested: bool = False


@dataclass(slots=True)
class CommandSpec:
    """A command leaf or group in the slash-command tree."""

    path: tuple[str, ...]
    usage: str
    description: str
    handler: CommandHandler | None = None
    aliases: tuple[tuple[str, ...], ...] = ()
    legacy: bool = False
    children: dict[str, CommandSpec] = field(default_factory=dict)

    @property
    def slash_path(self) -> str:
        return "/" + " ".join(self.path)


@dataclass(slots=True)
class CommandGroup:
    """Help metadata for a top-level command namespace."""

    name: str
    description: str


@dataclass(frozen=True, slots=True)
class CommandAlias:
    source: tuple[str, ...]
    target: tuple[str, ...]
    legacy: bool = True


@dataclass(frozen=True, slots=True)
class CommandSuggestion:
    insert_text: str
    display_text: str
    description: str

    @property
    def text(self) -> str:
        return self.insert_text
