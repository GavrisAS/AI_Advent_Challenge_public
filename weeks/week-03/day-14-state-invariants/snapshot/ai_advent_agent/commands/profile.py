"""Handlers for /profile commands."""

from __future__ import annotations

from ai_advent_agent.memory_layers import parse_key_value_argument
from ai_advent_agent.user_profile import PROFILE_FIELDS, UserProfile, normalize_profile_name

from .core import CommandContext, CommandResult, CommandSpec, CommandSuggestion
from .help import print_group_usage


def command_specs() -> list[CommandSpec]:
    return [
        CommandSpec(
            ("profile",),
            "/profile",
            "Assistant personalization profiles.",
            handle_profile,
            order=65,
        ),
        CommandSpec(
            ("profile", "list"),
            "/profile list",
            "Показать список профилей.",
            handle_profile_list,
            order=10,
        ),
        CommandSpec(
            ("profile", "active"),
            "/profile active",
            "Показать активный профиль.",
            handle_profile_active,
            order=20,
        ),
        CommandSpec(
            ("profile", "show"),
            "/profile show [name]",
            "Показать профиль.",
            handle_profile_show,
            order=30,
            argument_provider=profile_name_suggestions,
        ),
        CommandSpec(
            ("profile", "create"),
            "/profile create <name>",
            "Создать профиль и сделать его активным.",
            handle_profile_create,
            order=40,
        ),
        CommandSpec(
            ("profile", "use"),
            "/profile use <name>",
            "Сделать профиль активным.",
            handle_profile_use,
            order=50,
            argument_provider=profile_name_suggestions,
        ),
        CommandSpec(
            ("profile", "set"),
            "/profile set",
            "Настроить активный профиль.",
            order=60,
            argument_suggestions=(
                CommandSuggestion("language ", "language", "Язык ответов."),
                CommandSuggestion("style ", "style", "Стиль ответов."),
                CommandSuggestion("format ", "format", "Формат ответов."),
                CommandSuggestion("audience ", "audience", "Целевая аудитория."),
                CommandSuggestion("preference ", "preference", "Добавить preference key-value."),
                CommandSuggestion("constraint ", "constraint", "Добавить constraint key-value."),
            ),
        ),
        CommandSpec(
            ("profile", "set", "language"),
            "/profile set language <value>",
            "Задать profile.language.",
            handle_profile_set_language,
            order=61,
        ),
        CommandSpec(
            ("profile", "set", "style"),
            "/profile set style <value>",
            "Задать profile.style.",
            handle_profile_set_style,
            order=62,
        ),
        CommandSpec(
            ("profile", "set", "format"),
            "/profile set format <value>",
            "Задать profile.format.",
            handle_profile_set_format,
            order=63,
        ),
        CommandSpec(
            ("profile", "set", "audience"),
            "/profile set audience <value>",
            "Задать profile.audience.",
            handle_profile_set_audience,
            order=64,
        ),
        CommandSpec(
            ("profile", "set", "preference"),
            "/profile set preference <key>: <value>",
            "Задать profile preference.",
            handle_profile_set_preference,
            order=70,
        ),
        CommandSpec(
            ("profile", "set", "constraint"),
            "/profile set constraint <key>: <value>",
            "Задать profile constraint.",
            handle_profile_set_constraint,
            order=80,
        ),
        CommandSpec(
            ("profile", "reset"),
            "/profile reset",
            "Очистить profile state.",
            order=90,
            argument_suggestions=(
                CommandSuggestion("active --yes", "active --yes", "Очистить активный профиль."),
                CommandSuggestion("all --yes", "all --yes", "Очистить все профили."),
            ),
        ),
        CommandSpec(
            ("profile", "reset", "active"),
            "/profile reset active --yes",
            "Очистить поля активного профиля.",
            handle_profile_reset_active,
            order=90,
        ),
        CommandSpec(
            ("profile", "reset", "all"),
            "/profile reset all --yes",
            "Очистить все профили.",
            handle_profile_reset_all,
            order=100,
        ),
    ]


def profile_name_suggestions(
    context: CommandContext | None,
    prefix: str,
) -> list[CommandSuggestion]:
    if context is None:
        return []
    suggestions: list[CommandSuggestion] = []
    for name in sorted(context.agent.user_profiles.profiles):
        if prefix and not name.startswith(prefix.lower()):
            continue
        suggestions.append(CommandSuggestion(name, name, "User profile."))
    return suggestions


