"""Small .env loader without external dependencies."""

from __future__ import annotations

import os
from pathlib import Path


def _candidate_env_paths() -> list[Path]:
    """Return likely .env locations for both flat and src-based project layouts."""

    candidates: list[Path] = []

    # Most common case: command is started from the project root.
    cwd = Path.cwd().resolve()
    candidates.append(cwd / ".env")
    candidates.extend(parent / ".env" for parent in cwd.parents)

    # Also support running the module from a package directory or src layout.
    module_path = Path(__file__).resolve()
    candidates.append(module_path.parent / ".env")
    candidates.extend(parent / ".env" for parent in module_path.parents)

    # Preserve order and remove duplicates.
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in candidates:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def load_env_file(env_path: Path | None = None) -> Path | None:
    """Load KEY=VALUE pairs from .env without overwriting existing env vars.

    Returns the path that was loaded, or None when no .env file was found.
    """

    paths = [env_path] if env_path is not None else _candidate_env_paths()

    for candidate in paths:
        if candidate is None:
            continue
        path = candidate.expanduser().resolve()
        if not path.exists():
            continue

        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()

            if not line or line.startswith("#"):
                continue

            if line.startswith("export "):
                line = line.removeprefix("export ").strip()

            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key:
                os.environ.setdefault(key, value)

        return path

    return None
