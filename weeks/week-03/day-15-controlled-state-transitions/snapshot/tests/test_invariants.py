from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai_advent_agent.agent import SimpleAgent
from ai_advent_agent.config import AgentConfig
from ai_advent_agent.context_management import JsonFactsStore
from ai_advent_agent.invariants import (
    InvariantEventStore,
    InvariantSet,
    JsonInvariantStore,
    build_invariants_prompt_message,
)
from ai_advent_agent.llm_client import ChatResult, Message
from ai_advent_agent.memory_layers import JsonKeyValueMemoryStore, JsonShortTermMemoryStore
from ai_advent_agent.scenarios import scenario_state_invariants_demo
from ai_advent_agent.storage import JsonContextStore
from ai_advent_agent.task_state import JsonTaskStateStore
from ai_advent_agent.token_report import TokenReportStore
from ai_advent_agent.user_profile import JsonUserProfileStore


class CountingClient:
    def __init__(self) -> None:
        self.calls = 0
        self.last_messages: list[Message] = []

    def chat(self, messages: list[Message], config: AgentConfig) -> ChatResult:
        self.calls += 1
        self.last_messages = [message.copy() for message in messages]
        return ChatResult(
            content="fake answer",
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
            elapsed_seconds=0.01,
            model=config.model,
            raw={"fake": True},
        )


def build_agent(tmp_dir: Path, client: CountingClient | None = None) -> SimpleAgent:
    return SimpleAgent(
        client=client or CountingClient(),
        config=AgentConfig(system_prompt="system"),
        context_store=JsonContextStore(tmp_dir / "messages.json"),
        facts_store=JsonFactsStore(tmp_dir / "facts.json"),
        short_term_memory_store=JsonShortTermMemoryStore(tmp_dir / "short_term_memory.json"),
        working_memory_store=JsonKeyValueMemoryStore(
            tmp_dir / "working_memory.json",
            layer="working",
        ),
        long_term_memory_store=JsonKeyValueMemoryStore(
            tmp_dir / "long_term_memory.json",
            layer="long_term",
        ),
        user_profile_store=JsonUserProfileStore(tmp_dir / "user_profiles.json"),
        invariant_store=JsonInvariantStore(tmp_dir / "invariants.json"),
        invariant_event_store=InvariantEventStore(tmp_dir / "invariant_events.jsonl"),
        task_state_store=JsonTaskStateStore(tmp_dir / "task_state.json"),
        token_report_store=TokenReportStore(tmp_dir / "token_reports.jsonl"),
    )


class InvariantModelTest(unittest.TestCase):
    def test_storage_validation_id_generation_and_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            store = JsonInvariantStore(tmp_dir / "invariants.json")
            events = InvariantEventStore(tmp_dir / "invariant_events.jsonl")
            invariants = InvariantSet()

            first = invariants.add("architecture", "Не менять JSON storage на SQLite")
            second = invariants.add("technical_decision", "Prompt order должен быть стабильным")
            stack = invariants.add("stack_constraint", "Использовать Python 3.14")
            business = invariants.add("business_rule", "Offline demo не требует API key")
            invariants.add_reject_pattern(first.id, "перейти на sqlite")
            invariants.set_rationale(first.id, "Снапшоты должны быть читаемыми.")
            invariants.set_enabled(second.id, False)
            removed = invariants.remove_reject_pattern(first.id, "перейти на sqlite")

            self.assertEqual(first.id, "architecture-001")
            self.assertEqual(second.id, "decision-001")
            self.assertEqual(stack.id, "stack-001")
            self.assertEqual(business.id, "business-001")
            self.assertTrue(removed)

            store.save(invariants)
            loaded = store.load()
            self.assertEqual(
                [item.id for item in loaded.all()],
                [
                    "architecture-001",
                    "business-001",
                    "decision-001",
                    "stack-001",
                ],
            )
            events.append(action="add_invariant", invariant=first)
            events.append(
                action="remove_reject_pattern",
                invariant=first,
                value="перейти на sqlite",
            )
            self.assertEqual(len(events.load_all()), 2)

    def test_strict_validation_rejects_invalid_payload(self) -> None:
        cases = [
            lambda: InvariantSet().add("bad", "text"),
            lambda: InvariantSet().add("architecture", ""),
            lambda: InvariantSet.from_dict({"schema_version": 999, "invariants": []}),
            lambda: InvariantSet.from_dict(
                {
                    "schema_version": 1,
                    "invariants": [
                        {
                            "id": "architecture-001",
                            "category": "architecture",
                            "text": "x",
                            "reject_patterns": [""],
                        }
                    ],
                }
            ),
        ]
        for factory in cases:
            with self.subTest(factory=factory), self.assertRaises(ValueError):
                factory()

    def test_conflict_logic_case_insensitive_multiple_and_disabled(self) -> None:
        invariants = InvariantSet()
        first = invariants.add("architecture", "Не мигрировать storage на SQLite")
        second = invariants.add("business_rule", "Не требовать API key для offline demo")
        third = invariants.add("stack_constraint", "Использовать uv")
        invariants.add_reject_pattern(first.id, "перейти на sqlite")
        invariants.add_reject_pattern(second.id, "нужен api key")
        invariants.add_reject_pattern(third.id, "pip install")
        invariants.set_enabled(third.id, False)

        self.assertEqual(invariants.check_conflicts("обычный запрос"), [])
        conflicts = invariants.check_conflicts(
            "Давай перейти на SQLite, а для offline demo нужен API key."
        )

        self.assertEqual(
            [conflict.invariant_id for conflict in conflicts],
            [
                "architecture-001",
                "business-001",
            ],
        )
        self.assertEqual(invariants.check_conflicts("pip install pytest"), [])

    def test_prompt_builder_omits_empty_and_counts_enabled_only(self) -> None:
        invariants = InvariantSet()
        message, tokens, count = build_invariants_prompt_message(invariants)
        self.assertIsNone(message)
        self.assertEqual(tokens, 0)
        self.assertEqual(count, 0)

        first = invariants.add("architecture", "Не менять storage")
        second = invariants.add("business_rule", "Offline без API")
        invariants.set_enabled(second.id, False)
        message, tokens, count = build_invariants_prompt_message(invariants)

        self.assertIsNotNone(message)
        self.assertGreater(tokens, 0)
        self.assertEqual(count, 1)
        self.assertIn(first.id, message["content"] if message is not None else "")
        self.assertNotIn(second.id, message["content"] if message is not None else "")


