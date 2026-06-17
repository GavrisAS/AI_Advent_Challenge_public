"""Slash-command registry, router and completion for the training agent."""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from ai_advent_agent.agent import AgentResponse, SimpleAgent
from ai_advent_agent.config import AgentStrategy, SummaryMode, parse_overflow_policy
from ai_advent_agent.llm_client import Message
from ai_advent_agent.memory_layers import parse_key_value_argument
from ai_advent_agent.storage import ContextStorageError
from ai_advent_agent.token_report import TokenReport

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


CommandHandler = Callable[["CommandContext", str], "CommandResult"]


class CommandError(RuntimeError):
    """Raised when a slash-command cannot be parsed or executed."""


@dataclass(slots=True)
class CommandContext:
    """Runtime objects available to command handlers."""

    agent: SimpleAgent
    show_metadata: bool = True


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
    text: str
    description: str


class CommandRegistry:
    """Stores command specs, aliases and help metadata."""

    def __init__(self) -> None:
        self._commands: dict[tuple[str, ...], CommandSpec] = {}
        self._aliases: dict[tuple[str, ...], CommandAlias] = {}
        self._groups: dict[str, CommandGroup] = {}

    def register_group(self, name: str, description: str) -> None:
        self._groups[name] = CommandGroup(name=name, description=description)
        self.register(CommandSpec(path=(name,), usage=f"/{name}", description=description))

    def register(self, spec: CommandSpec) -> None:
        if not spec.path:
            raise CommandError("command path не должен быть пустым")
        self._commands[spec.path] = spec
        if len(spec.path) > 1:
            parent = self._commands.get(spec.path[:-1])
            if parent is None:
                parent = CommandSpec(
                    path=spec.path[:-1],
                    usage="/" + " ".join(spec.path[:-1]),
                    description="Группа команд.",
                )
                self.register(parent)
            parent.children[spec.path[-1]] = spec
        for alias in spec.aliases:
            self.add_alias(alias, spec.path, legacy=spec.legacy)

    def add_alias(
        self,
        source: tuple[str, ...],
        target: tuple[str, ...],
        *,
        legacy: bool = True,
    ) -> None:
        self._aliases[source] = CommandAlias(source=source, target=target, legacy=legacy)

    def find(self, path: tuple[str, ...]) -> CommandSpec | None:
        return self._commands.get(path)

    def top_level(self) -> list[CommandSpec]:
        return [
            spec
            for path, spec in sorted(self._commands.items())
            if len(path) == 1 and not spec.legacy
        ]

    def children_for(self, path: tuple[str, ...]) -> list[CommandSpec]:
        spec = self.find(path)
        if spec is None:
            return []
        return [spec.children[name] for name in sorted(spec.children)]

    def group_help(self, group: str | None = None) -> list[CommandSpec]:
        if group is None:
            return self.top_level()
        prefix = (group,)
        return [
            spec
            for path, spec in sorted(self._commands.items())
            if path == prefix or (len(path) > 1 and path[:1] == prefix and not spec.legacy)
        ]

    def legacy_help(self) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        for alias in sorted(self._aliases.values(), key=lambda item: item.source):
            if alias.legacy:
                rows.append(("/" + " ".join(alias.source), "/" + " ".join(alias.target)))
        return rows

    def resolve_alias(
        self,
        path: tuple[str, ...],
    ) -> tuple[CommandAlias | None, tuple[str, ...], tuple[str, ...]]:
        for size in range(len(path), 0, -1):
            source = path[:size]
            alias = self._aliases.get(source)
            if alias is not None:
                return alias, alias.target, path[size:]
        return None, path, ()

    def suggestions(self, text: str) -> list[CommandSuggestion]:
        stripped = text.lstrip()
        if not stripped.startswith("/"):
            return []
        body = stripped[1:]
        trailing_space = body.endswith(" ")
        tokens = body.split()

        if not tokens:
            return [
                CommandSuggestion(_completion_text(spec), spec.description)
                for spec in self.top_level()
            ]

        if len(tokens) == 1 and not trailing_space:
            prefix = "/" + tokens[0].lower()
            return [
                CommandSuggestion(_completion_text(spec), spec.description)
                for spec in self.top_level()
                if spec.slash_path.startswith(prefix)
            ]

        group_path = (tokens[0].lower(),)
        child_prefix = "" if trailing_space else tokens[-1].lower()
        base_tokens = tokens if trailing_space else tokens[:-1]
        base_path = tuple(token.lower() for token in base_tokens)
        if base_path != group_path and self.find(base_path) is not None:
            children = [
                spec
                for path, spec in sorted(self._commands.items())
                if len(path) > len(base_path)
                and path[: len(base_path)] == base_path
                and spec.handler is not None
            ]
        else:
            children = [
                spec
                for path, spec in sorted(self._commands.items())
                if len(path) > len(group_path)
                and path[:1] == group_path
                and spec.handler is not None
            ]
        suggestions = []
        for spec in children:
            visible_path = _completion_text(spec)
            if child_prefix and not visible_path.split()[-1].startswith(child_prefix):
                continue
            suggestions.append(CommandSuggestion(visible_path, spec.description))
        return suggestions


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
            _print_group_usage(self.registry, spec.path)
            return CommandResult()

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


