"""Explicit memory layers for the Day 11 stateful assistant."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_advent_agent.llm_client import Message
from ai_advent_agent.storage import ContextStorageError, JsonContextStore
from ai_advent_agent.token_counter import ApproxTokenCounter

MEMORY_SCHEMA_VERSION = 1
MEMORY_EVENTS_SCHEMA_VERSION = 1


@dataclass(slots=True)
class ShortTermMemory:
    """Short-term memory for the current dialog."""

    notes: list[str] = field(default_factory=list)
    recent_messages: list[Message] = field(default_factory=list)
    updated_at: str = ""

    @property
    def active(self) -> bool:
        return bool(self.normalized_notes() or self.recent_messages)

    def add_note(self, text: str) -> None:
        note = text.strip()
        if not note:
            raise ValueError("short-term memory text не должен быть пустым")
        self.notes.append(note)
        self.updated_at = datetime.now(UTC).isoformat()

    def set_recent_messages(self, messages: list[Message]) -> None:
        self.recent_messages = JsonContextStore._validate_messages(messages)
        self.updated_at = datetime.now(UTC).isoformat()

    def normalized_notes(self) -> list[str]:
        return [note.strip() for note in self.notes if note.strip()]

    def clear(self) -> None:
        self.notes = []
        self.recent_messages = []
        self.updated_at = ""


@dataclass(slots=True)
class KeyValueMemory:
    """Key-value memory used by working and long-term layers."""

    entries: dict[str, str] = field(default_factory=dict)
    updated_at: str = ""

    @property
    def active(self) -> bool:
        return bool(self.normalized())

    def set(self, key: str, value: str) -> None:
        checked_key = normalize_memory_key(key)
        checked_value = value.strip()
        if not checked_value:
            raise ValueError("memory value не должен быть пустым")
        self.entries[checked_key] = checked_value
        self.updated_at = datetime.now(UTC).isoformat()

    def forget(self, key: str) -> bool:
        checked_key = normalize_memory_key(key)
        removed = checked_key in self.entries
        self.entries.pop(checked_key, None)
        if removed:
            self.updated_at = datetime.now(UTC).isoformat()
        return removed

    def normalized(self) -> dict[str, str]:
        return {
            key.strip(): value.strip()
            for key, value in sorted(self.entries.items())
            if key.strip() and value.strip()
        }

    def clear(self) -> None:
        self.entries = {}
        self.updated_at = ""


@dataclass(slots=True)
class MemoryPromptMetadata:
    """Token metadata for memory blocks injected into a prompt."""

    layers_active: bool = False
    layer_entries: dict[str, int] = field(default_factory=dict)
    layer_tokens_estimated: dict[str, int] = field(default_factory=dict)
    prompt_tokens_estimated: int = 0
    profile_active: bool = False
    active_profile_name: str = ""
    profile_fields_count: int = 0
    profile_prompt_tokens_estimated: int = 0
    assembly_order: list[str] = field(default_factory=list)


class JsonShortTermMemoryStore:
    """Stores short-term memory in a dedicated JSON file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    def load(self) -> ShortTermMemory:
        if not self.path.exists():
            return ShortTermMemory()

        payload = read_json_object(self.path, "short-term memory")
        notes = payload.get("notes", [])
        recent_messages = payload.get("recent_messages", [])
        updated_at = payload.get("updated_at", "")
        if not isinstance(notes, list) or not all(isinstance(note, str) for note in notes):
            raise ContextStorageError("short-term notes должны быть списком строк")
        if not isinstance(updated_at, str):
            raise ContextStorageError("short-term updated_at должен быть строкой")
        return ShortTermMemory(
            notes=[note.strip() for note in notes if note.strip()],
            recent_messages=JsonContextStore._validate_messages(recent_messages),
            updated_at=updated_at,
        )

    def save(self, memory: ShortTermMemory) -> None:
        payload = {
            "schema_version": MEMORY_SCHEMA_VERSION,
            "layer": "short_term",
            "updated_at": datetime.now(UTC).isoformat(),
            "notes": memory.normalized_notes(),
            "recent_messages": JsonContextStore._validate_messages(memory.recent_messages),
        }
        write_json_object(self.path, payload)

    def clear(self) -> None:
        unlink_if_exists(self.path, "short-term memory")


class JsonKeyValueMemoryStore:
    """Stores working or long-term key-value memory in a dedicated JSON file."""

    def __init__(self, path: str | Path, *, layer: str) -> None:
        self.path = Path(path).expanduser()
        self.layer = layer

    def load(self) -> KeyValueMemory:
        if not self.path.exists():
            return KeyValueMemory()

        payload = read_json_object(self.path, self.layer)
        entries = payload.get("entries", {})
        updated_at = payload.get("updated_at", "")
        if not isinstance(entries, dict):
            raise ContextStorageError(f"{self.layer}.entries должен быть JSON-объектом")
        if not isinstance(updated_at, str):
            raise ContextStorageError(f"{self.layer}.updated_at должен быть строкой")

        normalized: dict[str, str] = {}
        for key, value in entries.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ContextStorageError(f"{self.layer}.entries должен содержать строки")
            if key.strip() and value.strip():
                normalized[key.strip()] = value.strip()
        return KeyValueMemory(entries=normalized, updated_at=updated_at)

    def save(self, memory: KeyValueMemory) -> None:
        payload = {
            "schema_version": MEMORY_SCHEMA_VERSION,
            "layer": self.layer,
            "updated_at": datetime.now(UTC).isoformat(),
            "entries": memory.normalized(),
        }
        write_json_object(self.path, payload)

    def clear(self) -> None:
        unlink_if_exists(self.path, self.layer)


