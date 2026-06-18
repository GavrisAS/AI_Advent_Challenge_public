"""Hard state invariants and deterministic conflict checks."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_advent_agent.llm_client import Message
from ai_advent_agent.storage import ContextStorageError
from ai_advent_agent.token_counter import ApproxTokenCounter

INVARIANTS_SCHEMA_VERSION = 1
INVARIANT_EVENTS_SCHEMA_VERSION = 1
VALID_INVARIANT_CATEGORIES = (
    "architecture",
    "technical_decision",
    "stack_constraint",
    "business_rule",
)
INVARIANT_ID_PREFIXES = {
    "architecture": "architecture",
    "technical_decision": "decision",
    "stack_constraint": "stack",
    "business_rule": "business",
}


def now_utc() -> str:
    return datetime.now(UTC).isoformat()


def validate_invariant_category(category: str) -> str:
    checked = category.strip().lower()
    if checked not in VALID_INVARIANT_CATEGORIES:
        allowed = ", ".join(VALID_INVARIANT_CATEGORIES)
        raise ValueError(f"Недопустимая категория invariant: {category}. Допустимо: {allowed}")
    return checked


def validate_invariant_text(text: str, *, field_name: str = "text") -> str:
    checked = text.strip()
    if not checked:
        raise ValueError(f"invariant.{field_name} не должен быть пустым")
    return checked


def validate_reject_pattern(pattern: str) -> str:
    checked = pattern.strip()
    if not checked:
        raise ValueError("reject pattern не должен быть пустым")
    return checked


@dataclass(slots=True)
class Invariant:
    """One hard constraint that can block conflicting user requests."""

    id: str
    category: str
    text: str
    enabled: bool = True
    rationale: str = ""
    reject_patterns: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        self.id = validate_invariant_text(self.id, field_name="id")
        self.category = validate_invariant_category(self.category)
        self.text = validate_invariant_text(self.text)
        self.rationale = self.rationale.strip()
        self.reject_patterns = [
            validate_reject_pattern(pattern) for pattern in self.reject_patterns
        ]
        if not isinstance(self.enabled, bool):
            raise ValueError("invariant.enabled должен быть boolean")
        if not self.created_at:
            self.created_at = now_utc()
        if not self.updated_at:
            self.updated_at = self.created_at

    @property
    def active(self) -> bool:
        return self.enabled and bool(self.text.strip())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Invariant:
        if not isinstance(payload, dict):
            raise ValueError("invariant должен быть JSON-объектом")
        kwargs: dict[str, Any] = {}
        for field_name in ("id", "category", "text", "rationale", "created_at", "updated_at"):
            value = payload.get(field_name, "")
            if value is None:
                value = ""
            if not isinstance(value, str):
                raise ValueError(f"invariant.{field_name} должен быть строкой")
            kwargs[field_name] = value
        enabled = payload.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError("invariant.enabled должен быть boolean")
        patterns = payload.get("reject_patterns", [])
        if not isinstance(patterns, list) or not all(isinstance(item, str) for item in patterns):
            raise ValueError("invariant.reject_patterns должен быть списком строк")
        kwargs["enabled"] = enabled
        kwargs["reject_patterns"] = patterns
        return cls(**kwargs)


@dataclass(slots=True)
class InvariantConflict:
    """Deterministic conflict detected before any LLM call."""

    invariant_id: str
    category: str
    invariant_text: str
    matched_pattern: str
    user_preview: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(slots=True)
class InvariantSet:
    """Collection of hard invariants with deterministic id generation."""

    invariants: dict[str, Invariant] = field(default_factory=dict)

    @property
    def active(self) -> bool:
        return any(invariant.active for invariant in self.invariants.values())

    def enabled(self) -> list[Invariant]:
        return sorted(
            [invariant for invariant in self.invariants.values() if invariant.active],
            key=lambda invariant: invariant.id,
        )

    def all(self) -> list[Invariant]:
        return sorted(self.invariants.values(), key=lambda invariant: invariant.id)

    def add(self, category: str, text: str) -> Invariant:
        checked_category = validate_invariant_category(category)
        checked_text = validate_invariant_text(text)
        invariant_id = self._next_id(checked_category)
        invariant = Invariant(id=invariant_id, category=checked_category, text=checked_text)
        self.invariants[invariant.id] = invariant
        return invariant

    def require(self, invariant_id: str) -> Invariant:
        checked_id = validate_invariant_text(invariant_id, field_name="id")
        invariant = self.invariants.get(checked_id)
        if invariant is None:
            raise ValueError(f"Invariant не найден: {checked_id}")
        return invariant

    def remove(self, invariant_id: str) -> Invariant:
        invariant = self.require(invariant_id)
        del self.invariants[invariant.id]
        return invariant

    def set_enabled(self, invariant_id: str, enabled: bool) -> Invariant:
        invariant = self.require(invariant_id)
        invariant.enabled = enabled
        invariant.updated_at = now_utc()
        return invariant

    def set_rationale(self, invariant_id: str, rationale: str) -> Invariant:
        invariant = self.require(invariant_id)
        invariant.rationale = validate_invariant_text(rationale, field_name="rationale")
        invariant.updated_at = now_utc()
        return invariant

    def add_reject_pattern(self, invariant_id: str, pattern: str) -> Invariant:
        invariant = self.require(invariant_id)
        checked = validate_reject_pattern(pattern)
        if checked not in invariant.reject_patterns:
            invariant.reject_patterns.append(checked)
            invariant.updated_at = now_utc()
        return invariant

    def remove_reject_pattern(self, invariant_id: str, pattern: str) -> bool:
        invariant = self.require(invariant_id)
        checked = validate_reject_pattern(pattern)
        before = len(invariant.reject_patterns)
        invariant.reject_patterns = [
            existing for existing in invariant.reject_patterns if existing != checked
        ]
        removed = len(invariant.reject_patterns) != before
        if removed:
            invariant.updated_at = now_utc()
        return removed

    def reset(self) -> None:
        self.invariants.clear()

    def check_conflicts(self, text: str) -> list[InvariantConflict]:
        checked_text = text.strip()
        if not checked_text:
            return []
        lowered = checked_text.lower()
        preview = checked_text[:160]
        conflicts: list[InvariantConflict] = []
        for invariant in self.enabled():
            for pattern in invariant.reject_patterns:
                if pattern.lower() in lowered:
                    conflicts.append(
                        InvariantConflict(
                            invariant_id=invariant.id,
                            category=invariant.category,
                            invariant_text=invariant.text,
                            matched_pattern=pattern,
                            user_preview=preview,
                        )
                    )
        return conflicts

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": INVARIANTS_SCHEMA_VERSION,
            "invariants": [invariant.to_dict() for invariant in self.all()],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> InvariantSet:
        if not isinstance(payload, dict):
            raise ValueError("invariants должен быть JSON-объектом")
        schema_version = payload.get("schema_version", INVARIANTS_SCHEMA_VERSION)
        if schema_version != INVARIANTS_SCHEMA_VERSION:
            raise ValueError(f"Неподдерживаемая версия invariants: {schema_version}")
        raw_invariants = payload.get("invariants", [])
        if not isinstance(raw_invariants, list):
            raise ValueError("invariants.invariants должен быть списком")
        invariants: dict[str, Invariant] = {}
        for raw_invariant in raw_invariants:
            invariant = Invariant.from_dict(raw_invariant)
            if invariant.id in invariants:
                raise ValueError(f"Дублирующийся invariant id: {invariant.id}")
            invariants[invariant.id] = invariant
        return cls(invariants=invariants)

    def _next_id(self, category: str) -> str:
        prefix = INVARIANT_ID_PREFIXES[category]
        used_numbers = []
        for invariant_id in self.invariants:
            if not invariant_id.startswith(f"{prefix}-"):
                continue
            suffix = invariant_id.removeprefix(f"{prefix}-")
            if suffix.isdigit():
                used_numbers.append(int(suffix))
        return f"{prefix}-{max(used_numbers, default=0) + 1:03d}"


class JsonInvariantStore:
    """Stores hard invariants in a dedicated JSON file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    def load(self) -> InvariantSet:
        if not self.path.exists():
            return InvariantSet()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ContextStorageError(
                f"Не удалось прочитать invariants {self.path}: {error}"
            ) from error
        try:
            return InvariantSet.from_dict(payload)
        except ValueError as error:
            raise ContextStorageError(f"Некорректный invariants {self.path}: {error}") from error

    def save(self, invariants: InvariantSet) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
            tmp_path.write_text(
                json.dumps(invariants.to_dict(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            tmp_path.replace(self.path)
        except OSError as error:
            raise ContextStorageError(
                f"Не удалось сохранить invariants {self.path}: {error}"
            ) from error

    def clear(self) -> None:
        try:
            if self.path.exists():
                self.path.unlink()
        except OSError as error:
            raise ContextStorageError(
                f"Не удалось удалить invariants {self.path}: {error}"
            ) from error


class InvariantEventStore:
    """Append-only JSONL audit log for invariant changes and conflict checks."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    def append(
        self,
        *,
        action: str,
        invariant: Invariant | None = None,
        conflicts: list[InvariantConflict] | None = None,
        value: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "schema_version": INVARIANT_EVENTS_SCHEMA_VERSION,
            "created_at": now_utc(),
            "action": action,
        }
        if invariant is not None:
            payload["invariant_id"] = invariant.id
            payload["category"] = invariant.category
            payload["enabled"] = invariant.enabled
        if conflicts is not None:
            payload["conflict_count"] = len(conflicts)
            payload["conflicts"] = [conflict.to_dict() for conflict in conflicts]
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
                    f"Не удалось разобрать invariant event {self.path}:{line_number}: {error}"
                ) from error
            if not isinstance(payload, dict):
                raise ContextStorageError(
                    f"invariant event должен быть объектом, строка {line_number}"
                )
            events.append(payload)
        return events

    def clear(self) -> None:
        try:
            if self.path.exists():
                self.path.unlink()
        except OSError as error:
            raise ContextStorageError(
                f"Не удалось удалить invariant events {self.path}: {error}"
            ) from error


def parse_invariant_add_argument(argument: str) -> tuple[str, str]:
    category, separator, text = argument.partition(":")
    if not separator:
        raise ValueError("Использование: <category>: <text>")
    return validate_invariant_category(category), validate_invariant_text(text)


def parse_invariant_id_text_argument(argument: str) -> tuple[str, str]:
    invariant_id, separator, text = argument.partition(":")
    if not separator:
        raise ValueError("Использование: <id>: <text>")
    return validate_invariant_text(invariant_id, field_name="id"), validate_invariant_text(text)


def build_invariants_prompt_message(
    invariants: InvariantSet,
    token_counter: ApproxTokenCounter | None = None,
) -> tuple[Message | None, int, int]:
    """Build a high-priority prompt block for enabled invariants."""

    enabled = invariants.enabled()
    if not enabled:
        return None, 0, 0
    lines = [
        "State invariants: hard constraints for this agent. Treat them as higher priority "
        "than user profile, memory, task state and current user text. "
        "If a user request conflicts with them, refuse the conflicting request and explain which "
        "invariant blocks it.",
    ]
    for invariant in enabled:
        lines.append(f"- {invariant.id} [{invariant.category}]: {invariant.text}")
        if invariant.rationale:
            lines.append(f"  rationale: {invariant.rationale}")
    message: Message = {"role": "system", "content": "\n".join(lines)}
    counter = token_counter or ApproxTokenCounter()
    return message, counter.count_message(message), len(enabled)


def build_invariant_refusal(conflicts: list[InvariantConflict]) -> str:
    if not conflicts:
        return "Запрос отклонён: он конфликтует с активным invariant."
    lines = [
        "Запрос отклонён локальным deterministic guard: он конфликтует с активными invariants."
    ]
    for conflict in conflicts:
        lines.append(
            f"- {conflict.invariant_id} [{conflict.category}]: {conflict.invariant_text} "
            f"(pattern: {conflict.matched_pattern})"
        )
    lines.append("LLM API не вызывался; обычная история диалога не изменена.")
    return "\n".join(lines)


__all__ = [
    "INVARIANTS_SCHEMA_VERSION",
    "INVARIANT_EVENTS_SCHEMA_VERSION",
    "VALID_INVARIANT_CATEGORIES",
    "Invariant",
    "InvariantConflict",
    "InvariantEventStore",
    "InvariantSet",
    "JsonInvariantStore",
    "build_invariant_refusal",
    "build_invariants_prompt_message",
    "parse_invariant_add_argument",
    "parse_invariant_id_text_argument",
    "validate_invariant_category",
]