def handle_profile(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        if context.registry is not None:
            print_group_usage(context.registry, ("profile",))
        else:
            print("Использование: /profile\n")
        return CommandResult()
    _print_profile_summary(context)
    return CommandResult()


def handle_profile_list(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /profile list\n")
        return CommandResult()
    profiles = context.agent.user_profiles
    if not profiles.profiles:
        print("Профили не созданы.\n")
        return CommandResult()
    print("Profiles:")
    for name, profile in sorted(profiles.profiles.items()):
        marker = "*" if name == profiles.active_profile else " "
        print(f"  {marker} {name}: fields={profile.fields_count}")
    print()
    return CommandResult()


def handle_profile_active(context: CommandContext, argument: str = "") -> CommandResult:
    if argument.strip():
        print("Использование: /profile active\n")
        return CommandResult()
    profile = context.agent.user_profiles.get_active()
    if profile is None:
        print("Активный профиль не выбран.\n")
    else:
        _print_profile(profile, active=True)
    return CommandResult()


def handle_profile_show(context: CommandContext, argument: str = "") -> CommandResult:
    raw_name = argument.strip()
    if raw_name:
        name = normalize_profile_name(raw_name)
        profile = context.agent.user_profiles.profiles.get(name)
        if profile is None:
            raise ValueError(f"Профиль не найден: {name}")
    else:
        profile = context.agent.user_profiles.get_active()
        if profile is None:
            print("Активный профиль не выбран.\n")
            return CommandResult()
    _print_profile(profile, active=profile.name == context.agent.user_profiles.active_profile)
    return CommandResult()


def handle_profile_create(context: CommandContext, argument: str) -> CommandResult:
    name = argument.strip()
    if not name:
        print("Использование: /profile create <name>\n")
        return CommandResult()
    context.agent.create_profile(name)
    print(f"Профиль создан и активирован: {normalize_profile_name(name)}\n")
    return CommandResult()


def handle_profile_use(context: CommandContext, argument: str) -> CommandResult:
    name = argument.strip()
    if not name:
        print("Использование: /profile use <name>\n")
        return CommandResult()
    context.agent.use_profile(name)
    print(f"Активный профиль: {normalize_profile_name(name)}\n")
    return CommandResult()


def handle_profile_set_language(context: CommandContext, argument: str) -> CommandResult:
    return _set_profile_field(context, "language", argument)


def handle_profile_set_style(context: CommandContext, argument: str) -> CommandResult:
    return _set_profile_field(context, "style", argument)


def handle_profile_set_format(context: CommandContext, argument: str) -> CommandResult:
    return _set_profile_field(context, "format", argument)


def handle_profile_set_audience(context: CommandContext, argument: str) -> CommandResult:
    return _set_profile_field(context, "audience", argument)


def _set_profile_field(
    context: CommandContext,
    field_name: str,
    argument: str,
) -> CommandResult:
    if not argument.strip():
        print("Использование: /profile set language|style|format|audience <value>\n")
        return CommandResult()
    if context.agent.user_profiles.get_active() is None:
        print("Сначала создайте профиль: /profile create <name>\n")
        return CommandResult()
    context.agent.set_profile_field(field_name, argument.strip())
    print(f"Профиль обновлён: {field_name}\n")
    return CommandResult()


def handle_profile_set_preference(context: CommandContext, argument: str) -> CommandResult:
    if not argument.strip():
        print("Использование: /profile set preference <key>: <value>\n")
        return CommandResult()
    if context.agent.user_profiles.get_active() is None:
        print("Сначала создайте профиль: /profile create <name>\n")
        return CommandResult()
    key, value = parse_key_value_argument(argument)
    context.agent.set_profile_preference(key, value)
    print(f"Preference сохранён: {key}\n")
    return CommandResult()


def handle_profile_set_constraint(context: CommandContext, argument: str) -> CommandResult:
    if not argument.strip():
        print("Использование: /profile set constraint <key>: <value>\n")
        return CommandResult()
    if context.agent.user_profiles.get_active() is None:
        print("Сначала создайте профиль: /profile create <name>\n")
        return CommandResult()
    key, value = parse_key_value_argument(argument)
    context.agent.set_profile_constraint(key, value)
    print(f"Constraint сохранён: {key}\n")
    return CommandResult()


def handle_profile_reset_active(context: CommandContext, argument: str) -> CommandResult:
    if argument.strip() != "--yes":
        print("Для очистки активного профиля используйте: /profile reset active --yes\n")
        return CommandResult()
    context.agent.reset_active_profile()
    print("Активный профиль очищен.\n")
    return CommandResult()


def handle_profile_reset_all(context: CommandContext, argument: str) -> CommandResult:
    if argument.strip() != "--yes":
        print("Для очистки всех профилей используйте: /profile reset all --yes\n")
        return CommandResult()
    context.agent.reset_all_profiles()
    print("Все профили очищены.\n")
    return CommandResult()


def _print_profile_summary(context: CommandContext) -> None:
    profiles = context.agent.user_profiles
    print(
        "Profile subsystem:\n"
        f"  profiles: {len(profiles.profiles)}\n"
        f"  active_profile: {profiles.active_profile or '-'}\n"
        f"  user_profiles_file: {context.agent.user_profiles_path or 'disabled'}\n"
        f"  profile_events_file: {context.agent.profile_events_path or 'disabled'}\n"
    )


def _print_profile(profile: UserProfile, *, active: bool) -> None:
    print(f"Profile: {profile.name}")
    print(f"  active: {active}")
    for field_name in PROFILE_FIELDS:
        value = getattr(profile, field_name)
        print(f"  {field_name}: {value or '-'}")
    if profile.preferences:
        print("  preferences:")
        for key, value in sorted(profile.preferences.items()):
            print(f"    {key}: {value}")
    else:
        print("  preferences: -")
    if profile.constraints:
        print("  constraints:")
        for key, value in sorted(profile.constraints.items()):
            print(f"    {key}: {value}")
    else:
        print("  constraints: -")
    print()
