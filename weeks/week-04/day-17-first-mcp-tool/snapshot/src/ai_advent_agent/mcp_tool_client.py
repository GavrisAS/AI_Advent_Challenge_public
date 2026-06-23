"""Stdio MCP client helpers for the Day 17 local tool demo."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any, cast

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult, TextContent, Tool

from ai_advent_agent.mcp_mock_api import TrackerIssuePayload

LOCAL_MCP_TRANSPORT = "stdio"
TRACKER_TOOL_NAME = "get_tracker_issue"
DEFAULT_MCP_TOOL_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True, slots=True)
class NormalizedMcpTool:
    name: str
    description: str | None
    input_schema: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass(frozen=True, slots=True)
class McpToolDemoResult:
    timestamp_utc: str
    sdk_version: str
    protocol_version: str
    server_name: str
    server_version: str
    issue_key: str
    include_comments: bool
    tools: tuple[NormalizedMcpTool, ...]
    tool_result: TrackerIssuePayload
    raw_call_result: dict[str, object]

    def tools_list_dict(self) -> dict[str, object]:
        return {
            "transport": LOCAL_MCP_TRANSPORT,
            "server_command": ["python", "-m", "ai_advent_agent.mcp_tool_server"],
            "tool_count": len(self.tools),
            "tools": [tool.to_dict() for tool in self.tools],
        }

    def call_result_dict(self) -> dict[str, object]:
        return {
            "transport": LOCAL_MCP_TRANSPORT,
            "tool_name": TRACKER_TOOL_NAME,
            "arguments": {
                "issue_key": self.issue_key,
                "include_comments": self.include_comments,
            },
            "is_error": False,
            "normalized_result": self.tool_result,
            "raw_call_result": self.raw_call_result,
        }


class McpToolDemoError(RuntimeError):
    """Raised when local MCP tool discovery or execution cannot be normalized."""


def normalize_tool(tool: Tool) -> NormalizedMcpTool:
    schema = cast(dict[str, object], json.loads(json.dumps(tool.inputSchema)))
    return NormalizedMcpTool(
        name=tool.name,
        description=tool.description,
        input_schema=schema,
    )


async def call_tracker_issue_tool(
    *,
    issue_key: str,
    include_comments: bool = False,
    timeout_seconds: float = DEFAULT_MCP_TOOL_TIMEOUT_SECONDS,
) -> McpToolDemoResult:
    """Start the local stdio MCP server and call get_tracker_issue through MCP."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")

    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "ai_advent_agent.mcp_tool_server"],
        env=server_environment(),
    )
    try:
        async with asyncio.timeout(timeout_seconds):
            async with stdio_client(server) as (read_stream, write_stream):
                async with ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=timedelta(seconds=timeout_seconds),
                ) as session:
                    initialization = await session.initialize()
                    tools_page = await session.list_tools()
                    tools = tuple(
                        sorted(
                            (normalize_tool(tool) for tool in tools_page.tools),
                            key=lambda tool: tool.name,
                        )
                    )
                    if TRACKER_TOOL_NAME not in {tool.name for tool in tools}:
                        raise McpToolDemoError(
                            f"Local MCP server did not expose {TRACKER_TOOL_NAME!r}"
                        )
                    call_result = await session.call_tool(
                        TRACKER_TOOL_NAME,
                        arguments={
                            "issue_key": issue_key,
                            "include_comments": include_comments,
                        },
                    )
    except TimeoutError as error:
        raise McpToolDemoError(
            f"Local MCP tool call timed out after {timeout_seconds:g} seconds"
        ) from error

    if call_result.isError:
        raise McpToolDemoError(f"Local MCP tool returned an error: {call_result!r}")

    normalized_result = extract_tracker_issue_payload(call_result)
    return McpToolDemoResult(
        timestamp_utc=utc_timestamp(),
        sdk_version=package_version("mcp"),
        protocol_version=str(initialization.protocolVersion),
        server_name=initialization.serverInfo.name,
        server_version=initialization.serverInfo.version,
        issue_key=issue_key,
        include_comments=include_comments,
        tools=tools,
        tool_result=normalized_result,
        raw_call_result=json_compatible(call_result.model_dump(by_alias=True)),
    )


def extract_tracker_issue_payload(call_result: CallToolResult) -> TrackerIssuePayload:
    """Normalize supported MCP call result shapes into a tracker issue payload."""

    if call_result.structuredContent is not None:
        return validate_tracker_issue_payload(call_result.structuredContent)

    for block in call_result.content:
        if isinstance(block, TextContent):
            try:
                payload = json.loads(block.text)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return validate_tracker_issue_payload(payload)

    raise McpToolDemoError(
        "MCP call result did not contain structuredContent or text JSON payload"
    )