class CommandCompleter(Completer):  # type: ignore[misc, valid-type]
    """prompt_toolkit adapter backed by CommandRegistry."""

    def __init__(self, registry: CommandRegistry) -> None:
        self.registry = registry

    def suggest(self, text: str) -> list[CommandSuggestion]:
        return self.registry.suggestions(text)

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
                suggestion.text,
                start_position=replace_length,
                display=suggestion.text,
                display_meta=suggestion.description,
            )
            for suggestion in suggestions
        ]


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

    specs = [
        CommandSpec(("help",), "/help [group|legacy]", "Показать справку.", _handle_help),
        CommandSpec(("status",), "/status", "Краткая диагностика состояния.", _handle_status),
        CommandSpec(("status", "config"), "/status config", "Показать настройки.", _handle_config),
        CommandSpec(
            ("status", "context"),
            "/status context",
            "Показать контекстные файлы.",
            _handle_context_status,
        ),
        CommandSpec(
            ("status", "tokens"), "/status tokens", "Показать token breakdown.", _handle_tokens
        ),
        CommandSpec(
            ("status", "report"),
            "/status report",
            "Показать последний token report.",
            _handle_last_report,
        ),
        CommandSpec(
            ("status", "history"), "/status history", "Показать сводку history.", _handle_history
        ),
        CommandSpec(
            ("status", "history", "full"),
            "/status history full",
            "Показать полную history.",
            _handle_history_full,
        ),
        CommandSpec(
            ("config", "show"), "/config show", "Показать текущую конфигурацию.", _handle_config
        ),
        CommandSpec(
            ("config", "strategy"),
            "/config strategy direct|step_by_step",
            "Изменить response strategy.",
            _handle_config_strategy,
        ),
        CommandSpec(
            ("config", "summary"),
            "/config summary off|llm",
            "Изменить summary mode.",
            _handle_config_summary,
        ),
        CommandSpec(
            ("config", "overflow"),
            "/config overflow error|no_trim|sliding_window",
            "Изменить overflow policy.",
            _handle_config_overflow,
        ),
        CommandSpec(
            ("session", "reset"),
            "/session reset",
            "Начать новую сессию и сохранить system prompt.",
            _handle_session_reset,
        ),
        CommandSpec(
            ("storage", "clear", "context"),
            "/storage clear context",
            "Удалить context/runtime файлы текущего контекста.",
            _handle_storage_clear_context,
        ),
        CommandSpec(
            ("storage", "clear", "reports"),
            "/storage clear reports",
            "Удалить token reports.",
            _handle_storage_clear_reports,
        ),
        CommandSpec(
            ("storage", "clear", "all"),
            "/storage clear all --yes",
            "Удалить все runtime-файлы агента.",
            _handle_storage_clear_all,
        ),
        CommandSpec(("memory",), "/memory", "Показать сводку memory subsystem.", _handle_memory),
        CommandSpec(
            ("memory", "short"),
            "/memory short",
            "Показать short-term memory.",
            _handle_memory_short,
        ),
        CommandSpec(
            ("memory", "summary"),
            "/memory summary",
            "Показать summary memory.",
            _handle_memory_summary_command,
        ),
        CommandSpec(
            ("memory", "facts"), "/memory facts", "Показать sticky facts.", _handle_memory_facts
        ),
        CommandSpec(
            ("memory", "working"),
            "/memory working",
            "Показать working memory.",
            _handle_memory_working,
        ),
        CommandSpec(
            ("memory", "long"), "/memory long", "Показать long-term memory.", _handle_memory_long
        ),
        CommandSpec(
            ("memory", "add", "short"),
            "/memory add short <text>",
            "Добавить short-term note.",
            _handle_memory_add_short,
        ),
        CommandSpec(
            ("memory", "set", "working"),
            "/memory set working <key>: <value>",
            "Записать working memory.",
            _handle_memory_set_working,
        ),
        CommandSpec(
            ("memory", "set", "long"),
            "/memory set long <key>: <value>",
            "Записать long-term memory.",
            _handle_memory_set_long,
        ),
        CommandSpec(
            ("memory", "forget", "working"),
            "/memory forget working <key>",
            "Удалить working memory entry.",
            _handle_memory_forget_working,
        ),
        CommandSpec(
            ("memory", "forget", "long"),
            "/memory forget long <key>",
            "Удалить long-term memory entry.",
            _handle_memory_forget_long,
        ),
        CommandSpec(
            ("memory", "reset", "working"),
            "/memory reset working",
            "Очистить working memory.",
            _handle_memory_reset_working,
        ),
        CommandSpec(
            ("memory", "reset", "all"),
            "/memory reset all --yes",
            "Очистить все memory layers.",
            _handle_memory_reset_all,
        ),
        CommandSpec(
            ("branch", "list"),
            "/branch list",
            "Показать branches и checkpoints.",
            _handle_branch_list,
        ),
        CommandSpec(
            ("branch", "checkpoint"),
            "/branch checkpoint <name>",
            "Создать checkpoint.",
            _handle_branch_checkpoint,
        ),
        CommandSpec(
            ("branch", "create"), "/branch create <name>", "Создать branch.", _handle_branch_create
        ),
        CommandSpec(
            ("branch", "switch"),
            "/branch switch <name>",
            "Переключиться на branch.",
            _handle_branch_switch,
        ),
        CommandSpec(
            ("file", "analyze"),
            "/file analyze <path>",
            "Dry-run token report для файла.",
            _handle_file_analyze,
        ),
        CommandSpec(
            ("file", "ask"), "/file ask <path>", "Отправить файл в модель.", _handle_file_ask
        ),
        CommandSpec(("exit",), "/exit", "Выйти из интерактивного режима.", _handle_exit),
    ]
    for spec in specs:
        registry.register(spec)

    for old, new in [
        (("quit",), ("exit",)),
        (("context",), ("status", "context")),
        (("config",), ("status", "config")),
        (("tokens",), ("status", "tokens")),
        (("last-report",), ("status", "report")),
        (("history",), ("status", "history")),
        (("history", "full"), ("status", "history", "full")),
        (("strategy",), ("config", "strategy")),
        (("summary-mode",), ("config", "summary")),
        (("context-mode",), ("config", "overflow")),
        (("reset",), ("session", "reset")),
        (("clear-context",), ("storage", "clear", "context")),
        (("summary",), ("memory", "summary")),
        (("facts",), ("memory", "facts")),
        (("remember", "short"), ("memory", "add", "short")),
        (("remember", "working"), ("memory", "set", "working")),
        (("remember", "long"), ("memory", "set", "long")),
        (("forget", "working"), ("memory", "forget", "working")),
        (("forget", "long"), ("memory", "forget", "long")),
        (("branches",), ("branch", "list")),
        (("checkpoint",), ("branch", "checkpoint")),
        (("switch",), ("branch", "switch")),
        (("analyze-file",), ("file", "analyze")),
        (("ask-file",), ("file", "ask")),
    ]:
        registry.add_alias(old, new, legacy=True)
    return registry


