from __future__ import annotations

import importlib
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from ai_advent_agent.agent import SimpleAgent
from ai_advent_agent.commands import (
    CommandCompleter,
    CommandContext,
    CommandRegistry,
    CommandRouter,
    CommandSpec,
    CommandSuggestion,
    build_command_completer,
    build_command_registry,
    should_open_followup_completion,
    should_open_nested_completion,
)
from ai_advent_agent.config import AgentConfig
from ai_advent_agent.context_management import JsonBranchesStore, JsonFactsStore
from ai_advent_agent.invariants import InvariantEventStore, JsonInvariantStore
from ai_advent_agent.llm_client import ChatResult, Message
from ai_advent_agent.memory_layers import (
    JsonKeyValueMemoryStore,
    JsonShortTermMemoryStore,
    MemoryEventStore,
)
from ai_advent_agent.storage import JsonContextStore, JsonSummaryStore
from ai_advent_agent.task_state import JsonTaskStateStore, TaskEventStore
from ai_advent_agent.token_report import TokenReportStore
from ai_advent_agent.user_profile import JsonUserProfileStore, UserProfileEventStore


class FakeClient:
    def chat(self, messages: list[Message], config: AgentConfig) -> ChatResult:
        return ChatResult(
            content="fake answer",
            finish_reason="stop",
            usage={},
            elapsed_seconds=0.01,
            model=config.model,
            raw={"fake": True},
        )


def build_agent(tmp_dir: Path) -> SimpleAgent:
    return SimpleAgent(
        client=FakeClient(),
        config=AgentConfig(system_prompt="system"),
        context_store=JsonContextStore(tmp_dir / "messages.json"),
        summary_store=JsonSummaryStore(tmp_dir / "summary.json"),
        facts_store=JsonFactsStore(tmp_dir / "facts.json"),
        branches_store=JsonBranchesStore(tmp_dir / "branches.json"),
        short_term_memory_store=JsonShortTermMemoryStore(tmp_dir / "short_term_memory.json"),
        working_memory_store=JsonKeyValueMemoryStore(
            tmp_dir / "working_memory.json",
            layer="working",
        ),
        long_term_memory_store=JsonKeyValueMemoryStore(
            tmp_dir / "long_term_memory.json",
            layer="long_term",
        ),
        memory_event_store=MemoryEventStore(tmp_dir / "memory_events.jsonl"),
        user_profile_store=JsonUserProfileStore(tmp_dir / "user_profiles.json"),
        profile_event_store=UserProfileEventStore(tmp_dir / "profile_events.jsonl"),
        invariant_store=JsonInvariantStore(tmp_dir / "invariants.json"),
        invariant_event_store=InvariantEventStore(tmp_dir / "invariant_events.jsonl"),
        task_state_store=JsonTaskStateStore(tmp_dir / "task_state.json"),
        task_event_store=TaskEventStore(tmp_dir / "task_events.jsonl"),
        token_report_store=TokenReportStore(tmp_dir / "token_reports.jsonl"),
    )


