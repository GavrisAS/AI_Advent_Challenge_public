"""Explicit task state machine for the current agent task."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_advent_agent.llm_client import Message
from ai_advent_agent.storage import ContextStorageError
from ai_advent_agent.token_counter import ApproxTokenCounter

TASK_STATE_SCHEMA_VERSION = 1
TASK_EVENTS_SCHEMA_VERSION = 1
EMPTY_TASK_STAGE = ""
VALID_TASK_STAGES = (
    "planning",
    "execution",
    "validation",
    "done",
)
NEXT_TASK_STAGE = {
    "planning": "execution",
    "execution": "validation",
    "validation": "done",
}


def now_utc() -> str:
    return datetime.now(UTC).isoformat()


def validate_task_stage(stage: str, *, allow_empty: bool = False) -> str:
    checked = stage.strip().lower()
    if allow_empty and checked == EMPTY_TASK_STAGE:
        return checked
    if checked not in VALID_TASK_STAGES:
        allowed = ", ".join(VALID_TASK_STAGES)
        raise ValueError(f"Недопустимый этап задачи: {stage}. Допустимо: {allowed}")
    return checked


def normalize_metadata(payload: Any) -> dict[str, str]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("task_state.metadata должен быть JSON-объектом")
    normalized: dict[str, str] = {}
    for raw_key, raw_value in payload.items():
        if not isinstance(raw_key, str) or not isinstance(raw_value, str):
            raise ValueError("task_state.metadata должен содержать только строки")
        key = raw_key.strip()
        value = raw_value.strip()
        if key and value:
            normalized[key] = value
    return normalized


@dataclass(slots=True)
class TaskState:
    """Formal state of the current task workflow."""

    stage: str = EMPTY_TASK_STAGE
    title: str = ""
    current_step: str = ""
    expected_action: str = ""
    done: bool = False
    paused: bool = False
    updated_at: str = ""
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.stage = validate_task_stage(self.stage, allow_empty=True)
        self.title = self.title.strip()
        self.current_step = self.current_step.strip()
        self.expected_action = self.expected_action.strip()
        self.metadata = normalize_metadata(self.metadata)
        if self.done:
            self.stage = "done"
            self.paused = False
        if self.stage == "done":
            self.done = True
            self.paused = False

    @property
    def active(self) -> bool:
        return any(
            (
                self.stage,
                self.title,
                self.current_step,
                self.expected_action,
                self.done,
                self.paused,
                self.metadata,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": TASK_STATE_SCHEMA_VERSION,
            **asdict(self),
        }

    def clear(self) -> None:
        self.stage = EMPTY_TASK_STAGE
        self.title = ""
        self.current_step = ""
        self.expected_action = ""
        self.done = False
        self.paused = False
        self.updated_at = ""
        self.metadata.clear()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TaskState:
        if not isinstance(payload, dict):
            raise ValueError("task_state должен быть JSON-объектом")
        schema_version = payload.get("schema_version", TASK_STATE_SCHEMA_VERSION)
        if schema_version != TASK_STATE_SCHEMA_VERSION:
            raise ValueError(f"Неподдерживаемая версия task_state: {schema_version}")

        kwargs: dict[str, Any] = {}
        for field_name in ("stage", "title", "current_step", "expected_action", "updated_at"):
            value = payload.get(field_name, "")
            if value is None:
                value = ""
            if not isinstance(value, str):
                raise ValueError(f"task_state.{field_name} должен быть строкой")
            kwargs[field_name] = value

        for field_name in ("done", "paused"):
            value = payload.get(field_name, False)
            if not isinstance(value, bool):
                raise ValueError(f"task_state.{field_name} должен быть boolean")
            kwargs[field_name] = value
        kwargs["metadata"] = normalize_metadata(payload.get("metadata", {}))
        return cls(**kwargs)


class JsonTaskStateStore:
    """Stores the current task state in a dedicated JSON file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    def load(self) -> TaskState:
        if not self.path.exists():
            return TaskState()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ContextStorageError(
                f"Не удалось прочитать task state {self.path}: {error}"
            ) from error
        try:
            return TaskState.from_dict(payload)
        except ValueError as error:
            raise ContextStorageError(f"Некорректный task state {self.path}: {error}") from error

    def save(self, state: TaskState) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
            tmp_path.write_text(
                json.dumps(state.to_dict(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            tmp_path.replace(self.path)
        except OSError as error:
            raise ContextStorageError(
                f"Не удалось сохранить task state {self.path}: {error}"
            ) from error

    def clear(self) -> None:
        try:
            if self.path.exists():
                self.path.unlink()
        except OSError as error:
            raise ContextStorageError(
                f"Не удалось удалить task state {self.path}: {error}"
            ) from error


class TaskEventStore:
    """Append-only JSONL audit log for task state commands."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    def append(
        self,
        *,
        action: str,
        state: TaskState,
        key: str | None = None,
        value: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "schema_version": TASK_EVENTS_SCHEMA_VERSION,
            "created_at": now_utc(),
            "action": action,
            "stage": state.stage,
            "title": state.title,
            "current_step": state.current_step,
            "expected_action": state.expected_action,
            "done": state.done,
            "paused": state.paused,
        }
        if key is not None:
            payload["key"] = key
        if value is not None:
            payload["value"] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def load_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line_number, raw_line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as error:
                raise ContextStorageError(
                    f"Не удалось разобрать task event {self.path}:{line_number}: {error}"
                ) from error
            if not isinstance(payload, dict):
                raise ContextStorageError(f"task event должен быть объектом, строка {line_number}")
            events.append(payload)
        return events

    def clear(self) -> None:
        try:
            if self.path.exists():
                self.path.unlink()
        except OSError as error:
            raise ContextStorageError(
                f"Не удалось удалить task events {self.path}: {error}"
            ) from error


def parse_task_metadata_argument(argument: str) -> tuple[str, str]:
    key, separator, value = argument.partition(":")
    if not separator:
        raise ValueError("Использование: <key>: <value>")
    checked_key = key.strip()
    checked_value = value.strip()
    if not checked_key:
        raise ValueError("metadata key не должен быть пустым")
    if not checked_value:
        raise ValueError("metadata value не должен быть пустым")
    return checked_key, checked_value


def build_task_state_prompt_message(
    state: TaskState,
    token_counter: ApproxTokenCounter | None = None,
) -> tuple[Message | None, int]:
    """Build a system prompt block for an active task state."""

    if not state.active:
        return None, 0
    lines = [
        "Task state: formal workflow state for the current task. "
        "Use it to continue the task; do not treat it as memory or user profile.",
        f"- stage: {state.stage or '-'}",
        f"- title: {state.title or '-'}",
        f"- current step: {state.current_step or '-'}",
        f"- expected action: {state.expected_action or '-'}",
        f"- done: {str(state.done).lower()}",
        f"- paused: {str(state.paused).lower()}",
    ]
    if state.metadata:
        lines.append("- metadata:")
        lines.extend(f"  - {key}: {value}" for key, value in sorted(state.metadata.items()))
    message: Message = {"role": "system", "content": "\n".join(lines)}
    counter = token_counter or ApproxTokenCounter()
    return message, counter.count_message(message)


__all__ = [
    "EMPTY_TASK_STAGE",
    "NEXT_TASK_STAGE",
    "TASK_EVENTS_SCHEMA_VERSION",
    "TASK_STATE_SCHEMA_VERSION",
    "VALID_TASK_STAGES",
    "JsonTaskStateStore",
    "TaskEventStore",
    "TaskState",
    "build_task_state_prompt_message",
    "parse_task_metadata_argument",
    "validate_task_stage",
]