class InvariantAgentTest(unittest.TestCase):
    def test_prompt_order_places_invariants_after_system_before_profile_memory_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = CountingClient()
            agent = build_agent(Path(tmp), client)
            agent.add_invariant("architecture", "Не менять storage")
            agent.create_profile("default")
            agent.set_profile_preference("style", "кратко")
            agent.remember_long("language", "русский")
            agent.remember_working("task", "проверить prompt order")
            agent.remember_short("Последнее уточнение: показать полный порядок prompt.")
            agent.start_task("Day 14")

            response = agent.ask("Собери следующий шаг")

            self.assertEqual(response.content, "fake answer")
            self.assertEqual(client.calls, 1)
            self.assertEqual(
                response.token_report.prompt_assembly_order,
                [
                    "system",
                    "invariants",
                    "user_profile",
                    "long_term_memory",
                    "working_memory",
                    "task_state",
                    "short_term_memory",
                    "current_user",
                ],
            )
            self.assertTrue(response.token_report.invariants_active)

    def test_conflict_path_refuses_locally_without_history_or_api_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = CountingClient()
            tmp_dir = Path(tmp)
            agent = build_agent(tmp_dir, client)
            agent.add_invariant("architecture", "Не менять storage на SQLite")
            agent.add_invariant_pattern("architecture-001", "перейти на sqlite")
            before = agent.get_history()

            response = agent.ask("Давай перейти на SQLite прямо сейчас")

            self.assertEqual(client.calls, 0)
            self.assertEqual(response.finish_reason, "invariant_conflict")
            self.assertIn("Запрос отклонён", response.content)
            self.assertEqual(response.usage["total_tokens"], 0)
            self.assertEqual(agent.get_history(), before)
            self.assertTrue(response.token_report.invariant_conflict)
            self.assertEqual(response.token_report.invariant_conflict_count, 1)
            self.assertEqual(response.token_report.total_tokens_actual, 0)
            reports = TokenReportStore(tmp_dir / "token_reports.jsonl").load_all()
            self.assertEqual(len(reports), 1)
            events = InvariantEventStore(tmp_dir / "invariant_events.jsonl").load_all()
            self.assertEqual(events[-1]["action"], "check_conflict")
            self.assertEqual(events[-1]["conflict_count"], 1)

    def test_state_invariants_demo_works_without_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            output_dir = tmp_dir / "agent-context"
            results_file = tmp_dir / "results" / "day-14-state-invariants.md"

            scenario_state_invariants_demo(
                output_dir=output_dir,
                results_file=results_file,
                context_window=10_000,
                max_tokens=500,
            )

            for name in [
                "invariants.json",
                "invariant_events.jsonl",
                "token_reports.jsonl",
                "prompt_without_invariants.json",
                "prompt_with_invariants.json",
                "prompt_conflict_preflight.json",
                "local_refusal.txt",
            ]:
                self.assertTrue((output_dir / name).exists())
            self.assertIn("State Invariants", results_file.read_text(encoding="utf-8"))
            self.assertIn("LLM API не вызывался", (output_dir / "local_refusal.txt").read_text())


if __name__ == "__main__":
    unittest.main()
