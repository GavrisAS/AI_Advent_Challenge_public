from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ai_advent_agent.agent import SimpleAgent
from ai_advent_agent.config import AgentConfig
from ai_advent_agent.llm_client import ChatResult, Message
from ai_advent_agent.storage import JsonContextStore, JsonSummaryStore
from ai_advent_agent.token_report import TokenReportStore


class SequencedFakeClient:
    def __init__(self, responses: list[str] | None = None) -> None:
        self.responses = responses or ["fake answer"]
        self.calls: list[list[Message]] = []

    def chat(self, messages: list[Message], config: AgentConfig) -> ChatResult:
        self.calls.append([message.copy() for message in messages])
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        content = self.responses[index]
        return ChatResult(
            content=content,
            finish_reason="stop",
            usage={
                "prompt_tokens": 100 + len(self.calls),
                "completion_tokens": 10,
                "total_tokens": 110 + len(self.calls),
            },
            elapsed_seconds=0.1,
            model=config.model,
            raw={"fake": True},
        )


class Day9SummaryAgentTest(unittest.TestCase):
    def test_summary_mode_off_does_not_call_summary_llm(self) -> None:
        client = SequencedFakeClient()
        agent = SimpleAgent(
            client=client,
            config=AgentConfig(system_prompt="system", summary_mode="off"),
        )
        agent.messages.extend(
            [
                {"role": "user", "content": "old fact"},
                {"role": "assistant", "content": "old answer"},
            ]
        )

        agent.ask("new question")

        self.assertEqual(len(client.calls), 1)
        self.assertIn("old fact", [message["content"] for message in client.calls[0]])
        self.assertIsNotNone(agent.last_token_report)
        assert agent.last_token_report is not None
        self.assertFalse(agent.last_token_report.summary_active)

    def test_llm_summary_replaces_old_raw_history_in_main_chat_call(self) -> None:
        client = SequencedFakeClient(
            responses=[
                "Пользователя зовут Алексей. Важный ранний факт: кодовое слово amber.",
                "main answer",
            ]
        )
        agent = SimpleAgent(
            client=client,
            config=AgentConfig(
                system_prompt="system",
                summary_mode="llm",
                recent_messages_limit=2,
                summarize_every_messages=4,
            ),
        )
        agent.messages.extend(
            [
                {"role": "user", "content": "Меня зовут Алексей"},
                {"role": "assistant", "content": "Запомнил имя"},
                {"role": "user", "content": "Кодовое слово amber"},
                {"role": "assistant", "content": "Запомнил кодовое слово"},
                {"role": "user", "content": "Свежий вопрос"},
                {"role": "assistant", "content": "Свежий ответ"},
            ]
        )

        response = agent.ask("Что важно помнить?")

        self.assertEqual(response.content, "main answer")
        self.assertEqual(len(client.calls), 2)
        summary_call, main_call = client.calls
        self.assertIn("Кодовое слово amber", summary_call[1]["content"])
        main_text = "\n".join(message["content"] for message in main_call)
        self.assertIn("кодовое слово amber", main_text)
        self.assertIn("Свежий вопрос", main_text)
        self.assertNotIn("Меня зовут Алексей", main_text)
        self.assertEqual(agent.summary_memory.summarized_message_count, 4)
        self.assertEqual(
            [message["role"] for message in agent.get_history()],
            ["system", "user", "assistant", "user", "assistant"],
        )
        self.assertTrue(response.token_report.summary_active)
        self.assertGreater(response.token_report.summary_tokens_estimated, 0)
        self.assertEqual(response.token_report.summarized_messages_count, 4)

    def test_summary_is_saved_and_restored_from_separate_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            context_path = Path(tmp_dir) / "messages.json"
            summary_path = Path(tmp_dir) / "summary.json"
            first_agent = SimpleAgent(
                client=SequencedFakeClient(["summary text", "answer"]),
                config=AgentConfig(
                    system_prompt="system",
                    summary_mode="llm",
                    recent_messages_limit=0,
                    summarize_every_messages=2,
                ),
                context_store=JsonContextStore(context_path),
                summary_store=JsonSummaryStore(summary_path),
            )
            first_agent.messages.extend(
                [
                    {"role": "user", "content": "old"},
                    {"role": "assistant", "content": "answer"},
                ]
            )
            first_agent.ask("new")

            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"], "summary text")
            self.assertEqual(payload["summarized_message_count"], 2)

            second_agent = SimpleAgent(
                client=SequencedFakeClient(),
                config=AgentConfig(system_prompt="system", summary_mode="llm"),
                context_store=JsonContextStore(context_path),
                summary_store=JsonSummaryStore(summary_path),
            )
            self.assertEqual(second_agent.summary_memory.summary, "summary text")

    def test_reset_and_clear_context_clear_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            context_path = Path(tmp_dir) / "messages.json"
            summary_path = Path(tmp_dir) / "summary.json"
            report_path = Path(tmp_dir) / "reports.jsonl"
            agent = SimpleAgent(
                client=SequencedFakeClient(),
                config=AgentConfig(system_prompt="system", summary_mode="llm"),
                context_store=JsonContextStore(context_path),
                summary_store=JsonSummaryStore(summary_path),
                token_report_store=TokenReportStore(report_path),
            )
            agent.summary_memory.summary = "old summary"
            agent.summary_memory.summarized_message_count = 10
            agent.save_summary()

            agent.reset()
            self.assertFalse(agent.summary_memory.active)
            self.assertFalse(JsonSummaryStore(summary_path).load().active)

            agent.summary_memory.summary = "old summary"
            agent.save_summary()
            agent.clear_context_file()
            self.assertFalse(summary_path.exists())


if __name__ == "__main__":
    unittest.main()
