from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai_advent_agent.agent import SimpleAgent
from ai_advent_agent.commands import (
    CommandCompleter,
    CommandContext,
    CommandRouter,
    build_command_registry,
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

    def test_completer_suggestions(self) -> None:
        completer = CommandCompleter(build_command_registry())

        slash = {item.text for item in completer.suggest("/")}
        filtered = {item.text for item in completer.suggest("/m")}
        memory = {item.text for item in completer.suggest("/memory ")}

        self.assertIn("/status", slash)
        self.assertIn("/memory", slash)
        self.assertEqual(filtered, {"/memory"})
        self.assertIn("/memory short", memory)
        self.assertIn("/memory add short", memory)
        self.assertIn("/memory set working", memory)
        self.assertIn("/memory reset all --yes", memory)


if __name__ == "__main__":
    unittest.main()