class CommandRegistryTest(unittest.TestCase):
    def test_commands_package_public_api_and_modules_are_importable(self) -> None:
        for module_name in [
            "ai_advent_agent.commands",
            "ai_advent_agent.commands.registry",
            "ai_advent_agent.commands.router",
            "ai_advent_agent.commands.completer",
            "ai_advent_agent.commands.builders",
        ]:
            self.assertIsNotNone(importlib.import_module(module_name))

        registry = build_command_registry()
        self.assertIsInstance(registry, CommandRegistry)
        self.assertIsInstance(build_command_completer(registry), CommandCompleter)

    def test_registry_contains_top_level_commands(self) -> None:
        registry = build_command_registry()

        top_level = {spec.slash_path for spec in registry.top_level()}

        self.assertEqual(
            top_level,
            {
                "/branch",
                "/config",
                "/exit",
                "/file",
                "/help",
                "/memory",
                "/profile",
                "/task",
                "/invariant",
                "/session",
                "/status",
                "/storage",
            },
        )

    def test_router_handles_new_commands_and_plain_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = build_agent(Path(tmp))
            router = CommandRouter(build_command_registry())
            context = CommandContext(agent=agent, show_metadata=False)

            self.assertTrue(router.route("/help", context).handled)
            self.assertTrue(router.route("/status context", context).handled)
            self.assertTrue(router.route("/memory working", context).handled)
            self.assertFalse(router.route("обычный пользовательский запрос", context).handled)

    def test_config_is_namespace_not_legacy_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = build_agent(Path(tmp))
            router = CommandRouter(build_command_registry())
            context = CommandContext(agent=agent, show_metadata=False)
            output = io.StringIO()

            with redirect_stdout(output):
                self.assertTrue(router.route("/config", context).handled)
                self.assertTrue(router.route("/config show", context).handled)

            text = output.getvalue()
            self.assertNotIn("Deprecated command", text)
            self.assertIn("Команды /config:", text)
            self.assertIn("Текущая конфигурация:", text)

    def test_memory_set_working_writes_working_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = build_agent(Path(tmp))
            router = CommandRouter(build_command_registry())

            result = router.route(
                "/memory set working key: value",
                CommandContext(agent=agent, show_metadata=False),
            )

            self.assertTrue(result.handled)
            self.assertEqual(agent.working_memory.normalized(), {"key": "value"})

    def test_legacy_aliases_are_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = build_agent(Path(tmp))
            router = CommandRouter(build_command_registry())
            context = CommandContext(agent=agent, show_metadata=False)

            self.assertTrue(router.route("/remember working key: value", context).handled)
            self.assertEqual(agent.working_memory.normalized(), {"key": "value"})
            self.assertTrue(router.route("/facts", context).handled)
            self.assertTrue(router.route("/branches", context).handled)
            self.assertTrue(router.route("/context-mode sliding_window", context).handled)
            self.assertEqual(agent.config.overflow_policy.value, "sliding_window")

    def test_help_legacy_lists_legacy_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = build_agent(Path(tmp))
            router = CommandRouter(build_command_registry())
            context = CommandContext(agent=agent, show_metadata=False)
            output = io.StringIO()

            with redirect_stdout(output):
                self.assertTrue(router.route("/help legacy", context).handled)

            text = output.getvalue()
            self.assertIn("/facts", text)
            self.assertIn("/remember working", text)
            self.assertIn("/context-mode", text)

    def test_root_suggestions_show_only_namespace_commands(self) -> None:
        completer = CommandCompleter(build_command_registry())

        suggestions = completer.suggest("/")
        slash = [item.display_text for item in suggestions]
        branch = next(item for item in suggestions if item.display_text == "/branch")
        exit_item = next(item for item in suggestions if item.display_text == "/exit")

        self.assertEqual(
            slash,
            [
                "/help",
                "/status",
                "/config",
                "/session",
                "/storage",
                "/memory",
                "/profile",
                "/task",
                "/invariant",
                "/branch",
                "/file",
                "/exit",
            ],
        )
        self.assertNotIn("/facts", slash)
        self.assertNotIn("/remember", slash)
        self.assertNotIn("/context", slash)
        self.assertNotIn("/help [group|legacy]", slash)
        self.assertEqual(branch.insert_text, "/branch ")
        self.assertTrue(branch.description)
        self.assertEqual(exit_item.insert_text, "/exit")

    def test_completer_filters_and_inserts_root_group_with_trailing_space(self) -> None:
        completer = CommandCompleter(build_command_registry())

        filtered = completer.suggest("/br")

        self.assertEqual([item.display_text for item in filtered], ["/branch"])
        self.assertEqual(filtered[0].insert_text, "/branch ")

    def test_completer_suggestions_for_nested_groups(self) -> None:
        completer = CommandCompleter(build_command_registry())

        branch_suggestions = completer.suggest("/branch ")
        memory_suggestions = completer.suggest("/memory ")
        task_suggestions = completer.suggest("/task ")
        invariant_suggestions = completer.suggest("/invariant ")
        branch = {item.display_text: item for item in branch_suggestions}
        memory = {item.display_text: item.insert_text for item in memory_suggestions}
        config = {item.display_text: item.insert_text for item in completer.suggest("/config ")}
        status = {item.display_text: item.insert_text for item in completer.suggest("/status ")}

        self.assertEqual(
            [item.display_text for item in branch_suggestions],
            ["/branch list", "/branch checkpoint", "/branch create", "/branch switch"],
        )
        self.assertTrue(all(item.description for item in branch.values()))
        self.assertEqual(branch["/branch checkpoint"].insert_text, "/branch checkpoint ")
        self.assertEqual(
            [item.display_text for item in memory_suggestions],
            [
                "/memory short",
                "/memory working",
                "/memory long",
                "/memory summary",
                "/memory facts",
                "/memory add",
                "/memory set",
                "/memory forget",
                "/memory reset",
            ],
        )
        profile_suggestions = completer.suggest("/profile ")
        self.assertEqual(
            [item.display_text for item in profile_suggestions],
            [
                "/profile list",
                "/profile active",
                "/profile show",
                "/profile create",
                "/profile use",
                "/profile set",
                "/profile reset",
            ],
        )
        self.assertEqual(memory["/memory set"], "/memory set ")
        self.assertEqual(memory["/memory reset"], "/memory reset ")
        self.assertEqual(
            [item.display_text for item in task_suggestions],
            [
                "/task status",
                "/task start",
                "/task transition",
                "/task stage",
                "/task approve-plan",
                "/task pass-validation",
                "/task step",
                "/task expected-action",
                "/task next",
                "/task pause",
                "/task resume",
                "/task complete",
                "/task reset",
                "/task metadata",
            ],
        )
        self.assertEqual(
            [item.display_text for item in invariant_suggestions],
            [
                "/invariant list",
                "/invariant show",
                "/invariant add",
                "/invariant rationale",
                "/invariant pattern",
                "/invariant check",
                "/invariant enable",
                "/invariant disable",
                "/invariant remove",
                "/invariant reset",
            ],
        )
        self.assertIn("/config show", config)
        self.assertIn("/config strategy", config)
        self.assertEqual(config["/config strategy"], "/config strategy ")
        self.assertEqual(config["/config summary"], "/config summary ")
        self.assertEqual(config["/config overflow"], "/config overflow ")
        self.assertIn("/status context", status)
        self.assertIn("/status tokens", status)

    def test_equal_order_suggestions_fall_back_to_display_text(self) -> None:
        registry = CommandRegistry()
        registry.register(CommandSpec(("zeta",), "/zeta", "Z.", order=10))
        registry.register(CommandSpec(("alpha",), "/alpha", "A.", order=10))

        suggestions = CommandCompleter(registry).suggest("/")

        self.assertEqual([item.display_text for item in suggestions], ["/alpha", "/zeta"])

    def test_completer_suggests_static_arguments(self) -> None:
        completer = CommandCompleter(build_command_registry())

        cases = {
            "/config strategy ": [
                ("direct", "/config strategy direct", "Быстрый прямой ответ."),
                ("step_by_step", "/config strategy step_by_step", "Пошаговое рассуждение."),
            ],
            "/config summary ": [
                ("off", "/config summary off", "Не использовать summary memory."),
                ("llm", "/config summary llm", "Использовать LLM summary memory."),
            ],
            "/config overflow ": [
                ("error", "/config overflow error", "Ошибка при переполнении контекста."),
                ("no_trim", "/config overflow no_trim", "Не обрезать контекст."),
                (
                    "sliding_window",
                    "/config overflow sliding_window",
                    "Использовать sliding window при переполнении.",
                ),
            ],
            "/memory set ": [
                ("working", "/memory set working ", "Сохранить key-value в working memory."),
                ("long", "/memory set long ", "Сохранить key-value в long-term memory."),
            ],
            "/memory forget ": [
                ("working", "/memory forget working ", "Удалить key из working memory."),
                ("long", "/memory forget long ", "Удалить key из long-term memory."),
            ],
            "/memory add ": [
                ("short", "/memory add short ", "Добавить short-term note."),
            ],
            "/memory reset ": [
                ("working", "/memory reset working", "Очистить working memory."),
                ("all --yes", "/memory reset all --yes", "Очистить все memory layers."),
            ],
            "/profile set ": [
                ("language", "/profile set language ", "Язык ответов."),
                ("style", "/profile set style ", "Стиль ответов."),
                ("format", "/profile set format ", "Формат ответов."),
                ("audience", "/profile set audience ", "Целевая аудитория."),
                ("preference", "/profile set preference ", "Добавить preference key-value."),
                ("constraint", "/profile set constraint ", "Добавить constraint key-value."),
            ],
            "/profile reset ": [
                ("active --yes", "/profile reset active --yes", "Очистить активный профиль."),
                ("all --yes", "/profile reset all --yes", "Очистить все профили."),
            ],
            "/task stage ": [
                ("planning", "/task stage planning", "Этап task state machine."),
                ("execution", "/task stage execution", "Этап task state machine."),
                ("validation", "/task stage validation", "Этап task state machine."),
                ("done", "/task stage done", "Этап task state machine."),
            ],
            "/task transition ": [
                ("planning", "/task transition planning", "Этап task state machine."),
                ("execution", "/task transition execution", "Этап task state machine."),
                ("validation", "/task transition validation", "Этап task state machine."),
                ("done", "/task transition done", "Этап task state machine."),
            ],
            "/task reset ": [
                ("--yes", "/task reset --yes", "Подтвердить reset."),
            ],
            "/invariant add ": [
                (
                    "architecture: ",
                    "/invariant add architecture: ",
                    "Категория invariant.",
                ),
                (
                    "technical_decision: ",
                    "/invariant add technical_decision: ",
                    "Категория invariant.",
                ),
                (
                    "stack_constraint: ",
                    "/invariant add stack_constraint: ",
                    "Категория invariant.",
                ),
                (
                    "business_rule: ",
                    "/invariant add business_rule: ",
                    "Категория invariant.",
                ),
            ],
            "/invariant reset ": [
                ("--yes", "/invariant reset --yes", "Подтвердить reset."),
            ],
        }

        for command, expected in cases.items():
            with self.subTest(command=command):
                suggestions = completer.suggest(command)
                self.assertEqual(
                    [
                        (item.display_text, item.insert_text, item.description)
                        for item in suggestions
                    ],
                    expected,
                )
                self.assertTrue(all(item.description for item in suggestions))
                self.assertTrue(all("<" not in item.display_text for item in suggestions))
                self.assertTrue(all("|" not in item.display_text for item in suggestions))

    def test_argument_completion_filters_by_prefix(self) -> None:
        completer = CommandCompleter(build_command_registry())

        suggestions = completer.suggest("/config strategy d")

        self.assertEqual(
            [(item.display_text, item.insert_text) for item in suggestions],
            [("direct", "/config strategy direct")],
        )

    def test_argument_suggestions_can_differ_display_and_insert_text(self) -> None:
        registry = CommandRegistry()
        registry.register(
            CommandSpec(
                ("demo", "reset"),
                "/demo reset",
                "Demo reset.",
                argument_suggestions=(CommandSuggestion("all --yes", "all", "Очистить всё."),),
            )
        )

        suggestions = CommandCompleter(registry).suggest("/demo reset ")

        self.assertEqual(suggestions[0].display_text, "all")
        self.assertEqual(suggestions[0].insert_text, "/demo reset all --yes")
        self.assertEqual(suggestions[0].description, "Очистить всё.")

    def test_argument_completion_does_not_show_placeholders(self) -> None:
        completer = CommandCompleter(build_command_registry())

        suggestions = completer.suggest("/memory set ")
        visible = {item.display_text for item in suggestions}

        self.assertNotIn("<key>: <value>", visible)
        self.assertNotIn("<name>", visible)
        self.assertNotIn("error|no_trim|sliding_window", visible)

    def test_router_handles_commands_with_completed_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = build_agent(Path(tmp))
            router = CommandRouter(build_command_registry())
            context = CommandContext(agent=agent, show_metadata=False)

            self.assertTrue(router.route("/config strategy direct", context).handled)
            self.assertEqual(agent.config.strategy, "direct")
            self.assertTrue(router.route("/config summary off", context).handled)
            self.assertEqual(agent.config.summary_mode, "off")
            self.assertTrue(router.route("/config overflow sliding_window", context).handled)
            self.assertEqual(agent.config.overflow_policy.value, "sliding_window")
            self.assertTrue(router.route("/memory set working key: value", context).handled)
            self.assertEqual(agent.working_memory.normalized(), {"key": "value"})
            self.assertTrue(router.route("/memory reset working", context).handled)
            self.assertEqual(agent.working_memory.normalized(), {})
            self.assertTrue(router.route("/memory set long profile: stable", context).handled)
            self.assertEqual(agent.long_term_memory.normalized(), {"profile": "stable"})
            self.assertTrue(router.route("/memory reset all --yes", context).handled)
            self.assertEqual(agent.long_term_memory.normalized(), {})

    def test_should_open_nested_completion(self) -> None:
        registry = build_command_registry()

        self.assertTrue(should_open_nested_completion("/branch ", registry))
        self.assertTrue(should_open_nested_completion("/memory ", registry))
        self.assertFalse(should_open_nested_completion("/exit", registry))
        self.assertFalse(should_open_nested_completion("обычный текст", registry))

    def test_should_open_followup_completion(self) -> None:
        registry = build_command_registry()

        for command in [
            "/branch ",
            "/memory ",
            "/config strategy ",
            "/config summary ",
            "/config overflow ",
            "/memory set ",
            "/memory forget ",
            "/memory add ",
            "/memory reset ",
            "/profile ",
            "/profile set ",
            "/profile reset ",
            "/task ",
            "/task transition ",
            "/task stage ",
            "/task reset ",
            "/invariant ",
            "/invariant add ",
            "/invariant reset ",
        ]:
            with self.subTest(command=command):
                self.assertTrue(should_open_followup_completion(command, registry))

        for command in ["/exit", "/config show", "обычный текст"]:
            with self.subTest(command=command):
                self.assertFalse(should_open_followup_completion(command, registry))

    def test_profile_commands_update_profiles_without_touching_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            agent = build_agent(tmp_dir)
            router = CommandRouter(build_command_registry())
            context = CommandContext(agent=agent, show_metadata=False)

            self.assertTrue(router.route("/profile create concise_engineer", context).handled)
            self.assertTrue(router.route("/profile set language русский", context).handled)
            self.assertTrue(router.route("/profile set preference length: кратко", context).handled)
            self.assertTrue(
                router.route(
                    "/profile set constraint privacy: не просить секреты",
                    context,
                ).handled
            )

            profile = agent.user_profiles.profiles["concise_engineer"]
            self.assertEqual(agent.user_profiles.active_profile, "concise_engineer")
            self.assertEqual(profile.language, "русский")
            self.assertEqual(profile.preferences, {"length": "кратко"})
            self.assertEqual(profile.constraints, {"privacy": "не просить секреты"})
            self.assertEqual(agent.long_term_memory.normalized(), {})
            self.assertTrue((tmp_dir / "user_profiles.json").exists())
            events = UserProfileEventStore(tmp_dir / "profile_events.jsonl").load_all()
            self.assertEqual(
                [event["action"] for event in events],
                [
                    "create_profile",
                    "set_profile_field",
                    "set_profile_preference",
                    "set_profile_constraint",
                ],
            )

    def test_task_commands_update_task_state_without_touching_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            agent = build_agent(tmp_dir)
            router = CommandRouter(build_command_registry())
            context = CommandContext(agent=agent, show_metadata=False)

            self.assertTrue(router.route("/task start Реализовать Day 13", context).handled)
            self.assertEqual(agent.task_state.stage, "planning")
            self.assertTrue(router.route("/task step Добавить команды /task", context).handled)
            self.assertTrue(router.route("/task expected-action Запустить tests", context).handled)
            self.assertTrue(router.route("/task transition execution", context).handled)
            self.assertEqual(agent.task_state.stage, "planning")
            self.assertTrue(router.route("/task approve-plan", context).handled)
            self.assertTrue(agent.task_state.plan_approved)
            self.assertTrue(router.route("/task stage execution", context).handled)
            self.assertTrue(router.route("/task pause", context).handled)
            self.assertEqual(agent.task_state.stage, "execution")
            self.assertTrue(agent.task_state.paused)
            self.assertTrue(router.route("/task transition validation", context).handled)
            self.assertEqual(agent.task_state.stage, "execution")
            self.assertTrue(router.route("/task resume", context).handled)
            self.assertFalse(agent.task_state.paused)
            self.assertTrue(router.route("/task next", context).handled)
            self.assertEqual(agent.task_state.stage, "validation")
            self.assertTrue(router.route("/task metadata check: pytest", context).handled)
            self.assertEqual(agent.task_state.metadata, {"check": "pytest"})
            self.assertTrue(router.route("/task complete", context).handled)
            self.assertFalse(agent.task_state.done)
            self.assertTrue(router.route("/task pass-validation", context).handled)
            self.assertTrue(agent.task_state.validation_passed)
            self.assertTrue(router.route("/task complete", context).handled)
            self.assertTrue(agent.task_state.done)
            self.assertTrue(router.route("/task reset --yes", context).handled)
            self.assertFalse(agent.task_state.active)

            events = TaskEventStore(tmp_dir / "task_events.jsonl").load_all()
            self.assertIn("pause_task", [event["action"] for event in events])
            self.assertIn("invalid_transition", [event["action"] for event in events])
            self.assertEqual(agent.working_memory.normalized(), {})

    def test_invalid_task_transition_prints_reason_and_writes_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            agent = build_agent(tmp_dir)
            router = CommandRouter(build_command_registry())
            context = CommandContext(agent=agent, show_metadata=False)
            output = io.StringIO()

            router.route("/task start Demo", context)
            with redirect_stdout(output):
                result = router.route("/task transition execution", context)

            self.assertTrue(result.handled)
            text = output.getvalue()
            self.assertIn("Переход отклонён: planning → execution.", text)
            self.assertIn("/task approve-plan", text)
            self.assertEqual(agent.task_state.stage, "planning")
            events = TaskEventStore(tmp_dir / "task_events.jsonl").load_all()
            self.assertEqual(events[-1]["action"], "invalid_transition")
            self.assertEqual(events[-1]["target_stage"], "execution")

    def test_profile_set_without_active_profile_prints_create_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = build_agent(Path(tmp))
            output = io.StringIO()

            with redirect_stdout(output):
                result = CommandRouter(build_command_registry()).route(
                    "/profile set language русский",
                    CommandContext(agent=agent, show_metadata=False),
                )

            self.assertTrue(result.handled)
            self.assertIn("Сначала создайте профиль: /profile create <name>", output.getvalue())
            self.assertEqual(agent.user_profiles.profiles, {})

    def test_profile_reset_active_keeps_record_and_reset_all_keeps_event_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            agent = build_agent(tmp_dir)
            router = CommandRouter(build_command_registry())
            context = CommandContext(agent=agent, show_metadata=False)

            router.route("/profile create teacher", context)
            router.route("/profile set style подробно", context)
            router.route("/profile reset active --yes", context)

            self.assertEqual(agent.user_profiles.active_profile, "teacher")
            self.assertIn("teacher", agent.user_profiles.profiles)
            self.assertFalse(agent.user_profiles.profiles["teacher"].active)

            router.route("/profile reset all --yes", context)

            self.assertEqual(agent.user_profiles.active_profile, "")
            self.assertEqual(agent.user_profiles.profiles, {})
            events = UserProfileEventStore(tmp_dir / "profile_events.jsonl").load_all()
            self.assertIn("reset_profile", [event["action"] for event in events])
            self.assertEqual(events[-1]["action"], "reset_all_profiles")

    def test_profile_dynamic_completion_uses_context_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = build_agent(Path(tmp))
            agent.create_profile("concise_engineer")
            agent.create_profile("teacher")
            context = CommandContext(agent=agent, show_metadata=False)
            completer = CommandCompleter(build_command_registry(), context)

            suggestions = completer.suggest("/profile use c")

            self.assertEqual(
                [(item.display_text, item.insert_text) for item in suggestions],
                [("concise_engineer", "/profile use concise_engineer")],
            )

    def test_invariant_commands_update_invariants_without_touching_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            agent = build_agent(tmp_dir)
            router = CommandRouter(build_command_registry())
            context = CommandContext(agent=agent, show_metadata=False)

            self.assertTrue(
                router.route(
                    "/invariant add architecture: Не менять storage на SQLite",
                    context,
                ).handled
            )
            self.assertTrue(
                router.route(
                    "/invariant rationale architecture-001: JSON проще проверять в курсе",
                    context,
                ).handled
            )
            self.assertTrue(
                router.route(
                    "/invariant pattern architecture-001: перейти на sqlite",
                    context,
                ).handled
            )
            self.assertEqual(len(agent.invariants.all()), 1)
            self.assertEqual(agent.invariants.all()[0].reject_patterns, ["перейти на sqlite"])
            self.assertTrue(
                router.route("/invariant check Давай перейти на SQLite", context).handled
            )
            self.assertTrue(router.route("/invariant disable architecture-001", context).handled)
            self.assertFalse(agent.invariants.enabled())
            self.assertTrue(router.route("/invariant enable architecture-001", context).handled)
            self.assertTrue(agent.invariants.enabled())
            self.assertTrue(router.route("/invariant remove architecture-001", context).handled)
            self.assertEqual(agent.invariants.all(), [])
            self.assertEqual(agent.working_memory.normalized(), {})

            events = InvariantEventStore(tmp_dir / "invariant_events.jsonl").load_all()
            self.assertIn("add_invariant", [event["action"] for event in events])
            self.assertIn("check_conflict", [event["action"] for event in events])

    def test_invariant_dynamic_completion_uses_context_invariant_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = build_agent(Path(tmp))
            agent.add_invariant("architecture", "Не менять storage на SQLite")
            context = CommandContext(agent=agent, show_metadata=False)
            completer = CommandCompleter(build_command_registry(), context)

            self.assertEqual(
                [
                    (item.display_text, item.insert_text)
                    for item in completer.suggest("/invariant show a")
                ],
                [("architecture-001", "/invariant show architecture-001")],
            )
            self.assertEqual(
                [
                    (item.display_text, item.insert_text)
                    for item in completer.suggest("/invariant pattern a")
                ],
                [("architecture-001:", "/invariant pattern architecture-001: ")],
            )


if __name__ == "__main__":
    unittest.main()