class MemoryEventStore:
    """Append-only JSONL journal for explicit memory operations."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    def append(
        self,
        *,
        action: str,
        layer: str,
        key: str | None = None,
        value: str | None = None,
        text: str | None = None,
    ) -> None:
        payload = {
            "schema_version": MEMORY_EVENTS_SCHEMA_VERSION,
            "created_at": datetime.now(UTC).isoformat(),
            "action": action,
            "layer": layer,
        }
        if key is not None:
            payload["key"] = key
        if value is not None:
            payload["value"] = value
        if text is not None:
            payload["text"] = text
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
                    f"Не удалось разобрать memory event {self.path}:{line_number}: {error}"
                ) from error
            if not isinstance(payload, dict):
                raise ContextStorageError("memory event должен быть JSON-объектом")
            events.append(payload)
        return events

    def clear(self) -> None:
        unlink_if_exists(self.path, "memory events")


def build_memory_prompt_messages(
    *,
    short_term: ShortTermMemory,
    working: KeyValueMemory,
    long_term: KeyValueMemory,
    token_counter: ApproxTokenCounter,
) -> tuple[list[Message], MemoryPromptMetadata]:
    """Build ordered memory prompt blocks and token metadata."""

    messages: list[Message] = []
    entries: dict[str, int] = {"long_term": 0, "working": 0, "short_term": 0}
    tokens: dict[str, int] = {"long_term": 0, "working": 0, "short_term": 0}
    order: list[str] = []

    long_entries = long_term.normalized()
    if long_entries:
        message = key_value_memory_message(
            "Long-term memory: профиль, устойчивые предпочтения, решения и знания.",
            long_entries,
        )
        messages.append(message)
        entries["long_term"] = len(long_entries)
        tokens["long_term"] = token_counter.count_message(message)
        order.append("long_term_memory")

    working_entries = working.normalized()
    if working_entries:
        message = key_value_memory_message(
            "Working memory: данные текущей задачи, ограничения и промежуточные решения.",
            working_entries,
        )
        messages.append(message)
        entries["working"] = len(working_entries)
        tokens["working"] = token_counter.count_message(message)
        order.append("working_memory")

    short_message = short_term_memory_message(short_term)
    if short_message is not None:
        messages.append(short_message)
        entries["short_term"] = len(short_term.normalized_notes()) + len(short_term.recent_messages)
        tokens["short_term"] = token_counter.count_message(short_message)
        order.append("short_term_memory")

    return messages, MemoryPromptMetadata(
        layers_active=bool(messages),
        layer_entries=entries,
        layer_tokens_estimated=tokens,
        prompt_tokens_estimated=sum(tokens.values()),
        assembly_order=order,
    )


def key_value_memory_message(title: str, entries: dict[str, str]) -> Message:
    lines = [title, ""]
    lines.extend(f"- {key}: {value}" for key, value in entries.items())
    return {"role": "system", "content": "\n".join(lines)}


def short_term_memory_message(memory: ShortTermMemory) -> Message | None:
    notes = memory.normalized_notes()
    recent_messages = JsonContextStore._validate_messages(memory.recent_messages)
    if not notes and not recent_messages:
        return None

    lines = ["Short-term memory: текущий диалог и явные short notes."]
    if notes:
        lines.extend(["", "Явные short notes:"])
        lines.extend(f"- {note}" for note in notes)
    if recent_messages:
        lines.extend(["", "Последние сообщения текущего диалога:"])
        for message in recent_messages:
            lines.append(f"- {message['role']}: {message['content']}")
    return {"role": "system", "content": "\n".join(lines)}


def normalize_memory_key(key: str) -> str:
    checked = key.strip()
    if not checked:
        raise ValueError("memory key не должен быть пустым")
    return checked


def parse_key_value_argument(argument: str) -> tuple[str, str]:
    key, separator, value = argument.partition(":")
    if not separator:
        raise ValueError("Использование: <key>: <value>")
    return normalize_memory_key(key), value.strip()


def read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContextStorageError(f"Не удалось прочитать {label} {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ContextStorageError(f"Файл {label} должен содержать JSON-объект")
    return payload


def write_json_object(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(f"{path.suffix}.tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)
    except OSError as error:
        raise ContextStorageError(f"Не удалось сохранить {path}: {error}") from error


def unlink_if_exists(path: Path, label: str) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError as error:
        raise ContextStorageError(f"Не удалось удалить {label} {path}: {error}") from error


def memory_payload(memory: ShortTermMemory | KeyValueMemory) -> dict[str, Any]:
    """Return a JSON-serializable copy for reports and tests."""

    return asdict(memory)


__all__ = [
    "JsonKeyValueMemoryStore",
    "JsonShortTermMemoryStore",
    "KeyValueMemory",
    "MemoryEventStore",
    "MemoryPromptMetadata",
    "ShortTermMemory",
    "build_memory_prompt_messages",
    "parse_key_value_argument",
]
