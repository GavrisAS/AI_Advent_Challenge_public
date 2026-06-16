"""Token/cost report models and JSONL persistence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class TokenReport:
    """Token statistics for one agent turn."""

    request_tokens_estimated: int
    history_tokens_before_estimated: int
    prompt_tokens_estimated: int
    projected_total_tokens_estimated: int
    context_window_tokens: int
    context_usage_ratio: float
    projected_usage_ratio: float
    warn_threshold_reached: bool
    overflow_detected: bool
    overflow_policy: str
    trimmed_messages_count: int = 0
    summary_active: bool = False
    summary_tokens_estimated: int = 0
    summarized_messages_count: int = 0
    memory_layers_active: bool = False
    memory_layer_entries: dict[str, int] = field(default_factory=dict)
    memory_layer_tokens_estimated: dict[str, int] = field(default_factory=dict)
    memory_prompt_tokens_estimated: int = 0
    prompt_assembly_order: list[str] = field(default_factory=list)
    response_tokens_estimated: int | None = None
    history_tokens_after_response_estimated: int | None = None
    prompt_tokens_actual: int | None = None
    completion_tokens_actual: int | None = None
    total_tokens_actual: int | None = None
    estimated_input_cost_usd: float | None = None
    estimated_output_cost_usd: float | None = None
    estimated_total_cost_usd: float | None = None
    elapsed_seconds: float | None = None
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(UTC).isoformat()

    @property
    def actual_usage_available(self) -> bool:
        return self.total_tokens_actual is not None

    @property
    def context_usage_percent(self) -> float:
        return self.context_usage_ratio * 100

    @property
    def projected_usage_percent(self) -> float:
        return self.projected_usage_ratio * 100

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TokenReportStore:
    """Append-only JSONL store for token reports."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    def append(self, report: TokenReport) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(report.to_dict(), ensure_ascii=False) + "\n")

    def load_all(self) -> list[TokenReport]:
        if not self.path.exists():
            return []

        reports: list[TokenReport] = []
        for line_number, raw_line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
                reports.append(TokenReport(**payload))
            except (json.JSONDecodeError, TypeError) as error:
                raise ValueError(
                    "Не удалось разобрать token report "
                    f"в {self.path}, строка {line_number}: {error}"
                ) from error
        return reports

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()


__all__ = ["TokenReport", "TokenReportStore"]
