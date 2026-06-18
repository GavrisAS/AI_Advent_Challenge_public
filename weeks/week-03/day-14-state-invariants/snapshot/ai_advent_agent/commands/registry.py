"""Command tree and alias registry."""

from __future__ import annotations

from .core import CommandAlias, CommandError, CommandGroup, CommandSpec


class CommandRegistry:
    """Stores command specs, aliases and help metadata."""

    def __init__(self) -> None:
        self._commands: dict[tuple[str, ...], CommandSpec] = {}
        self._aliases: dict[tuple[str, ...], CommandAlias] = {}
        self._groups: dict[str, CommandGroup] = {}

    def register_group(self, name: str, description: str, *, order: int = 100) -> None:
        self._groups[name] = CommandGroup(name=name, description=description)
        self.register(
            CommandSpec(path=(name,), usage=f"/{name}", description=description, order=order)
        )

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
                    order=spec.order,
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
        return sorted(
            (spec for path, spec in self._commands.items() if len(path) == 1 and not spec.legacy),
            key=_spec_sort_key,
        )

    def children_for(self, path: tuple[str, ...]) -> list[CommandSpec]:
        spec = self.find(path)
        if spec is None:
            return []
        return sorted(spec.children.values(), key=_spec_sort_key)

    def group_help(self, group: str | None = None) -> list[CommandSpec]:
        if group is None:
            return self.top_level()
        prefix = (group,)
        return sorted(
            (
                spec
                for path, spec in self._commands.items()
                if path == prefix or (len(path) > 1 and path[:1] == prefix and not spec.legacy)
            ),
            key=_spec_sort_key,
        )

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

    def command_items(self) -> list[tuple[tuple[str, ...], CommandSpec]]:
        return sorted(self._commands.items(), key=lambda item: _spec_sort_key(item[1]))


def _spec_sort_key(spec: CommandSpec) -> tuple[int, str]:
    return spec.order, spec.slash_path