def validate_tracker_issue_payload(payload: dict[str, Any]) -> TrackerIssuePayload:
    required = {"issue_key", "title", "status", "assignee", "priority", "summary", "comments"}
    missing = sorted(required - set(payload))
    if missing:
        raise McpToolDemoError("MCP tool result is missing fields: " + ", ".join(missing))
    comments = payload["comments"]
    if not isinstance(comments, list):
        raise McpToolDemoError("MCP tool result field 'comments' must be a list")
    return cast(TrackerIssuePayload, json_compatible(payload))


def json_compatible(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def server_environment() -> dict[str, str]:
    env = dict(os.environ)
    src_dir = str(Path(__file__).resolve().parents[1])
    current_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        src_dir if not current_pythonpath else os.pathsep.join([src_dir, current_pythonpath])
    )
    return env


def build_agent_used_tool_markdown(result: McpToolDemoResult) -> str:
    issue = result.tool_result
    next_action = build_next_action(issue)
    comments = "\n".join(
        f"- {comment['author']}: {comment['text']}" for comment in issue["comments"]
    )
    comments_block = comments or "- Комментарии не запрашивались."
    return f"""# MCP Tool Result Used by Agent

Agent called `{TRACKER_TOOL_NAME}` for `{issue['issue_key']}` through the local MCP server.

## Issue

- Key: {issue['issue_key']}
- Title: {issue['title']}
- Status: {issue['status']}
- Priority: {issue['priority']}
- Assignee: {issue['assignee']}

## Summary

{issue['summary']}

## Comments

{comments_block}

## Agent conclusion

The next action is to {next_action}.
"""


def build_next_action(issue: TrackerIssuePayload) -> str:
    if issue["status"] == "done":
        return "keep the completed MCP work documented and use it as a baseline"
    if issue["priority"] == "high":
        return (
            "keep the local stdio MCP tool integration read-only, documented, and ready for "
            "extension in Day 18"
        )
    return "prepare the next MCP extension without adding external services or secrets"


def write_tool_demo_outputs(
    result: McpToolDemoResult, output_dir: Path, results_file: Path
) -> tuple[Path, Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results_file.parent.mkdir(parents=True, exist_ok=True)

    tools_path = output_dir / "tools-list.json"
    call_result_path = output_dir / "mcp-tool-call-result.json"
    agent_markdown_path = output_dir / "agent-used-tool-result.md"

    write_json(tools_path, result.tools_list_dict())
    write_json(call_result_path, result.call_result_dict())
    agent_markdown = build_agent_used_tool_markdown(result)
    agent_markdown_path.write_text(agent_markdown, encoding="utf-8")
    results_file.write_text(build_results_markdown(result, output_dir), encoding="utf-8")
    return tools_path, call_result_path, agent_markdown_path, results_file


def build_results_markdown(result: McpToolDemoResult, output_dir: Path) -> str:
    issue = result.tool_result
    tool_rows = "\n".join(
        f"| `{tool.name}` | {markdown_cell(tool.description or '—')} |"
        for tool in result.tools
    )
    return f"""# Day 17 — Первый MCP Tool

Сценарий выполнен локально через stdio MCP server, без внешней сети, API key и LLM API.

## MCP server и tool

- Server: `{result.server_name} {result.server_version}`
- Transport: `{LOCAL_MCP_TRANSPORT}`
- Protocol version: `{result.protocol_version}`
- MCP Python SDK: `{result.sdk_version}`
- Tool: `{TRACKER_TOOL_NAME}`
- Arguments: `issue_key={result.issue_key}`, `include_comments={result.include_comments}`
- Timestamp UTC: `{result.timestamp_utc}`

| Tool | Description |
|---|---|
{tool_rows}

## Полученный результат

- Key: `{issue['issue_key']}`
- Title: {issue['title']}
- Status: `{issue['status']}`
- Priority: `{issue['priority']}`
- Assignee: `{issue['assignee']}`
- Comments returned: `{len(issue['comments'])}`

## Как агент использовал результат

Агентский слой сформировал Markdown-резюме задачи, выделил статус, приоритет, исполнителя и
следующее действие. Итог сохранён в `agent-used-tool-result.md`.

Next action: {build_next_action(issue)}.

## Артефакты

JSON и Markdown outputs сформированы в `{output_dir}`:

- `tools-list.json`
- `mcp-tool-call-result.json`
- `agent-used-tool-result.md`
"""


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def markdown_cell(value: str) -> str:
    return " ".join(value.replace("|", "\\|").split())


def utc_timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
