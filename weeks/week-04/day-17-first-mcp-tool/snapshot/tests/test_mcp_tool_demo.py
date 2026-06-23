from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

import pytest

from ai_advent_agent.mcp_mock_api import UnknownTrackerIssueError, get_issue
from ai_advent_agent.mcp_tool_client import (
    TRACKER_TOOL_NAME,
    build_agent_used_tool_markdown,
    call_tracker_issue_tool,
)
from ai_advent_agent.scenarios import parse_args, scenario_mcp_tool_demo


def test_mock_api_returns_day17_issue() -> None:
    issue = get_issue("AI-17", include_comments=True)

    assert issue["issue_key"] == "AI-17"
    assert issue["title"] == "Подключить первый MCP tool"
    assert issue["status"] == "in_progress"
    assert issue["comments"]


def test_mock_api_normalizes_lowercase_issue_key() -> None:
    issue = get_issue(" ai-17 ")

    assert issue["issue_key"] == "AI-17"
    assert issue["comments"] == []


def test_mock_api_unknown_issue_is_controlled_error() -> None:
    with pytest.raises(UnknownTrackerIssueError, match="Unknown mock tracker issue"):
        get_issue("AI-999")


def test_cli_mcp_tool_defaults_and_overrides(tmp_path: Path) -> None:
    defaults = parse_args(["mcp-tool-demo"])
    assert defaults.issue_key == "AI-17"
    assert defaults.include_comments is False
    assert defaults.timeout_seconds == 15.0

    parsed = parse_args(
        [
            "mcp-tool-demo",
            "--issue-key",
            "ai-16",
            "--include-comments",
            "--timeout-seconds",
            "5",
            "--output-dir",
            str(tmp_path / "artifacts"),
            "--results-file",
            str(tmp_path / "result.md"),
        ]
    )
    assert parsed.issue_key == "ai-16"
    assert parsed.include_comments is True
    assert parsed.timeout_seconds == 5.0
    assert parsed.output_dir == tmp_path / "artifacts"
    assert parsed.results_file == tmp_path / "result.md"


def test_local_mcp_server_exposes_tracker_tool_and_schema() -> None:
    result = asyncio.run(
        call_tracker_issue_tool(issue_key="AI-17", include_comments=False, timeout_seconds=10)
    )

    tools = {tool.name: tool for tool in result.tools}
    assert TRACKER_TOOL_NAME in tools
    schema = tools[TRACKER_TOOL_NAME].input_schema
    assert schema["type"] == "object"
    assert schema["required"] == ["issue_key"]
    properties = cast(dict[str, dict[str, Any]], schema["properties"])
    assert properties["issue_key"]["type"] == "string"
    assert properties["include_comments"]["type"] == "boolean"
    assert properties["include_comments"]["default"] is False


def test_mcp_client_calls_tracker_tool_through_stdio() -> None:
    result = asyncio.run(
        call_tracker_issue_tool(issue_key="ai-17", include_comments=True, timeout_seconds=10)
    )

    assert result.tool_result["issue_key"] == "AI-17"
    assert result.tool_result["title"] == "Подключить первый MCP tool"
    assert result.tool_result["comments"]
    assert result.raw_call_result["isError"] is False


def test_agent_markdown_uses_tool_result() -> None:
    result = asyncio.run(
        call_tracker_issue_tool(issue_key="AI-17", include_comments=True, timeout_seconds=10)
    )

    markdown = build_agent_used_tool_markdown(result)

    assert "Подключить первый MCP tool" in markdown
    assert "Status: in_progress" in markdown
    assert "keep the local stdio MCP tool integration read-only" in markdown


def test_mcp_tool_demo_scenario_creates_artifacts_and_results(tmp_path: Path) -> None:
    output_dir = tmp_path / "artifacts"
    results_file = tmp_path / "results" / "day-17-first-mcp-tool.md"

    scenario_mcp_tool_demo(
        issue_key="AI-17",
        include_comments=True,
        timeout_seconds=10,
        output_dir=output_dir,
        results_file=results_file,
    )

    tools_payload = json.loads((output_dir / "tools-list.json").read_text(encoding="utf-8"))
    call_payload = json.loads(
        (output_dir / "mcp-tool-call-result.json").read_text(encoding="utf-8")
    )
    agent_markdown = (output_dir / "agent-used-tool-result.md").read_text(encoding="utf-8")
    results_markdown = results_file.read_text(encoding="utf-8")

    assert [tool["name"] for tool in tools_payload["tools"]] == [TRACKER_TOOL_NAME]
    assert call_payload["normalized_result"]["issue_key"] == "AI-17"
    assert "Подключить первый MCP tool" in agent_markdown
    assert "Agent conclusion" in agent_markdown
    assert "Tool calls: 1" not in results_markdown
    assert "Next action:" in results_markdown
