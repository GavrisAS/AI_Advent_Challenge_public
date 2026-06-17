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
    build_command_completer,
    build_command_registry,
    should_open_nested_completion,
)
from ai_advent_agent.config import AgentConfig
from ai_advent_agent.context_management import JsonBranchesStore, JsonFactsStore
from ai_advent_agent.llm_client import ChatResult, Message
from ai_advent_agent.memory_layers import (
    JsonKeyValueMemoryStore,
    JsonShortTermMemoryStore,
    MemoryEventStore,
)
from ai_advent_agent.storage import JsonContextStore, JsonSummaryStore
from ai_advent_agent.token_report import TokenReportStore


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
        slash = {item.display_text for item in suggestions}
        branch = next(item for item in suggestions if item.display_text == "/branch")
        exit_item = next(item for item in suggestions if item.display_text == "/exit")

        self.assertEqual(
            slash,
            {
                "/branch",
                "/config",
                "/exit",
                "/file",
                "/help",
                "/memory",
                "/session",
                "/status",
                "/storage",
            },
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

        branch = {item.display_text: item for item in completer.suggest("/branch ")}
        memory = {item.display_text: item.insert_text for item in completer.suggest("/memory ")}
        config = {item.display_text: item.insert_text for item in completer.suggest("/config ")}
        status = {item.display_text: item.insert_text for item in completer.suggest("/status ")}

        self.assertIn("/branch checkpoint", branch)
        self.assertIn("/branch create", branch)
        self.assertIn("/branch list", branch)
        self.assertIn("/branch switch", branch)
        self.assertTrue(all(item.description for item in branch.values()))
        self.assertEqual(branch["/branch checkpoint"].insert_text, "/branch checkpoint ")
        self.assertIn("/memory short", memory)
        self.assertIn("/memory summary", memory)
        self.assertIn("/memory facts", memory)
        self.assertIn("/memory working", memory)
        self.assertIn("/memory long", memory)
        self.assertIn("/memory add short", memory)
        self.assertIn("/memory set working", memory)
        self.assertIn("/memory set long", memory)
        self.assertIn("/memory forget working", memory)
        self.assertIn("/memory forget long", memory)
        self.assertIn("/memory reset working", memory)
        self.assertIn("/memory reset all --yes", memory)
        self.assertEqual(memory["/memory set working"], "/memory set working ")
        self.assertEqual(memory["/memory reset all --yes"], "/memory reset all --yes")
        self.assertIn("/config show", config)
        self.assertIn("/config strategy", config)
        self.assertEqual(config["/config overflow"], "/config overflow ")
        self.assertIn("/status context", status)
        self.assertIn("/status tokens", status)

    def test_should_open_nested_completion(self) -> None:
        registry = build_command_registry()

        self.assertTrue(should_open_nested_completion("/branch ", registry))
        self.assertTrue(should_open_nested_completion("/memory ", registry))
        self.assertFalse(should_open_nested_completion("/exit", registry))
        self.assertFalse(should_open_nested_completion("обычный текст", registry))


if __name__ == "__main__":
    unittest.main()
