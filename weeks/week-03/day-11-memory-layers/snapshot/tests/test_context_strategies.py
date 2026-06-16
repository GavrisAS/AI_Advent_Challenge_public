from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ai_advent_agent.agent import SimpleAgent
from ai_advent_agent.config import AgentConfig
from ai_advent_agent.context_management import JsonBranchesStore, JsonFactsStore
from ai_advent_agent.llm_client import ChatResult, Message
from ai_advent_agent.scenarios import scenario_context_strategies_comparison
from ai_advent_agent.storage import JsonContextStore
from ai_advent_agent.token_report import TokenReportStore


class SequencedFakeClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[list[Message]] = []

    def chat(self, messages: list[Message], config: AgentConfig) -> ChatResult:
        self.calls.append([message.copy() for message in messages])
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        return ChatResult(
            content=self.responses[index],
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            elapsed_seconds=0.01,
            model=config.model,
            raw={"fake": True},
        )


class Day10ContextStrategiesTest(unittest.TestCase):
    def test_sliding_window_context_strategy_keeps_only_recent_messages(self) -> None:
        client = SequencedFakeClient(["answer"])
        agent = SimpleAgent(
            client=client,
            config=AgentConfig(
                system_prompt="system",
                context_strategy="sliding_window",
                recent_messages_limit=2,
            ),
        )
        agent.messages.extend(
            [
                {"role": "user", "content": "old user"},
                {"role": "assistant", "content": "old assistant"},
                {"role": "user", "content": "recent user"},
                {"role": "assistant", "content": "recent assistant"},
            ]
        )

        agent.ask("new question")

        sent_contents = [message["content"] for message in client.calls[0]]
        self.assertNotIn("old user", sent_contents)
        self.assertIn("recent user", sent_contents)
        self.assertEqual(
            [message["role"] for message in agent.get_history()],
            ["system", "user", "assistant", "user", "assistant"],
        )

    def test_sticky_facts_are_saved_and_injected_into_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            facts_path = Path(tmp_dir) / "facts.json"
            client = SequencedFakeClient(
                [
                    json.dumps(
                        {
                            "goal": "Собрать ТЗ на AI-агента",
                            "constraints": "Не делать commit без подтверждения",
                            "preferences": "",
                            "decisions": "",
                            "agreements": "",
                            "user_data": "",
                        },
                        ensure_ascii=False,
                    ),
                    "answer",
                ]
            )
            agent = SimpleAgent(
                client=client,
                config=AgentConfig(system_prompt="system", context_strategy="sticky_facts"),
                facts_store=JsonFactsStore(facts_path),
            )

            agent.ask("Цель: собрать ТЗ. Ограничение: без commit.")

            self.assertEqual(len(client.calls), 2)
            main_call_text = "\n".join(message["content"] for message in client.calls[1])
            self.assertIn("Sticky facts", main_call_text)
            self.assertIn("Собрать ТЗ", main_call_text)
            facts_payload = json.loads(facts_path.read_text(encoding="utf-8"))
            self.assertEqual(facts_payload["facts"]["goal"], "Собрать ТЗ на AI-агента")

    def test_facts_json_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "facts.json"
            store = JsonFactsStore(path)
            facts = store.load()
            facts.merge({"goal": "Собрать ТЗ", "constraints": "Без приватных файлов"})
            store.save(facts)

            restored = store.load()

            self.assertEqual(restored.values["goal"], "Собрать ТЗ")
            self.assertEqual(restored.values["constraints"], "Без приватных файлов")

    def test_branching_creates_checkpoint_two_branches_and_switches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            branches_path = Path(tmp_dir) / "branches.json"
            agent = SimpleAgent(
                client=SequencedFakeClient(["answer"]),
                config=AgentConfig(system_prompt="system", context_strategy="branching"),
                branches_store=JsonBranchesStore(branches_path),
            )
            agent.messages.append({"role": "user", "content": "base"})
            agent.create_checkpoint("base")

            agent.create_branch("branch-a")
            agent.messages.append({"role": "assistant", "content": "A"})
            agent.create_branch("branch-b")
            agent.messages.append({"role": "assistant", "content": "B"})

            agent.switch_branch("branch-a")

            self.assertEqual(agent.branch_memory.active_branch, "branch-a")
            contents = [message["content"] for message in agent.get_history()]
            self.assertIn("base", contents)
            self.assertNotIn("B", contents)
            payload = json.loads(branches_path.read_text(encoding="utf-8"))
            self.assertIn("branch-a", payload["branches"])
            self.assertIn("branch-b", payload["branches"])

    def test_day10_scenario_writes_token_reports_without_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "agent-context"

            scenario_context_strategies_comparison(
                recent_messages_limit=6,
                context_window=10_000,
                max_tokens=500,
                output_dir=output_dir,
            )

            reports = TokenReportStore(output_dir / "token_reports.jsonl").load_all()
            self.assertEqual(len(reports), 3)
            self.assertTrue(all(not report.summary_active for report in reports))
            self.assertTrue((output_dir / "facts.json").exists())
            self.assertTrue((output_dir / "branches.json").exists())

    def test_sticky_facts_and_token_report_files_are_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            facts_path = Path(tmp_dir) / "facts.json"
            context_path = Path(tmp_dir) / "messages.json"
            reports_path = Path(tmp_dir) / "reports.jsonl"
            client = SequencedFakeClient(
                [
                    json.dumps(
                        {
                            "goal": "ТЗ",
                            "constraints": "",
                            "preferences": "",
                            "decisions": "",
                            "agreements": "",
                            "user_data": "",
                        }
                    ),
                    "answer",
                ]
            )
            agent = SimpleAgent(
                client=client,
                config=AgentConfig(system_prompt="system", context_strategy="sticky_facts"),
                context_store=JsonContextStore(context_path),
                facts_store=JsonFactsStore(facts_path),
                token_report_store=TokenReportStore(reports_path),
            )

            agent.ask("Цель: ТЗ")

            self.assertTrue(facts_path.exists())
            self.assertTrue(reports_path.exists())
            self.assertEqual(len(TokenReportStore(reports_path).load_all()), 1)


if __name__ == "__main__":
    unittest.main()
