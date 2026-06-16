from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ai_advent_agent.agent import SimpleAgent
from ai_advent_agent.cli import handle_command
from ai_advent_agent.config import AgentConfig
from ai_advent_agent.llm_client import ChatResult, Message
from ai_advent_agent.memory_layers import (
    JsonKeyValueMemoryStore,
    JsonShortTermMemoryStore,
    MemoryEventStore,
)
from ai_advent_agent.scenarios import scenario_memory_layers_demo
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
            usage={"prompt_tokens": 77, "completion_tokens": 11, "total_tokens": 88},
            elapsed_seconds=0.01,
            model=config.model,
            raw={"fake": True},
        )


def build_memory_agent(tmp_dir: Path, client: FakeClient | None = None) -> SimpleAgent:
    return SimpleAgent(
        client=client or FakeClient(),
        config=AgentConfig(system_prompt="system"),
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


class Day11MemoryLayersTest(unittest.TestCase):
    def test_memory_layers_are_saved_to_separate_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            agent = build_memory_agent(tmp_dir)

            agent.remember_short("последний локальный факт")
            agent.remember_working("task", "реализовать memory layers")
            agent.remember_long("language", "русский")

            short_payload = json.loads((tmp_dir / "short_term_memory.json").read_text())
            working_payload = json.loads((tmp_dir / "working_memory.json").read_text())
            long_payload = json.loads((tmp_dir / "long_term_memory.json").read_text())

            self.assertIn("последний локальный факт", short_payload["notes"])
            self.assertEqual(working_payload["entries"], {"task": "реализовать memory layers"})
            self.assertEqual(long_payload["entries"], {"language": "русский"})

    def test_cli_remember_working_does_not_write_long_term(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            agent = build_memory_agent(tmp_dir)

            handled = handle_command(
                "/remember working task: реализовать memory layers",
                agent,
                show_metadata=False,
            )

            self.assertTrue(handled)
            self.assertEqual(agent.working_memory.normalized()["task"], "реализовать memory layers")
            self.assertEqual(agent.long_term_memory.normalized(), {})

    def test_cli_remember_long_does_not_write_working(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            agent = build_memory_agent(tmp_dir)

            handled = handle_command(
                "/remember long style: кратко и технически",
                agent,
                show_metadata=False,
            )

            self.assertTrue(handled)
            self.assertEqual(agent.long_term_memory.normalized()["style"], "кратко и технически")
            self.assertEqual(agent.working_memory.normalized(), {})

    def test_prompt_assembly_includes_memory_layers_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            client = FakeClient()
            agent = build_memory_agent(tmp_dir, client)
            agent.remember_long("language", "русский")
            agent.remember_working("task", "реализовать memory layers")
            agent.remember_short("показать разделение файлов")

            response = agent.ask("Что делать дальше?")

            sent = client.calls[0]
            contents = [message["content"] for message in sent]
            self.assertEqual(sent[0]["content"], "system")
            self.assertIn("Long-term memory", contents[1])
            self.assertIn("Working memory", contents[2])
            self.assertIn("Short-term memory", contents[3])
            self.assertEqual(sent[-1]["content"], "Что делать дальше?")
            self.assertEqual(
                response.token_report.prompt_assembly_order,
                [
                    "system",
                    "long_term_memory",
                    "working_memory",
                    "short_term_memory",
                    "current_user",
                ],
            )

    def test_working_memory_can_be_reset_without_clearing_long_term(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            agent = build_memory_agent(tmp_dir)
            agent.remember_working("task", "реализовать memory layers")
            agent.remember_long("style", "кратко")

            agent.reset_working_memory()

            self.assertEqual(agent.working_memory.normalized(), {})
            self.assertEqual(agent.long_term_memory.normalized(), {"style": "кратко"})

    def test_memory_events_are_written_to_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            agent = build_memory_agent(tmp_dir)
            agent.remember_working("task", "demo")
            agent.forget_working("task")

            events = MemoryEventStore(tmp_dir / "memory_events.jsonl").load_all()

            self.assertEqual([event["action"] for event in events], ["remember", "forget"])
            self.assertEqual([event["layer"] for event in events], ["working", "working"])

    def test_token_reports_contain_memory_layer_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            agent = build_memory_agent(tmp_dir)
            agent.remember_long("language", "русский")
            agent.remember_working("task", "demo")

            agent.ask("Ответь с учётом памяти")

            reports = TokenReportStore(tmp_dir / "token_reports.jsonl").load_all()
            self.assertEqual(len(reports), 1)
            self.assertTrue(reports[0].memory_layers_active)
            self.assertEqual(reports[0].memory_layer_entries["long_term"], 1)
            self.assertEqual(reports[0].memory_layer_entries["working"], 1)
            self.assertGreater(reports[0].memory_prompt_tokens_estimated, 0)

    def test_memory_layers_demo_works_without_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            output_dir = tmp_dir / "agent-context"
            results_file = tmp_dir / "results" / "day-11-memory-layers.md"

            scenario_memory_layers_demo(
                output_dir=output_dir,
                results_file=results_file,
                context_window=10_000,
                max_tokens=500,
            )

            self.assertTrue((output_dir / "short_term_memory.json").exists())
            self.assertTrue((output_dir / "working_memory.json").exists())
            self.assertTrue((output_dir / "long_term_memory.json").exists())
            self.assertTrue((output_dir / "memory_events.jsonl").exists())
            self.assertTrue((output_dir / "token_reports.jsonl").exists())
            self.assertIn("Memory Layers", results_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
