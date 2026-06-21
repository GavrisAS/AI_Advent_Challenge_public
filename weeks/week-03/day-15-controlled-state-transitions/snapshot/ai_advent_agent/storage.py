"""Persistent JSON storage for agent conversation context."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_advent_agent.llm_client import Message

CONTEXT_SCHEMA_VERSION = 1
SUMMARY_SCHEMA_VERSION = 1
ALLOWED_ROLES = {"system", "user", "assistant", "tool"}


class ContextStorageError(RuntimeError):
    """Raised when persisted context cannot be read or written safely."""


@dataclass(slots=True)
class SummaryMemory:
    """Persisted compressed memory for old conversation turns."""

    summary: str = ""
    summarized_message_count: int = 0
    updated_at: str = ""

    @property
    def active(self) -> bool:
        return bool(self.summary.strip())


class JsonContextStore:
    """Stores and restores agent messages in a JSON file.

    The store is intentionally small and dependency-free. It owns only disk I/O
    and validation. SimpleAgent owns conversational behavior.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    def load(self) -> list[Message]:
        """Load messages from JSON. Missing file means empty history."""

        if not self.path.exists():
            return []

        try:
            raw = self.path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError) as error:
            raise ContextStorageError(
                f"Не удалось прочитать файл контекста {self.path}: {error}"
            ) from error

        if not isinstance(payload, dict):
            raise ContextStorageError("Файл контекста должен содержать JSON-объект")

        messages = payload.get("messages")
        if not isinstance(messages, list):
            raise ContextStorageError("В файле контекста нет списка messages")

        return self._validate_messages(messages)

    def save(self, messages: list[Message]) -> None:
        """Persist messages to JSON using an atomic replace."""

        normalized_messages = self._validate_messages(messages)
        payload = {
            "schema_version": CONTEXT_SCHEMA_VERSION,
            "updated_at": datetime.now(UTC).isoformat(),
            "message_count": len(normalized_messages),
            "messages": normalized_messages,
        }

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
            tmp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp_path.replace(self.path)
        except OSError as error:
            raise ContextStorageError(
                f"Не удалось сохранить контекст в {self.path}: {error}"
            ) from error

    def clear(self) -> None:
        """Remove persisted context file if it exists."""

        try:
            if self.path.exists():
                self.path.unlink()
        except OSError as error:
            raise ContextStorageError(
                f"Не удалось удалить файл контекста {self.path}: {error}"
            ) from error

    @staticmethod
    def _validate_messages(messages: Any) -> list[Message]:
        if not isinstance(messages, list):
            raise ContextStorageError("messages должен быть списком")

        normalized: list[Message] = []
        for index, item in enumerate(messages):
            if not isinstance(item, dict):
                raise ContextStorageError(f"messages[{index}] должен быть объектом")

            role = item.get("role")
            content = item.get("content")
            if not isinstance(role, str) or role not in ALLOWED_ROLES:
                raise ContextStorageError(
                    f"messages[{index}].role должен быть одним из {sorted(ALLOWED_ROLES)}"
                )
            if not isinstance(content, str):
                raise ContextStorageError(f"messages[{index}].content должен быть строкой")

            normalized.append({"role": role, "content": content})

        return normalized


class JsonSummaryStore:
    """Stores and restores LLM-generated conversation summary in a JSON file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    def load(self) -> SummaryMemory:
        """Load summary memory. Missing file means empty summary."""

        if not self.path.exists():
            return SummaryMemory()

        try:
            raw = self.path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError) as error:
            raise ContextStorageError(
                f"Не удалось прочитать файл summary {self.path}: {error}"
            ) from error

        if not isinstance(payload, dict):
            raise ContextStorageError("Файл summary должен содержать JSON-объект")

        summary = payload.get("summary", "")
        summarized_message_count = payload.get("summarized_message_count", 0)
        updated_at = payload.get("updated_at", "")
        if not isinstance(summary, str):
            raise ContextStorageError("summary должен быть строкой")
        if not isinstance(summarized_message_count, int) or summarized_message_count < 0:
            raise ContextStorageError("summarized_message_count должен быть неотрицательным числом")
        if not isinstance(updated_at, str):
            raise ContextStorageError("updated_at должен быть строкой")

        return SummaryMemory(
            summary=summary,
            summarized_message_count=summarized_message_count,
            updated_at=updated_at,
        )

    def save(self, memory: SummaryMemory) -> None:
        """Persist summary memory using an atomic replace."""

        payload = {
            "schema_version": SUMMARY_SCHEMA_VERSION,
            **asdict(
                SummaryMemory(
                    summary=memory.summary,
                    summarized_message_count=memory.summarized_message_count,
                    updated_at=datetime.now(UTC).isoformat(),
                )
            ),
        }

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
            tmp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp_path.replace(self.path)
        except OSError as error:
            raise ContextStorageError(
                f"Не удалось сохранить summary в {self.path}: {error}"
            ) from error

    def clear(self) -> None:
        """Remove persisted summary file if it exists."""

        try:
            if self.path.exists():
                self.path.unlink()
        except OSError as error:
            raise ContextStorageError(
                f"Не удалось удалить файл summary {self.path}: {error}"
            ) from error
