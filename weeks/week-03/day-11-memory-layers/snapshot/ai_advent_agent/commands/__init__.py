"""Slash-command subsystem public API."""

from __future__ import annotations

from .builders import build_command_completer, build_command_registry
from .completer import (
    CommandCompleter,
    build_command_key_bindings,
    should_open_nested_completion,
)
from .context import (
    analyze_file,
    ask_file,
    extract_path_argument,
    format_number,
    format_optional_number,
    print_config,
    print_history_full,
    print_history_summary,
    print_key_value_memory,
    print_memory_layer,
    print_memory_summary,
    print_metadata,
    print_token_breakdown,
    print_token_report,
)
from .core import (
    CommandAlias,
    CommandContext,
    CommandError,
    CommandGroup,
    CommandHandler,
    CommandResult,
    CommandSpec,
    CommandSuggestion,
)
from .registry import CommandRegistry
from .router import CommandRouter

__all__ = [
    "CommandAlias",
    "CommandCompleter",
    "CommandContext",
    "CommandError",
    "CommandGroup",
    "CommandHandler",
    "CommandRegistry",
    "CommandResult",
    "CommandRouter",
    "CommandSpec",
    "CommandSuggestion",
    "analyze_file",
    "ask_file",
    "build_command_completer",
    "build_command_key_bindings",
    "build_command_registry",
    "extract_path_argument",
    "format_number",
    "format_optional_number",
    "print_config",
    "print_history_full",
    "print_history_summary",
    "print_key_value_memory",
    "print_memory_layer",
    "print_memory_summary",
    "print_metadata",
    "print_token_breakdown",
    "print_token_report",
    "should_open_nested_completion",
]
