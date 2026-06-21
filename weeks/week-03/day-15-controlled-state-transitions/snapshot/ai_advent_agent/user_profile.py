"""Persistent assistant personalization profiles."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_advent_agent.llm_client import Message
from ai_advent_agent.token_counter import ApproxTokenCounter

PROFILE_SCHEMA_VERSION = 1
PROFILE_EVENT_SCHEMA_VERSION = 1
PROFILE_FIELDS = ("language", "style", "format", "audience")
_PROFILE_NAME_RE = re.compile(r"^[a-z0-9_-]+$")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def normalize_profile_name(name: str) -> str:
    """Normalize and validate a profile name used in persistence and commands."""

    checked = name.strip().lower()
    if not checked:
        raise ValueError("Имя профиля не должно быть пустым")
    if "/" in checked or "\\" in checked:
        raise ValueError("Имя профиля не должно содержать path separators")
    if any(char.isspace() for char in checked):
        raise ValueError("Имя профиля не должно содержать пробелы")
    if not _PROFILE_NAME_RE.fullmatch(checked):
        raise ValueError("Имя профиля может содержать только a-z, 0-9, _ и -")
    return checked


def _clean_string(value: str) -> str:
    return value.strip()


def _validate_string_map(payload: Any, field_name: str) -> dict[str, str]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError(f"{field_name} должен быть JSON-объектом")
    cleaned: dict[str, str] = {}
    for raw_key, raw_value in payload.items():
        if not isinstance(raw_key, str) or not isinstance(raw_value, str):
            raise ValueError(f"{field_name} должен содержать только строковые ключи и значения")
        key = raw_key.strip()
        value = raw_value.strip()
        if key and value:
            cleaned[key] = value
    return cleaned


@dataclass(slots=True)
class UserProfile:
    """One named personalization profile."""

    name: str
    language: str = ""
    style: str = ""
    format: str = ""
    audience: str = ""
    preferences: dict[str, str] = field(default_factory=dict)
    constraints: dict[str, str] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        self.name = normalize_profile_name(self.name)
        for field_name in PROFILE_FIELDS:
            setattr(self, field_name, _clean_string(getattr(self, field_name)))
        self.preferences = _validate_string_map(self.preferences, "preferences")
        self.constraints = _validate_string_map(self.constraints, "constraints")
        if not self.created_at:
            self.created_at = _now()
        if not self.updated_at:
            self.updated_at = self.created_at

    @property
    def active(self) -> bool:
        return any(
            (
                self.language,
                self.style,
                self.format,
                self.audience,
                self.preferences,
                self.constraints,
            )
        )

    @property
    def fields_count(self) -> int:
        scalar_count = sum(1 for field_name in PROFILE_FIELDS if getattr(self, field_name))
        return scalar_count + len(self.preferences) + len(self.constraints)

    def set_field(self, field_name: str, value: str) -> None:
        if field_name not in PROFILE_FIELDS:
            raise ValueError(f"Неизвестное поле профиля: {field_name}")
        setattr(self, field_name, _clean_string(value))
        self.updated_at = _now()

    def set_preference(self, key: str, value: str) -> None:
        checked_key = key.strip()
        checked_value = value.strip()
        if not checked_key:
            raise ValueError("Ключ preference не должен быть пустым")
        if not checked_value:
            raise ValueError("Значение preference не должно быть пустым")
        self.preferences[checked_key] = checked_value
        self.updated_at = _now()

    def set_constraint(self, key: str, value: str) -> None:
        checked_key = key.strip()
        checked_value = value.strip()
        if not checked_key:
            raise ValueError("Ключ constraint не должен быть пустым")
        if not checked_value:
            raise ValueError("Значение constraint не должно быть пустым")
        self.constraints[checked_key] = checked_value
        self.updated_at = _now()

    def reset(self) -> None:
        for field_name in PROFILE_FIELDS:
            setattr(self, field_name, "")
        self.preferences.clear()
        self.constraints.clear()
        self.updated_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> UserProfile:
        if not isinstance(payload, dict):
            raise ValueError("profile должен быть JSON-объектом")
        name = payload.get("name")
        if not isinstance(name, str):
            raise ValueError("profile.name должен быть строкой")
        kwargs: dict[str, Any] = {"name": name}
        for field_name in PROFILE_FIELDS:
            value = payload.get(field_name, "")
            if value is None:
                value = ""
            if not isinstance(value, str):
                raise ValueError(f"profile.{field_name} должен быть строкой")
            kwargs[field_name] = value
        kwargs["preferences"] = _validate_string_map(payload.get("preferences", {}), "preferences")
        kwargs["constraints"] = _validate_string_map(payload.get("constraints", {}), "constraints")
        for timestamp in ("created_at", "updated_at"):
            value = payload.get(timestamp, "")
            if value is None:
                value = ""
            if not isinstance(value, str):
                raise ValueError(f"profile.{timestamp} должен быть строкой")
            kwargs[timestamp] = value
        return cls(**kwargs)


@dataclass(slots=True)
class UserProfiles:
    """Collection of named personalization profiles."""

    active_profile: str = ""
    profiles: dict[str, UserProfile] = field(default_factory=dict)
    updated_at: str = ""

    def __post_init__(self) -> None:
        normalized: dict[str, UserProfile] = {}
        for name, profile in self.profiles.items():
            checked_name = normalize_profile_name(name)
            if checked_name != profile.name:
                raise ValueError("Ключ профиля должен совпадать с profile.name")
            normalized[checked_name] = profile
        self.profiles = normalized
        if self.active_profile:
            self.active_profile = normalize_profile_name(self.active_profile)
            if self.active_profile not in self.profiles:
                self.active_profile = ""
        if not self.updated_at:
            self.updated_at = _now()

    @property
    def active(self) -> bool:
        profile = self.get_active()
        return profile is not None and profile.active

    def get_active(self) -> UserProfile | None:
        if not self.active_profile:
            return None
        return self.profiles.get(self.active_profile)

    def create(self, name: str) -> UserProfile:
        checked_name = normalize_profile_name(name)
        if checked_name in self.profiles:
            raise ValueError(f"Профиль уже существует: {checked_name}")
        profile = UserProfile(name=checked_name)
        self.profiles[checked_name] = profile
        self.active_profile = checked_name
        self.updated_at = _now()
        return profile

    def use(self, name: str) -> UserProfile:
        checked_name = normalize_profile_name(name)
        profile = self.profiles.get(checked_name)
        if profile is None:
            raise ValueError(f"Профиль не найден: {checked_name}")
        self.active_profile = checked_name
        self.updated_at = _now()
        return profile

    def require_active(self) -> UserProfile:
        profile = self.get_active()
        if profile is None:
            raise ValueError("Сначала создайте профиль: /profile create <name>")
        return profile

    def reset_active(self) -> UserProfile:
        profile = self.require_active()
        profile.reset()
        self.updated_at = _now()
        return profile

    def reset_all(self) -> None:
        self.profiles.clear()
        self.active_profile = ""
        self.updated_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PROFILE_SCHEMA_VERSION,
            "active_profile": self.active_profile,
            "profiles": {
                name: profile.to_dict()
                for name, profile in sorted(self.profiles.items(), key=lambda item: item[0])
            },
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> UserProfiles:
        if not isinstance(payload, dict):
            raise ValueError("user_profiles должен быть JSON-объектом")
        schema_version = payload.get("schema_version", PROFILE_SCHEMA_VERSION)
        if schema_version != PROFILE_SCHEMA_VERSION:
            raise ValueError(f"Неподдерживаемая версия user_profiles: {schema_version}")
        active_profile = payload.get("active_profile", "")
        if active_profile is None:
            active_profile = ""
        if not isinstance(active_profile, str):
            raise ValueError("active_profile должен быть строкой")
        raw_profiles = payload.get("profiles", {})
        if not isinstance(raw_profiles, dict):
            raise ValueError("profiles должен быть JSON-объектом")
        profiles: dict[str, UserProfile] = {}
        for name, raw_profile in raw_profiles.items():
            if not isinstance(name, str):
                raise ValueError("profiles keys должны быть строками")
            profile = UserProfile.from_dict(raw_profile)
            checked_name = normalize_profile_name(name)
            if checked_name != profile.name:
                raise ValueError("Ключ профиля должен совпадать с profile.name")
            profiles[checked_name] = profile
        updated_at = payload.get("updated_at", "")
        if updated_at is None:
            updated_at = ""
        if not isinstance(updated_at, str):
            raise ValueError("updated_at должен быть строкой")
        return cls(active_profile=active_profile, profiles=profiles, updated_at=updated_at)


class JsonUserProfileStore:
    """JSON store for personalization profiles."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    def load(self) -> UserProfiles:
        if not self.path.exists():
            return UserProfiles()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"Не удалось разобрать user profiles {self.path}: {error}") from error
        return UserProfiles.from_dict(payload)

    def save(self, profiles: UserProfiles) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(profiles.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()


class UserProfileEventStore:
    """Append-only JSONL audit log for profile commands."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    def append(
        self,
        *,
        action: str,
        profile: str | None = None,
        field: str | None = None,
        key: str | None = None,
        value: str | None = None,
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": PROFILE_EVENT_SCHEMA_VERSION,
            "created_at": _now(),
            "action": action,
            "profile": profile,
            "field": field,
            "key": key,
            "value": value,
        }
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
                raise ValueError(
                    f"Не удалось разобрать profile event {self.path}, строка {line_number}: {error}"
                ) from error
            if not isinstance(payload, dict):
                raise ValueError(f"profile event должен быть объектом, строка {line_number}")
            events.append(payload)
        return events


def build_profile_prompt_message(
    profiles: UserProfiles,
    token_counter: ApproxTokenCounter | None = None,
) -> tuple[Message | None, int, int]:
    """Build a system prompt message for the active non-empty profile."""

    profile = profiles.get_active()
    if profile is None or not profile.active:
        return None, 0, 0

    lines = [
        (
            "User profile preferences. Treat this as personalization guidance, "
            "not as a higher-priority instruction than the current user request."
        ),
        f"- profile: {profile.name}",
    ]
    for field_name in PROFILE_FIELDS:
        value = getattr(profile, field_name)
        if value:
            lines.append(f"- {field_name}: {value}")
    if profile.preferences:
        lines.append("- preferences:")
        lines.extend(f"  - {key}: {value}" for key, value in sorted(profile.preferences.items()))
    if profile.constraints:
        lines.append("- constraints:")
        lines.extend(f"  - {key}: {value}" for key, value in sorted(profile.constraints.items()))

    message: Message = {"role": "system", "content": "\n".join(lines)}
    counter = token_counter or ApproxTokenCounter()
    return message, profile.fields_count, counter.count_message(message)


__all__ = [
    "PROFILE_FIELDS",
    "JsonUserProfileStore",
    "UserProfile",
    "UserProfileEventStore",
    "UserProfiles",
    "build_profile_prompt_message",
    "normalize_profile_name",
]
