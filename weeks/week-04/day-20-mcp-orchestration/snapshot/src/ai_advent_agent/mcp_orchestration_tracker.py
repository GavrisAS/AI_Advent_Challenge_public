"""Deterministic Tracker MCP server for Day 20 multi-server orchestration."""

from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ai_advent_agent.mcp_mock_api import MOCK_TRACKER_ISSUES, TrackerIssue

TrackerStatus = Literal["done", "in_progress", "planned"]


class OrchestrationIssuePayload(TypedDict):
    issue_key: str
    title: str
    status: str
    priority: str
    summary: str
    tags: list[str]


DAY20_TRACKER_ISSUES: dict[str, TrackerIssue] = {
    **MOCK_TRACKER_ISSUES,
    "AI-19": TrackerIssue(
        issue_key="AI-19",
        title="Реализовать композицию MCP tools",
        status="done",
        assignee="student",
        priority="high",
        summary=(
            "Собрать LLM-driven pipeline search, deterministic report и safe file save "
            "внутри одного stdio MCP server."
        ),
    ),
    "AI-20": TrackerIssue(
        issue_key="AI-20",
        title="Оркестрировать несколько MCP servers",
        status="planned",
        assignee="student",
        priority="high",
        summary=(
            "Добавить discovery, normalized registry, neutral JSON planner и routing между "
            "четырьмя локальными stdio MCP servers."
        ),
    ),
}


def build_tracker_server() -> FastMCP:
    """Build the isolated Tracker server used by the orchestration host."""

    server = FastMCP("AI Advent Orchestration Tracker")

    @server.tool(structured_output=True)
    def search_tracker_issues(
        status: Annotated[
            TrackerStatus | None,
            Field(description="Optional status filter: done, in_progress, planned or null."),
        ] = None,
        tag: Annotated[
            str | None,
            Field(description="Optional tag filter. Week 04 issues use the mcp tag."),
        ] = None,
        limit: Annotated[int, Field(description="Maximum results.", ge=1, le=50)] = 10,
    ) -> dict[str, object]:
        """Search deterministic mock Tracker issues by status and tag."""

        normalized_tag = tag.strip().casefold() if tag else None
        issues: list[OrchestrationIssuePayload] = []
        for issue in sorted(DAY20_TRACKER_ISSUES.values(), key=lambda item: item.issue_key):
            tags = ["mcp", "week-04"]
            if status is not None and issue.status != status:
                continue
            if normalized_tag is not None and normalized_tag not in tags:
                continue
            issues.append(_issue_payload(issue, tags))
            if len(issues) >= limit:
                break
        return {
            "query": {"status": status, "tag": normalized_tag, "limit": limit},
            "issue_count": len(issues),
            "issues": issues,
        }

    @server.tool(structured_output=True)
    def get_tracker_issue(
        issue_key: Annotated[str, Field(description="Mock Tracker key, for example AI-18.")],
    ) -> OrchestrationIssuePayload:
        """Return one deterministic mock Tracker issue."""

        normalized = issue_key.strip().upper()
        issue = DAY20_TRACKER_ISSUES.get(normalized)
        if issue is None:
            raise ValueError(
                f"Unknown mock Tracker issue: {normalized}. "
                f"Known issues: {', '.join(sorted(DAY20_TRACKER_ISSUES))}"
            )
        return _issue_payload(issue, ["mcp", "week-04"])

    return server


def _issue_payload(issue: TrackerIssue, tags: list[str]) -> OrchestrationIssuePayload:
    return {
        "issue_key": issue.issue_key,
        "title": issue.title,
        "status": issue.status,
        "priority": issue.priority,
        "summary": issue.summary,
        "tags": tags,
    }


mcp = build_tracker_server()
