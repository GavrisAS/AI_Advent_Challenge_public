"""prompt_toolkit completion adapter for slash-commands."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from .core import CommandContext, CommandSpec, CommandSuggestion
from .registry import CommandRegistry

if TYPE_CHECKING:
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.document import Document
else:
    try:  # pragma: no cover - exercised through prompt_toolkit when installed.
        from prompt_toolkit.completion import Completer, Completion
        from prompt_toolkit.document import Document
    except ImportError:  # pragma: no cover - fallback is validated through suggest().

        class Completer:  # type: ignore[no-redef]
            pass

        Completion = None  # type: ignore[assignment]
        Document = Any  # type: ignore[misc, assignment]


class CommandCompleter(Completer):  # type: ignore[misc, valid-type]
    """prompt_toolkit adapter backed by CommandRegistry."""

    def __init__(self, registry: CommandRegistry, context: CommandContext | None = None) -> None:
        self.registry = registry
        self.context = context

    def suggest(self, text: str) -> list[CommandSuggestion]:
        return suggest_commands(text, self.registry, self.context)

    def get_completions(
        self,
        document: Document,
        complete_event: object,
    ) -> Iterable[Any]:
        if Completion is None:
            return []
        text = document.text_before_cursor
        suggestions = self.suggest(text)
        replace_length = -len(text) if text else 0
        return [
            Completion(
                suggestion.insert_text,
                start_position=replace_length,
                display=suggestion.display_text,
                display_meta=suggestion.description,
            )
            for suggestion in suggestions
        ]


def build_command_completer(registry: CommandRegistry) -> CommandCompleter:
    return CommandCompleter(registry)


def suggest_commands(
    text: str,
    registry: CommandRegistry,
    context: CommandContext | None = None,
) -> list[CommandSuggestion]:
    stripped = text.lstrip()
    if not stripped.startswith("/"):
        return []
    body = stripped[1:]
    trailing_space = body.endswith(" ")
    tokens = body.split()

    if not tokens:
        return [_suggestion_for(spec) for spec in registry.top_level()]

    if len(tokens) == 1 and not trailing_space:
        prefix = "/" + tokens[0].lower()
        return [
            _suggestion_for(spec)
            for spec in registry.top_level()
            if spec.slash_path.startswith(prefix)
        ]

    group_path = (tokens[0].lower(),)
    child_prefix = "" if trailing_space else tokens[-1].lower()
    base_tokens = tokens if trailing_space else tokens[:-1]
    base_path = tuple(token.lower() for token in base_tokens)

    argument_suggestions = _argument_suggestions_for(base_path, child_prefix, registry, context)
    if argument_suggestions:
        return argument_suggestions

    child_base_path = base_path if registry.find(base_path) is not None else group_path
    children = [
        spec for spec in registry.children_for(child_base_path) if _should_show_in_completion(spec)
    ]

    suggestions = []
    for spec in children:
        visible_path = _completion_display_text(spec)
        if child_prefix and not visible_path.split()[-1].startswith(child_prefix):
            continue
        suggestions.append(_suggestion_for(spec))
    return suggestions


def _should_show_in_completion(spec: CommandSpec) -> bool:
    return (
        spec.handler is not None
        or bool(spec.children)
        or bool(spec.argument_suggestions)
        or spec.argument_provider is not None
    )


def _argument_suggestions_for(
    base_path: tuple[str, ...],
    prefix: str,
    registry: CommandRegistry,
    context: CommandContext | None,
) -> list[CommandSuggestion]:
    spec = registry.find(base_path)
    if spec is None:
        return []
    suggestions = list(spec.argument_suggestions)
    if spec.argument_provider is not None:
        suggestions.extend(spec.argument_provider(context, prefix))

    filtered = []
    for suggestion in suggestions:
        if prefix and not suggestion.display_text.lower().startswith(prefix):
            continue
        filtered.append(_argument_suggestion_for(base_path, suggestion))
    return filtered


def _argument_suggestion_for(
    base_path: tuple[str, ...],
    suggestion: CommandSuggestion,
) -> CommandSuggestion:
    trailing_space = suggestion.insert_text.endswith(" ")
    argument = suggestion.insert_text.strip()
    insert_text = "/" + " ".join((*base_path, *argument.split()))
    if trailing_space:
        insert_text = f"{insert_text} "
    return CommandSuggestion(
        insert_text=insert_text,
        display_text=suggestion.display_text,
        description=suggestion.description,
    )


def should_open_followup_completion(text_before_cursor: str, registry: CommandRegistry) -> bool:
    stripped = text_before_cursor.lstrip()
    if not stripped.startswith("/") or not stripped.endswith(" "):
        return False
    tokens = stripped[1:].split()
    if not tokens:
        return False
    spec = registry.find(tuple(token.lower() for token in tokens))
    return spec is not None and (
        bool(spec.children) or bool(spec.argument_suggestions) or spec.argument_provider is not None
    )


def should_open_nested_completion(text_before_cursor: str, registry: CommandRegistry) -> bool:
    return should_open_followup_completion(text_before_cursor, registry)


def build_command_key_bindings(registry: CommandRegistry):
    from prompt_toolkit.key_binding import KeyBindings

    bindings = KeyBindings()

    @bindings.add("enter")
    def _accept_completion_or_submit(event):
        buffer = event.current_buffer
        completion_state = buffer.complete_state
        completion = completion_state.current_completion if completion_state is not None else None
        if completion is not None:
            buffer.apply_completion(completion)
            if should_open_followup_completion(buffer.document.text_before_cursor, registry):
                buffer.start_completion(select_first=False)
                return
        buffer.validate_and_handle()

    return bindings


def _suggestion_for(spec: CommandSpec) -> CommandSuggestion:
    return CommandSuggestion(
        insert_text=_completion_insert_text(spec),
        display_text=_completion_display_text(spec),
        description=spec.description,
    )


def _completion_display_text(spec: CommandSpec) -> str:
    path_size = len(spec.path)
    parts = spec.usage.split()
    display_parts = parts[:path_size]
    display_parts.extend(part for part in parts[path_size:] if part.startswith("--"))
    return " ".join(display_parts)


def _completion_insert_text(spec: CommandSpec) -> str:
    text = _completion_display_text(spec)
    if spec.children:
        return f"{text} "
    usage_parts = spec.usage.split()
    display_size = len(text.split())
    remaining_parts = usage_parts[display_size:]
    if any(
        part.startswith("<") or ("|" in part and not part.startswith("["))
        for part in remaining_parts
    ):
        return f"{text} "
    return text
