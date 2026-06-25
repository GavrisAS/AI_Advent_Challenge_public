"""Local stdio MCP server exposing deterministic Day 19 composition tools."""

from __future__ import annotations

import hashlib
import os
from collections import Counter
from pathlib import Path
from typing import Annotated, Literal, TypedDict

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ai_advent_agent.mcp_mock_api import MOCK_TRACKER_ISSUES

TrackerStatus = Literal["done", "in_progress", "planned"]
TrackerPriority = Literal["high", "medium", "low"]

COMPOSITION_OUTPUT_DIR_ENV = "AI_ADVENT_COMPOSITION_OUTPUT_DIR"


class CompositionIssuePayload(TypedDict):
    issue_key: str
    title: str
    status: str
    priority: str
    summary: str


class TrackerSearchQueryPayload(TypedDict):
    status: str | None
    priority: str | None
    query: str | None
    limit: int


class TrackerSearchResultPayload(TypedDict):
    query: TrackerSearchQueryPayload
    issues: list[CompositionIssuePayload]
    issue_count: int


class TrackerReportPayload(TypedDict):
    title: str
    issue_count: int
    status_counts: dict[str, int]
    priority_counts: dict[str, int]
    markdown: str


class SaveReportPayload(TypedDict):
    saved: bool
    path: str
    bytes_written: int
    sha256: str


mcp = FastMCP("AI Advent MCP Tool Composition")


@mcp.tool(structured_output=True)
def search_tracker_issues(
    status: Annotated[
        TrackerStatus | None,
        Field(description="Optional issue status filter: done, in_progress, planned or null."),
    ] = None,
    priority: Annotated[
        TrackerPriority | None,
        Field(description="Optional issue priority filter: high, medium, low or null."),
    ] = None,
    query: Annotated[
        str | None,
        Field(description="Optional case-insensitive text filter, for example Week 04 or MCP."),
    ] = None,
    limit: Annotated[
        int,
        Field(description="Maximum number of issues to return.", ge=1, le=50),
    ] = 10,
) -> TrackerSearchResultPayload:
    """Return filtered mock Tracker issues for MCP tool composition demos."""

    normalized_query = query.strip() if query else None
    issues: list[CompositionIssuePayload] = []
    for issue in sorted(MOCK_TRACKER_ISSUES.values(), key=lambda item: item.issue_key):
        if status is not None and issue.status != status:
            continue
        if priority is not None and issue.priority != priority:
            continue
        if normalized_query and not issue_matches_query(
            issue_key=issue.issue_key,
            fields=(
                issue.title,
                issue.status,
                issue.priority,
                issue.summary,
            ),
            query=normalized_query,
        ):
            continue
        issues.append(
            {
                "issue_key": issue.issue_key,
                "title": issue.title,
                "status": issue.status,
                "priority": issue.priority,
                "summary": issue.summary,
            }
        )
        if len(issues) >= limit:
            break

    return {
        "query": {
            "status": status,
            "priority": priority,
            "query": normalized_query,
            "limit": limit,
        },
        "issues": issues,
        "issue_count": len(issues),
    }


@mcp.tool(structured_output=True)
def build_tracker_report(
    issues: Annotated[
        list[CompositionIssuePayload],
        Field(description="Issues returned by search_tracker_issues."),
    ],
    report_title: Annotated[
        str,
        Field(description="Markdown report title."),
    ] = "Week 04 MCP progress report",
) -> TrackerReportPayload:
    """Build a deterministic Markdown report from Tracker issues without using an LLM."""

    title = report_title.strip() or "Tracker report"
    normalized_issues = sorted(issues, key=lambda item: item["issue_key"])
    status_counts = dict(sorted(Counter(issue["status"] for issue in normalized_issues).items()))
    priority_counts = dict(
        sorted(Counter(issue["priority"] for issue in normalized_issues).items())
    )
    issue_rows = "\n".join(
        ("- `{issue_key}` — {title}; status `{status}`, priority `{priority}`. {summary}").format(
            **issue
        )
        for issue in normalized_issues
    )
    issues_block = issue_rows or "- Нет задач, подходящих под фильтр."
    status_line = format_counts(status_counts)
    priority_line = format_counts(priority_counts)
    summary = (
        f"Итого найдено {len(normalized_issues)} задач. "
        f"Статусы: {status_line}. Приоритеты: {priority_line}."
    )
    markdown = f"""# {title}

## Counts

- Issues: `{len(normalized_issues)}`
- Status counts: `{status_counts}`
- Priority counts: `{priority_counts}`

## Issues

{issues_block}

## Итог

{summary}
"""
    return {
        "title": title,
        "issue_count": len(normalized_issues),
        "status_counts": status_counts,
        "priority_counts": priority_counts,
        "markdown": markdown,
    }


@mcp.tool(structured_output=True)
def save_report_to_file(
    markdown: Annotated[
        str,
        Field(description="Markdown content produced by build_tracker_report."),
    ],
    filename: Annotated[
        str,
        Field(description="Safe relative filename, for example tracker-composition-report.md."),
    ] = "tracker-composition-report.md",
) -> SaveReportPayload:
    """Save a Markdown report inside the configured local artifacts directory."""

    safe_filename = validate_safe_filename(filename)
    output_dir = configured_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / safe_filename
    data = markdown.encode("utf-8")
    path.write_bytes(data)
    return {
        "saved": True,
        "path": str(path),
        "bytes_written": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def issue_matches_query(*, issue_key: str, fields: tuple[str, ...], query: str) -> bool:
    normalized_query = query.casefold()
    searchable = " ".join((issue_key, *fields, "Week 04")).casefold()
    return normalized_query in searchable


def format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "нет"
    return ", ".join(f"{key}={value}" for key, value in counts.items())


def configured_output_dir() -> Path:
    raw_output_dir = os.environ.get(COMPOSITION_OUTPUT_DIR_ENV, "artifacts")
    return Path(raw_output_dir).expanduser()


def validate_safe_filename(filename: str) -> str:
    stripped = filename.strip()
    if not stripped:
        raise ValueError("filename must not be empty")
    candidate = Path(stripped)
    if candidate.is_absolute():
        raise ValueError("filename must be relative")
    if any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValueError("filename must not contain empty, current or parent path segments")
    if len(candidate.parts) != 1:
        raise ValueError("filename must not contain path separators")
    return candidate.name


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