def _argument_after_path(command: str, path_size: int) -> str:
    body = command.strip()[1:]
    parts = body.split(maxsplit=path_size)
    if len(parts) <= path_size:
        return ""
    return parts[path_size].strip()


def _completion_text(spec: CommandSpec) -> str:
    return " ".join(part for part in spec.usage.split() if not part.startswith("<"))


def _print_group_usage(registry: CommandRegistry, path: tuple[str, ...]) -> None:
    commands = registry.children_for(path)
    if not commands:
        print(f"Использование: /{' '.join(path)}\n")
        return
    print(f"Команды /{' '.join(path)}:")
    for spec in commands:
        print(f"  {spec.usage:<36} — {spec.description}")
    print()


def _handle_help(context: CommandContext, argument: str) -> CommandResult:
    registry = build_command_registry()
    topic = argument.strip().lower()
    if topic == "legacy":
        print("Legacy aliases:")
        for old, new in registry.legacy_help():
            print(f"  {old:<28} -> {new}")
        print()
        return CommandResult()
    if topic:
        specs = registry.group_help(topic)
        if not specs:
            print(f"Нет справки для группы: {topic}\n")
            return CommandResult()
        print(f"Команды /{topic}:")
        for spec in specs:
            if spec.handler is not None:
                print(f"  {spec.usage:<40} — {spec.description}")
        print()
        return CommandResult()

    print("Slash-команды:")
    for spec in registry.top_level():
        print(f"  {spec.usage:<16} — {spec.description}")
    print("\nИспользуйте /help <group> или /help legacy.\n")
    _ = context
    return CommandResult()


