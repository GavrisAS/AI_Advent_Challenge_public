from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ai_advent_agent.agent import SimpleAgent
from ai_advent_agent.config import AgentConfig
from ai_advent_agent.llm_client import ChatResult, Message
from ai_advent_agent.memory_layers import JsonKeyValueMemoryStore, JsonShortTermMemoryStore
from ai_advent_agent.scenarios import scenario_task_state_machine_demo
from ai_advent_agent.storage import ContextStorageError
from ai_advent_agent.task_state import (
    JsonTaskStateStore,
    TaskEventStore,
    TaskState,
    build_task_state_prompt_message,
)
from ai_advent_agent.token_report import TokenReportStore
from ai_advent_agent.user_profile import JsonUserProfileStore


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[list[Message]] = []

    def chat(self, messages: list[Message], config: AgentConfig) -> ChatResult:
        self.calls.append([message.copy() for message in messages])
        return ChatResult(
            content="fake answer",
            finish_reason="stop",
            usage={"prompt_tokens": 77, "completion_tokens": 11, "total_tokens": 88},
            elapsed_seconds=0.01,
            model=config.model,
            raw={"fake": True},
        )


def build_task_agent(tmp_dir: Path, client: FakeClient | None = None) -> SimpleAgent:
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
        user_profile_store=JsonUserProfileStore(tmp_dir / "user_profiles.json"),
        task_state_store=JsonTaskStateStore(tmp_dir / "task_state.json"),
        task_event_store=TaskEventStore(tmp_dir / "task_events.jsonl"),
        token_report_store=TokenReportStore(tmp_dir / "token_reports.jsonl"),
    )


class TaskStateTest(unittest.TestCase):
    def test_default_state_is_inactive_and_not_prompted(self) -> None:
        state = TaskState()

        message, tokens = build_task_state_prompt_message(state)

        self.assertFalse(state.active)
        self.assertIsNone(message)
        self.assertEqual(tokens, 0)

    def test_store_save_load_and_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "task_state.json"
            store = JsonTaskStateStore(path)
            state = TaskState(
                stage="planning",
                title="demo",
                current_step="step",
                expected_action="act",
                metadata={" key ": " value "},
            )

            store.save(state)
            loaded = store.load()

            self.assertEqual(loaded.stage, "planning")
            self.assertEqual(loaded.metadata, {"key": "value"})
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)

    def test_invalid_stage_and_json_types_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TaskState(stage="paused")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "task_state.json"
            path.write_text(json.dumps({"schema_version": 1, "stage": 42}), encoding="utf-8")
            with self.assertRaises(ContextStorageError):
                JsonTaskStateStore(path).load()

    def test_transitions_pause_resume_complete_reset_and_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            agent = build_task_agent(tmp_dir)

            agent.start_task("Реализовать Day 13")
            self.assertEqual(agent.task_state.stage, "planning")
            agent.advance_task()
            self.assertEqual(agent.task_state.stage, "execution")
            agent.pause_task()
            self.assertEqual(agent.task_state.stage, "execution")
            self.assertTrue(agent.task_state.paused)
            agent.resume_task()
            self.assertFalse(agent.task_state.paused)
            agent.advance_task()
            self.assertEqual(agent.task_state.stage, "validation")
            agent.set_task_metadata("check", "pytest")
            agent.complete_task()
            self.assertEqual(agent.task_state.stage, "done")
            self.assertTrue(agent.task_state.done)
            agent.reset_task()
            self.assertFalse(agent.task_state.active)

            events = TaskEventStore(tmp_dir / "task_events.jsonl").load_all()
            self.assertEqual(
                [event["action"] for event in events],
                [
                    "start_task",
                    "set_stage",
                    "pause_task",
                    "resume_task",
                    "set_stage",
                    "set_metadata",
                    "complete_task",
                    "reset_task",
                ],
            )

    def test_prompt_order_places_task_after_working_before_short_term(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeClient()
            agent = build_task_agent(Path(tmp), client)
            agent.create_profile("engineer")
            agent.set_profile_field("style", "кратко")
            agent.remember_long("project", "AI Advent")
            agent.remember_working("task", "Day 13")
            agent.remember_short("проверить порядок prompt")
            agent.start_task("Реализовать task state")
            agent.set_task_step("Добавить команды /task")

            response = agent.ask("Что дальше?")

            contents = [message["content"] for message in client.calls[0]]
            self.assertIn("User profile preferences", contents[1])
            self.assertIn("Long-term memory", contents[2])
            self.assertIn("Working memory", contents[3])
            self.assertIn("Task state:", contents[4])
            self.assertIn("Short-term memory", contents[5])
            self.assertEqual(
                response.token_report.prompt_assembly_order,
                [
                    "system",
                    "user_profile",
                    "long_term_memory",
                    "working_memory",
                    "task_state",
                    "short_term_memory",
                    "current_user",
                ],
            )
            self.assertTrue(response.token_report.task_state_active)
            self.assertEqual(response.token_report.task_stage, "planning")
            self.assertGreater(response.token_report.task_prompt_tokens_estimated, 0)

    def test_task_state_does_not_modify_profile_or_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = build_task_agent(Path(tmp))

            agent.start_task("demo")
            agent.set_task_step("step")

            self.assertEqual(agent.user_profiles.profiles, {})
            self.assertEqual(agent.working_memory.normalized(), {})
            self.assertEqual(agent.long_term_memory.normalized(), {})

    def test_task_state_machine_demo_works_without_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            output_dir = tmp_dir / "agent-context"
            results_file = tmp_dir / "results" / "day-13-task-state-machine.md"

            scenario_task_state_machine_demo(
                output_dir=output_dir,
                results_file=results_file,
                context_window=10_000,
                max_tokens=500,
            )

            for name in [
                "task_state.json",
                "task_events.jsonl",
                "token_reports.jsonl",
                "prompt_empty.json",
                "prompt_planning.json",
                "prompt_execution.json",
                "prompt_paused_execution.json",
                "prompt_validation.json",
                "prompt_done.json",
            ]:
                self.assertTrue((output_dir / name).exists())
            self.assertIn("Task State Machine", results_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
