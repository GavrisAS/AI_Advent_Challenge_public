"""Day 10 context-management stores: sticky facts and dialog branches."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_advent_agent.llm_client import Message
from ai_advent_agent.storage import ContextStorageError, JsonContextStore

FACTS_SCHEMA_VERSION = 1
BRANCHES_SCHEMA_VERSION = 1

FACT_KEYS = (
    "goal",
    "constraints",
    "preferences",
    "decisions",
    "agreements",
    "user_data",
)


@dataclass(slots=True)
class StickyFacts:
    """Key-value memory extracted from user messages."""

    values: dict[str, str] = field(default_factory=dict)
    updated_at: str = ""

    @property
    def active(self) -> bool:
        return any(value.strip() for value in self.values.values())

    def normalized(self) -> dict[str, str]:
        return {key: self.values.get(key, "").strip() for key in FACT_KEYS}

    def merge(self, updates: dict[str, str]) -> None:
        normalized = self.normalized()
        changed = False
        for key in FACT_KEYS:
            value = updates.get(key, "").strip()
            if value:
                normalized[key] = value
                changed = True
        self.values = normalized
        if changed:
            self.updated_at = datetime.now(UTC).isoformat()

    def clear(self) -> None:
        self.values = {key: "" for key in FACT_KEYS}
        self.updated_at = ""


class JsonFactsStore:
    """Stores sticky facts in a small JSON document."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    def load(self) -> StickyFacts:
        if not self.path.exists():
            return StickyFacts({key: "" for key in FACT_KEYS})

        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ContextStorageError(f"Не удалось прочитать facts {self.path}: {error}") from error

        if not isinstance(payload, dict):
            raise ContextStorageError("Файл facts должен содержать JSON-объект")

        raw_facts = payload.get("facts", {})
        updated_at = payload.get("updated_at", "")
        if not isinstance(raw_facts, dict):
            raise ContextStorageError("facts должен быть JSON-объектом")
        if not isinstance(updated_at, str):
            raise ContextStorageError("updated_at должен быть строкой")

        facts: dict[str, str] = {}
        for key in FACT_KEYS:
            value = raw_facts.get(key, "")
            if not isinstance(value, str):
                raise ContextStorageError(f"facts.{key} должен быть строкой")
            facts[key] = value
        return StickyFacts(values=facts, updated_at=updated_at)

    def save(self, facts: StickyFacts) -> None:
        payload = {
            "schema_version": FACTS_SCHEMA_VERSION,
            "updated_at": datetime.now(UTC).isoformat(),
            "facts": facts.normalized(),
        }
        self._write_json(payload)

    def clear(self) -> None:
        try:
            if self.path.exists():
                self.path.unlink()
        except OSError as error:
            raise ContextStorageError(f"Не удалось удалить facts {self.path}: {error}") from error

    def _write_json(self, payload: dict[str, Any]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
            tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp_path.replace(self.path)
        except OSError as error:
            raise ContextStorageError(
                f"Не удалось сохранить facts в {self.path}: {error}"
            ) from error


@dataclass(slots=True)
class BranchSnapshot:
    """Saved state for a checkpoint or branch."""

    name: str
    messages: list[Message]
    facts: dict[str, str] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        now = datetime.now(UTC).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


@dataclass(slots=True)
class BranchMemory:
    """Mutable branch graph persisted by JsonBranchesStore."""

    active_branch: str = "main"
    branches: dict[str, BranchSnapshot] = field(default_factory=dict)
    checkpoints: dict[str, BranchSnapshot] = field(default_factory=dict)
    latest_checkpoint: str = ""


class JsonBranchesStore:
    """Stores checkpoints and independent dialog branches in JSON."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    def load(self) -> BranchMemory:
        if not self.path.exists():
            return BranchMemory()

        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ContextStorageError(
                f"Не удалось прочитать branches {self.path}: {error}"
            ) from error

        if not isinstance(payload, dict):
            raise ContextStorageError("Файл branches должен содержать JSON-объект")

        active_branch = payload.get("active_branch", "main")
        latest_checkpoint = payload.get("latest_checkpoint", "")
        if not isinstance(active_branch, str) or not active_branch.strip():
            raise ContextStorageError("active_branch должен быть непустой строкой")
        if not isinstance(latest_checkpoint, str):
            raise ContextStorageError("latest_checkpoint должен быть строкой")

        return BranchMemory(
            active_branch=active_branch,
            branches=self._load_snapshots(payload.get("branches", {}), "branches"),
            checkpoints=self._load_snapshots(payload.get("checkpoints", {}), "checkpoints"),
            latest_checkpoint=latest_checkpoint,
        )

    def save(self, memory: BranchMemory) -> None:
        payload = {
            "schema_version": BRANCHES_SCHEMA_VERSION,
            "updated_at": datetime.now(UTC).isoformat(),
            "active_branch": memory.active_branch,
            "latest_checkpoint": memory.latest_checkpoint,
            "branches": {
                name: self._snapshot_to_payload(snapshot)
                for name, snapshot in sorted(memory.branches.items())
            },
            "checkpoints": {
                name: self._snapshot_to_payload(snapshot)
                for name, snapshot in sorted(memory.checkpoints.items())
            },
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
            tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp_path.replace(self.path)
        except OSError as error:
            raise ContextStorageError(
                f"Не удалось сохранить branches в {self.path}: {error}"
            ) from error

    def clear(self) -> None:
        try:
            if self.path.exists():
                self.path.unlink()
        except OSError as error:
            raise ContextStorageError(
                f"Не удалось удалить branches {self.path}: {error}"
            ) from error

    @staticmethod
    def _load_snapshots(raw: Any, field_name: str) -> dict[str, BranchSnapshot]:
        if not isinstance(raw, dict):
            raise ContextStorageError(f"{field_name} должен быть JSON-объектом")

        snapshots: dict[str, BranchSnapshot] = {}
        for name, payload in raw.items():
            if not isinstance(name, str) or not name.strip():
                raise ContextStorageError(f"{field_name} содержит пустое имя")
            if not isinstance(payload, dict):
                raise ContextStorageError(f"{field_name}.{name} должен быть объектом")
            messages = JsonContextStore._validate_messages(payload.get("messages", []))
            facts = payload.get("facts", {})
            if not isinstance(facts, dict):
                raise ContextStorageError(f"{field_name}.{name}.facts должен быть объектом")
            normalized_facts = {
                key: value
                for key, value in facts.items()
                if isinstance(key, str) and isinstance(value, str)
            }
            created_at = payload.get("created_at", "")
            updated_at = payload.get("updated_at", "")
            if not isinstance(created_at, str) or not isinstance(updated_at, str):
                raise ContextStorageError(
                    f"{field_name}.{name}.created_at/updated_at должны быть строками"
                )
            snapshots[name] = BranchSnapshot(
                name=name,
                messages=messages,
                facts=normalized_facts,
                created_at=created_at,
                updated_at=updated_at,
            )
        return snapshots

    @staticmethod
    def _snapshot_to_payload(snapshot: BranchSnapshot) -> dict[str, Any]:
        payload = asdict(snapshot)
        payload.pop("name", None)
        return payload


__all__ = [
    "FACT_KEYS",
    "BranchMemory",
    "BranchSnapshot",
    "JsonBranchesStore",
    "JsonFactsStore",
    "StickyFacts",
]
