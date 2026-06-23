"""Local stdio MCP server exposing the Day 17 mock Tracker tool."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ai_advent_agent.mcp_mock_api import (
    TrackerIssuePayload,
    UnknownTrackerIssueError,
    get_issue,
)

mcp = FastMCP("AI Advent Mock Tracker")


@mcp.tool(structured_output=True)
def get_tracker_issue(
    issue_key: Annotated[str, Field(description="Issue key, for example AI-17.")],
    include_comments: Annotated[
        bool,
        Field(description="Whether to include issue comments in the result."),
    ] = False,
) -> TrackerIssuePayload:
    """Return a mock tracker issue by key.

    Args:
        issue_key: Issue key, for example AI-17.
        include_comments: Whether to include issue comments in the result.
    """

    try:
        return get_issue(issue_key, include_comments=include_comments)
    except UnknownTrackerIssueError as error:
        raise ValueError(str(error)) from error


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