def _handle_status(context: CommandContext, argument: str) -> CommandResult:
    if argument.strip():
        _print_group_usage(build_command_registry(), ("status",))
        return CommandResult()
    agent = context.agent
    print("Status:")
    print(f"  messages: {len(agent.get_history())}")
    print(f"  strategy: {agent.config.strategy}")
    print(f"  overflow_policy: {agent.config.overflow_policy.value}")
    print(f"  context_strategy: {agent.config.context_strategy}")
    print(f"  summary_mode: {agent.config.summary_mode}")
    print(f"  active_branch: {agent.branch_memory.active_branch}")
    memory_layers_active = (
        agent.short_term_memory.active
        or agent.working_memory.active
        or agent.long_term_memory.active
    )
    print(f"  memory_layers_active: {memory_layers_active}")
    print()
    return CommandResult()


def _handle_config(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        _print_group_usage(build_command_registry(), ("config",))
        return CommandResult()
    print_config(context.agent)
    return CommandResult()


def _handle_context_status(context: CommandContext, argument: str = "") -> CommandResult:
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
    print(f"Файл token reports: {agent.token_report_path or 'логирование отключено'}\n")
    return CommandResult()


def _handle_tokens(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /status tokens\n")
        return CommandResult()
    print_token_breakdown(context.agent)
    return CommandResult()


def _handle_last_report(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /status report\n")
        return CommandResult()
    if context.agent.last_token_report is None:
        print("За текущий запуск ещё нет token report.\n")
    else:
        print_token_report(context.agent.last_token_report)
        print()
    return CommandResult()


def _handle_history(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /status history или /status history full\n")
        return CommandResult()
    print_history_summary(context.agent.get_history())
    return CommandResult()


def _handle_history_full(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /status history full\n")
        return CommandResult()
    print_history_full(context.agent.get_history())
    return CommandResult()


def _handle_config_strategy(context: CommandContext, argument: str) -> CommandResult:
    value = argument.strip().lower()
    if value not in {"direct", "step_by_step"}:
        print("Использование: /config strategy direct или /config strategy step_by_step\n")
        return CommandResult()
    context.agent.set_strategy(cast(AgentStrategy, value))
    print(f"Стратегия изменена: {context.agent.config.strategy}\n")
    return CommandResult()


def _handle_config_summary(context: CommandContext, argument: str) -> CommandResult:
    value = argument.strip().lower()
    if value not in {"off", "llm"}:
        print("Использование: /config summary off|llm\n")
        return CommandResult()
    context.agent.set_summary_mode(cast(SummaryMode, value))
    print(f"Summary mode изменён: {context.agent.config.summary_mode}\n")
    return CommandResult()


def _handle_config_overflow(context: CommandContext, argument: str) -> CommandResult:
    value = argument.strip().lower()
    if not value:
        print("Использование: /config overflow error|no_trim|sliding_window\n")
        return CommandResult()
    context.agent.set_overflow_policy(parse_overflow_policy(value))
    print(f"Context overflow policy изменена: {context.agent.config.overflow_policy.value}\n")
    return CommandResult()


def _handle_session_reset(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /session reset\n")
        return CommandResult()
    context.agent.reset()
    print("Новая сессия начата. В JSON сохранён system prompt, token reports очищены.\n")
    return CommandResult()


def _handle_storage_clear_context(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /storage clear context\n")
        return CommandResult()
    context.agent.clear_context_file()
    print("Runtime-файлы контекста удалены. Новая сессия начата с system prompt.\n")
    return CommandResult()


def _handle_storage_clear_reports(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /storage clear reports\n")
        return CommandResult()
    context.agent.last_token_report = None
    if context.agent.token_report_store is not None:
        context.agent.token_report_store.clear()
    print("Token reports удалены.\n")
    return CommandResult()


def _handle_storage_clear_all(context: CommandContext, argument: str) -> CommandResult:
    if argument.strip() != "--yes":
        print("Для удаления всех runtime-файлов используйте: /storage clear all --yes\n")
        return CommandResult()
    agent = context.agent
    agent.clear_context_file()
    agent.short_term_memory.clear()
    agent.working_memory.clear()
    agent.long_term_memory.clear()
    if agent.working_memory_store is not None:
        agent.working_memory_store.clear()
    if agent.long_term_memory_store is not None:
        agent.long_term_memory_store.clear()
    if agent.memory_event_store is not None:
        agent.memory_event_store.clear()
    print("Все runtime-файлы агента удалены.\n")
    return CommandResult()


def _handle_memory(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        _print_group_usage(build_command_registry(), ("memory",))
        return CommandResult()
    print_memory_summary(context.agent)
    return CommandResult()


def _handle_memory_short(context: CommandContext, argument: str = "") -> CommandResult:
    return _memory_layer_command(context, argument, "short")


def _handle_memory_working(context: CommandContext, argument: str = "") -> CommandResult:
    return _memory_layer_command(context, argument, "working")


def _handle_memory_long(context: CommandContext, argument: str = "") -> CommandResult:
    return _memory_layer_command(context, argument, "long")


def _memory_layer_command(context: CommandContext, argument: str, layer: str) -> CommandResult:
    if argument.strip():
        print(f"Использование: /memory {layer}\n")
        return CommandResult()
    print_memory_layer(context.agent, layer)
    return CommandResult()


def _handle_memory_summary_command(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip() == "clear":
        context.agent.summary_memory.summary = ""
        context.agent.summary_memory.summarized_message_count = 0
        context.agent.summary_memory.updated_at = ""
        context.agent.save_summary()
        print("Summary memory очищена.\n")
        return CommandResult()
    if argument.strip():
        print("Использование: /memory summary\n")
        return CommandResult()
    if not context.agent.summary_memory.active:
        print("Summary memory пустая.\n")
    else:
        print(
            "Summary memory:\n"
            f"{context.agent.summary_memory.summary}\n\n"
            f"Сжато сообщений: {context.agent.summary_memory.summarized_message_count}\n"
        )
    return CommandResult()


def _handle_memory_facts(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /memory facts\n")
        return CommandResult()
    facts = context.agent.facts_memory.normalized()
    if not context.agent.facts_memory.active:
        print("Sticky facts пустые.\n")
    else:
        print("Sticky facts:")
        for key, value in facts.items():
            if value.strip():
                print(f"  {key}: {value}")
        print()
    return CommandResult()


def _handle_memory_add_short(context: CommandContext, argument: str) -> CommandResult:
    if not argument.strip():
        print("Использование: /memory add short <text>\n")
        return CommandResult()
    context.agent.remember_short(argument.strip())
    print("Сохранено в short-term memory.\n")
    return CommandResult()


def _handle_memory_set_working(context: CommandContext, argument: str) -> CommandResult:
    if not argument.strip():
        print("Использование: /memory set working <key>: <value>\n")
        return CommandResult()
    key, value = parse_key_value_argument(argument)
    context.agent.remember_working(key, value)
    print(f"Сохранено в working memory: {key}\n")
    return CommandResult()


def _handle_memory_set_long(context: CommandContext, argument: str) -> CommandResult:
    if not argument.strip():
        print("Использование: /memory set long <key>: <value>\n")
        return CommandResult()
    key, value = parse_key_value_argument(argument)
    context.agent.remember_long(key, value)
    print(f"Сохранено в long-term memory: {key}\n")
    return CommandResult()


def _handle_memory_forget_working(context: CommandContext, argument: str) -> CommandResult:
    key = argument.strip()
    if not key:
        print("Использование: /memory forget working <key>\n")
        return CommandResult()
    removed = context.agent.forget_working(key)
    print(("Удалено" if removed else "Ключ не найден") + f" в working memory: {key}\n")
    return CommandResult()


def _handle_memory_forget_long(context: CommandContext, argument: str) -> CommandResult:
    key = argument.strip()
    if not key:
        print("Использование: /memory forget long <key>\n")
        return CommandResult()
    removed = context.agent.forget_long(key)
    print(("Удалено" if removed else "Ключ не найден") + f" в long-term memory: {key}\n")
    return CommandResult()


def _handle_memory_reset_working(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /memory reset working\n")
        return CommandResult()
    context.agent.reset_working_memory()
    print("Working memory очищена.\n")
    return CommandResult()


def _handle_memory_reset_all(context: CommandContext, argument: str) -> CommandResult:
    if argument.strip() != "--yes":
        print("Для очистки всех memory layers используйте: /memory reset all --yes\n")
        return CommandResult()
    context.agent.reset_all_memory_layers()
    print("Все memory layers очищены.\n")
    return CommandResult()


def _handle_branch_list(context: CommandContext, argument: str = "") -> CommandResult:
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


def _handle_branch_checkpoint(context: CommandContext, argument: str) -> CommandResult:
    name = argument.strip()
    if not name:
        print("Использование: /branch checkpoint <name>\n")
        return CommandResult()
    context.agent.create_checkpoint(name)
    print(f"Checkpoint создан: {name}\n")
    return CommandResult()


def _handle_branch_create(context: CommandContext, argument: str) -> CommandResult:
    name = argument.strip()
    if not name:
        print("Использование: /branch create <name>\n")
        return CommandResult()
    context.agent.create_branch(name)
    print(f"Ветка создана и активирована: {name}\n")
    return CommandResult()


def _handle_branch_switch(context: CommandContext, argument: str) -> CommandResult:
    name = argument.strip()
    if not name:
        print("Использование: /branch switch <name>\n")
        return CommandResult()
    context.agent.switch_branch(name)
    print(f"Активная ветка: {name}\n")
    return CommandResult()


def _handle_file_analyze(context: CommandContext, argument: str) -> CommandResult:
    path = _extract_path_argument(argument)
    if path is None:
        print("Использование: /file analyze path/to/skills-all.md\n")
        return CommandResult()
    analyze_file(path, context.agent)
    return CommandResult()


def _handle_file_ask(context: CommandContext, argument: str) -> CommandResult:
    path = _extract_path_argument(argument)
    if path is None:
        print("Использование: /file ask path/to/skills-all.md\n")
        return CommandResult()
    ask_file(path, context.agent, show_metadata=context.show_metadata)
    return CommandResult()


def _handle_exit(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /exit\n")
        return CommandResult()
    _ = context
    return CommandResult(exit_requested=True)


def _extract_path_argument(argument: str) -> Path | None:
    cleaned = argument.strip()
    if not cleaned:
        return None
    return Path(cleaned.strip('"').strip("'"))


def print_config(agent: SimpleAgent) -> None:
    config = agent.config
    print(
        "Текущая конфигурация:\n"
        f"  model: {config.model}\n"
        f"  strategy: {config.strategy}\n"
        f"  temperature: {config.temperature}\n"
        f"  max_tokens: {config.max_tokens}\n"
        f"  thinking: {config.thinking_type}\n"
        f"  reasoning_effort: {config.reasoning_effort or '-'}\n"
        f"  context_window_tokens: {format_number(config.context_window_tokens)}\n"
        f"  warn_context_ratio: {config.warn_context_ratio:.2f}\n"
        f"  overflow_policy: {config.overflow_policy.value}\n"
        f"  context_strategy: {config.context_strategy}\n"
        f"  summary_mode: {config.summary_mode}\n"
        f"  recent_messages_limit: {config.recent_messages_limit}\n"
        f"  summarize_every_messages: {config.summarize_every_messages}\n"
        f"  summary_max_tokens: {config.summary_max_tokens}\n"
        f"  input_price_per_1m_tokens: {config.input_price_per_1m_tokens}\n"
        f"  output_price_per_1m_tokens: {config.output_price_per_1m_tokens}\n"
        f"  context_file: {agent.context_path or 'disabled'}\n"
        f"  facts_file: {agent.facts_path or 'disabled'}\n"
        f"  branches_file: {agent.branches_path or 'disabled'}\n"
        f"  summary_file: {agent.summary_path or 'disabled'}\n"
        f"  short_term_memory_file: {agent.short_term_memory_path or 'disabled'}\n"
        f"  working_memory_file: {agent.working_memory_path or 'disabled'}\n"
        f"  long_term_memory_file: {agent.long_term_memory_path or 'disabled'}\n"
        f"  memory_events_file: {agent.memory_events_path or 'disabled'}\n"
        f"  token_report_file: {agent.token_report_path or 'disabled'}\n"
    )


def print_metadata(response: AgentResponse) -> None:
    usage = response.usage or {}
    print(
        "\n--- metadata ---\n"
        f"model: {response.model}\n"
        f"strategy: {response.strategy}\n"
        f"finish_reason: {response.finish_reason}\n"
        f"elapsed_seconds: {response.elapsed_seconds:.2f}\n"
        f"message_count: {response.message_count}\n"
        f"summary_active: {response.summary_active}\n"
        f"context_saved: {response.context_saved}\n"
        f"context_path: {response.context_path or '-'}\n"
        f"prompt_tokens_actual: {usage.get('prompt_tokens', '-')}\n"
        f"completion_tokens_actual: {usage.get('completion_tokens', '-')}\n"
        f"total_tokens_actual: {usage.get('total_tokens', '-')}"
    )
    print_token_report(response.token_report)


def print_token_report(report: TokenReport) -> None:
    print(
        "\n--- token report ---\n"
        f"request_tokens_estimated: {format_number(report.request_tokens_estimated)}\n"
        "history_tokens_before_estimated: "
        f"{format_number(report.history_tokens_before_estimated)}\n"
        f"prompt_tokens_estimated: {format_number(report.prompt_tokens_estimated)}\n"
        f"projected_total_tokens_estimated: "
        f"{format_number(report.projected_total_tokens_estimated)}\n"
        f"context_window_tokens: {format_number(report.context_window_tokens)}\n"
        f"context_usage: {report.context_usage_percent:.2f}%\n"
        f"projected_usage: {report.projected_usage_percent:.2f}%\n"
        f"warning: {report.warn_threshold_reached}\n"
        f"overflow_detected: {report.overflow_detected}\n"
        f"overflow_policy: {report.overflow_policy}\n"
        f"trimmed_messages_count: {report.trimmed_messages_count}\n"
        f"summary_active: {report.summary_active}\n"
        f"summary_tokens_estimated: {format_number(report.summary_tokens_estimated)}\n"
        f"summarized_messages_count: {format_number(report.summarized_messages_count)}"
    )
    if report.memory_layers_active:
        print(
            "memory_layers_active: true\n"
            f"memory_layer_entries: {report.memory_layer_entries}\n"
            f"memory_layer_tokens_estimated: {report.memory_layer_tokens_estimated}\n"
            "memory_prompt_tokens_estimated: "
            f"{format_number(report.memory_prompt_tokens_estimated)}\n"
            f"prompt_assembly_order: {', '.join(report.prompt_assembly_order)}"
        )
    if report.response_tokens_estimated is not None:
        print(f"response_tokens_estimated: {format_number(report.response_tokens_estimated)}")
    if report.history_tokens_after_response_estimated is not None:
        print(
            "history_tokens_after_response_estimated: "
            f"{format_number(report.history_tokens_after_response_estimated)}"
        )
    print(
        f"prompt_tokens_actual: {format_optional_number(report.prompt_tokens_actual)}\n"
        f"completion_tokens_actual: {format_optional_number(report.completion_tokens_actual)}\n"
        f"total_tokens_actual: {format_optional_number(report.total_tokens_actual)}"
    )
    if report.estimated_total_cost_usd is not None:
        print(
            "estimated_cost_usd: "
            f"input={report.estimated_input_cost_usd:.8f}, "
            f"output={report.estimated_output_cost_usd:.8f}, "
            f"total={report.estimated_total_cost_usd:.8f}"
        )
    if report.elapsed_seconds is not None:
        print(f"elapsed_seconds: {report.elapsed_seconds:.2f}")


def print_token_breakdown(agent: SimpleAgent) -> None:
    breakdown = agent.get_token_breakdown()
    config = agent.config
    ratio = breakdown.total / config.context_window_tokens
    projected_ratio = (breakdown.total + config.max_tokens) / config.context_window_tokens
    print(
        "Token breakdown текущей истории:\n"
        f"  messages: {breakdown.message_count}\n"
        f"  total_estimated: {format_number(breakdown.total)}\n"
        f"  system: {format_number(breakdown.system)}\n"
        f"  user: {format_number(breakdown.user)}\n"
        f"  assistant: {format_number(breakdown.assistant)}\n"
        f"  tool: {format_number(breakdown.tool)}\n"
        f"  context_window_tokens: {format_number(config.context_window_tokens)}\n"
        f"  current_context_usage: {ratio * 100:.2f}%\n"
        f"  projected_with_max_tokens: {projected_ratio * 100:.2f}%\n"
    )


def print_history_summary(messages: list[Message]) -> None:
    role_counts: dict[str, int] = {}
    for message in messages:
        role = message.get("role", "unknown")
        role_counts[role] = role_counts.get(role, 0) + 1
    print(f"Сообщений в истории: {len(messages)}")
    for role, count in sorted(role_counts.items()):
        print(f"  {role}: {count}")
    print()


def print_history_full(messages: list[Message]) -> None:
    for index, message in enumerate(messages, start=1):
        content = message.get("content", "")
        print(f"[{index}] {message.get('role', 'unknown')}\n{content}\n")


def print_memory_summary(agent: SimpleAgent) -> None:
    short_notes = agent.short_term_memory.normalized_notes()
    recent_messages = agent.short_term_memory.recent_messages
    working = agent.working_memory.normalized()
    long_term = agent.long_term_memory.normalized()
    print("Memory layers:")
    print(
        f"  short-term: notes={len(short_notes)}, "
        f"recent_messages={len(recent_messages)}, file={agent.short_term_memory_path or 'disabled'}"
    )
    print(f"  working: entries={len(working)}, file={agent.working_memory_path or 'disabled'}")
    print(
        f"  long-term: entries={len(long_term)}, file={agent.long_term_memory_path or 'disabled'}"
    )
    print(f"  events: {agent.memory_events_path or 'disabled'}\n")


def print_memory_layer(agent: SimpleAgent, layer: str) -> None:
    if layer == "short":
        notes = agent.short_term_memory.normalized_notes()
        recent_messages = agent.short_term_memory.recent_messages
        print("Short-term memory:")
        if not notes and not recent_messages:
            print("  пусто\n")
            return
        if notes:
            print("  Явные notes:")
            for note in notes:
                print(f"    - {note}")
        if recent_messages:
            print("  Последние сообщения:")
            for message in recent_messages:
                print(f"    - {message['role']}: {message['content']}")
        print()
        return
    if layer == "working":
        print_key_value_memory("Working memory", agent.working_memory.normalized())
        return
    if layer == "long":
        print_key_value_memory("Long-term memory", agent.long_term_memory.normalized())
        return
    raise ValueError("memory layer должен быть short, working или long")


def print_key_value_memory(title: str, entries: dict[str, str]) -> None:
    print(f"{title}:")
    if not entries:
        print("  пусто\n")
        return
    for key, value in entries.items():
        print(f"  {key}: {value}")
    print()


def analyze_file(path: Path, agent: SimpleAgent) -> None:
    text = path.expanduser().read_text(encoding="utf-8")
    report = agent.build_file_token_report(text)
    print(f"Файл: {path}")
    print(f"Размер: {format_number(len(text))} символов")
    print_token_report(report)
    print("\nDry-run: содержимое файла не отправлялось в API и не сохранялось в history.\n")


def ask_file(path: Path, agent: SimpleAgent, *, show_metadata: bool) -> None:
    text = path.expanduser().read_text(encoding="utf-8")
    print(
        f"Файл {path} будет отправлен в модель как одно user message "
        f"({format_number(agent.estimate_text_tokens(text))} estimated tokens)."
    )
    response = agent.ask(text)
    print(f"\nAgent:\n{response.content.strip()}")
    if show_metadata:
        print_metadata(response)
    print()


def format_number(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def format_optional_number(value: int | None) -> str:
    return "-" if value is None else format_number(value)
