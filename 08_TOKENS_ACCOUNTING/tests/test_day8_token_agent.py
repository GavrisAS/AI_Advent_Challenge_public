from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from ai_advent_agent.agent import ContextOverflowError, SimpleAgent, STEP_BY_STEP_SUFFIX
from ai_advent_agent.config import AgentConfig, ContextOverflowPolicy
from ai_advent_agent.llm_client import ChatResult, Message
from ai_advent_agent.storage import JsonContextStore
from ai_advent_agent.token_counter import ApproxTokenCounter
from ai_advent_agent.token_report import TokenReportStore


class FakeClient:
    def __init__(self, content: str = "fake answer") -> None:
        self.content = content
        self.calls: list[list[Message]] = []

    def chat(self, messages: list[Message], config: AgentConfig) -> ChatResult:
        self.calls.append([message.copy() for message in messages])
        return ChatResult(
            content=self.content,
            finish_reason="stop",
            usage={
                "prompt_tokens": 123,
                "completion_tokens": 45,
                "total_tokens": 168,
            },
            elapsed_seconds=0.25,
            model=config.model,
            raw={"fake": True},
        )


class Day8AgentTest(unittest.TestCase):
    def test_agent_saves_messages_and_token_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            context_path = Path(tmp_dir) / "messages.json"
            report_path = Path(tmp_dir) / "reports.jsonl"
            agent = SimpleAgent(
                client=FakeClient(),
                config=AgentConfig(system_prompt="system"),
                context_store=JsonContextStore(context_path),
                token_report_store=TokenReportStore(report_path),
            )

            response = agent.ask("Привет")

            payload = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["message_count"], 3)
            self.assertEqual([item["role"] for item in payload["messages"]], ["system", "user", "assistant"])
            self.assertEqual(response.token_report.prompt_tokens_actual, 123)
            self.assertEqual(response.token_report.completion_tokens_actual, 45)
            self.assertTrue(report_path.exists())
            reports = TokenReportStore(report_path).load_all()
            self.assertEqual(len(reports), 1)
            self.assertEqual(reports[0].total_tokens_actual, 168)

    def test_agent_restores_context_on_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "context.json"
            first_agent = SimpleAgent(
                client=FakeClient(),
                config=AgentConfig(system_prompt="system"),
                context_store=JsonContextStore(path),
            )
            first_agent.ask("Меня зовут Алексей")

            second_client = FakeClient()
            second_agent = SimpleAgent(
                client=second_client,
                config=AgentConfig(system_prompt="system"),
                context_store=JsonContextStore(path),
            )

            restored_history = second_agent.get_history()
            self.assertEqual(len(restored_history), 3)
            self.assertEqual(restored_history[1]["content"], "Меня зовут Алексей")

            second_agent.ask("Как меня зовут?")
            self.assertEqual(len(second_client.calls), 1)
            sent_messages = second_client.calls[0]
            self.assertEqual([item["role"] for item in sent_messages], ["system", "user", "assistant", "user"])
            self.assertIn("Меня зовут Алексей", sent_messages[1]["content"])

    def test_step_by_step_strategy_is_persisted_as_sent_to_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "context.json"
            agent = SimpleAgent(
                client=FakeClient(),
                config=AgentConfig(system_prompt="system", strategy="step_by_step"),
                context_store=JsonContextStore(path),
            )
            agent.ask("Реши задачу")

            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(payload["messages"][1]["content"].startswith("Реши задачу"))
            self.assertIn(STEP_BY_STEP_SUFFIX, payload["messages"][1]["content"])

    def test_overflow_error_policy_does_not_call_client_or_save_user_message(self) -> None:
        client = FakeClient()
        config = AgentConfig(
            system_prompt="system",
            context_window_tokens=30,
            max_tokens=20,
            overflow_policy=ContextOverflowPolicy.ERROR,
        )
        agent = SimpleAgent(client=client, config=config)

        with self.assertRaises(ContextOverflowError) as ctx:
            agent.ask("x" * 500)

        self.assertEqual(len(client.calls), 0)
        self.assertEqual([message["role"] for message in agent.get_history()], ["system"])
        self.assertTrue(ctx.exception.report.overflow_detected)

    def test_sliding_window_removes_old_messages_before_request(self) -> None:
        client = FakeClient()
        config = AgentConfig(
            system_prompt="system",
            context_window_tokens=120,
            max_tokens=20,
            overflow_policy=ContextOverflowPolicy.SLIDING_WINDOW,
        )
        agent = SimpleAgent(client=client, config=config)
        # Seed history with old messages that can be removed.
        agent.messages.extend(
            [
                {"role": "user", "content": "old user " * 20},
                {"role": "assistant", "content": "old assistant " * 20},
            ]
        )

        response = agent.ask("new question")

        self.assertGreater(response.token_report.trimmed_messages_count, 0)
        sent_messages = client.calls[0]
        sent_contents = [message["content"] for message in sent_messages]
        self.assertIn("new question", sent_contents)
        self.assertNotIn("old user " * 20, sent_contents)

    def test_token_counter_counts_history_breakdown(self) -> None:
        counter = ApproxTokenCounter()
        messages: list[Message] = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "Привет"},
            {"role": "assistant", "content": "Здравствуйте"},
        ]
        breakdown = counter.breakdown(messages)
        self.assertEqual(breakdown.message_count, 3)
        self.assertGreater(breakdown.total, 0)
        self.assertGreater(breakdown.user, 0)
        self.assertGreater(breakdown.assistant, 0)


if __name__ == "__main__":
    unittest.main()
