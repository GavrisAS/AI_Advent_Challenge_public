from __future__ import annotations

import asyncio
import json
import os
import socket
from pathlib import Path

import pytest
from mcp.types import Tool

from ai_advent_agent.mcp_connection import (
    DEFAULT_MCP_SERVER_URL,
    EXPECTED_DEEPWIKI_TOOLS,
    McpConnectionError,
    McpConnectionResult,
    NormalizedTool,
    classify_mcp_error,
    compare_expected_tools,
    discover_mcp_tools,
    normalize_tool,
    validate_server_url,
    write_error_artifact,
    write_success_outputs,
)
from ai_advent_agent.scenarios import parse_args


def test_normalize_tool_uses_stable_json_fields() -> None:
    tool = Tool(
        name="search_docs",
        description="Search documentation",
        inputSchema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )

    normalized = normalize_tool(tool)

    assert normalized.to_dict() == {
        "name": "search_docs",
        "description": "Search documentation",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    }


def test_compare_expected_tools_reports_missing_and_extra_in_stable_order() -> None:
    missing, extra = compare_expected_tools(
        {"read_wiki_structure", "new_tool"}, EXPECTED_DEEPWIKI_TOOLS
    )

    assert missing == ("ask_question", "read_wiki_contents")
    assert extra == ("new_tool",)


def test_result_serializes_to_json_and_sorts_tools_in_payload_order(tmp_path: Path) -> None:
    result = McpConnectionResult(
        server_url=DEFAULT_MCP_SERVER_URL,
        timestamp_utc="2026-06-23T12:00:00Z",
        sdk_version="1.28.0",
        protocol_version="2025-11-25",
        server_name="DeepWiki",
        server_version="1.0.0",
        tools=(
            NormalizedTool("ask_question", "Ask", {"type": "object"}),
            NormalizedTool("read_wiki_contents", "Read", {"type": "object"}),
            NormalizedTool("read_wiki_structure", "List", {"type": "object"}),
        ),
        expected_tools=tuple(sorted(EXPECTED_DEEPWIKI_TOOLS)),
        missing_expected_tools=(),
        extra_tools=(),
    )

    result_path, tools_path, report_path = write_success_outputs(
        result, tmp_path / "artifacts", tmp_path / "results.md"
    )

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    tools_payload = json.loads(tools_path.read_text(encoding="utf-8"))
    assert payload["connected"] is True
    assert payload["initialized"] is True
    assert payload["expected_tools_present"] is True
    assert payload["tool_count"] == 3
    assert [tool["name"] for tool in tools_payload["tools"]] == [
        "ask_question",
        "read_wiki_contents",
        "read_wiki_structure",
    ]
    assert "Tools вызывались: нет" in report_path.read_text(encoding="utf-8")


def test_classify_mcp_errors() -> None:
    assert classify_mcp_error(TimeoutError()) == "timeout"
    assert classify_mcp_error(socket.gaierror("name or service not known")) == "dns"
    assert classify_mcp_error(ConnectionRefusedError()) == "connectivity"
    assert classify_mcp_error(RuntimeError("invalid initialize response")) == "protocol"


def test_error_artifact_is_explicitly_unsuccessful(tmp_path: Path) -> None:
    error = McpConnectionError("timeout", "timed out")
    path = write_error_artifact(error, DEFAULT_MCP_SERVER_URL, tmp_path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["connected"] is False
    assert payload["initialized"] is False
    assert payload["error_kind"] == "timeout"
    assert not (tmp_path / "mcp-connection-result.json").exists()


@pytest.mark.parametrize(
    "server_url",
    ["deepwiki.example/mcp", "file:///tmp/server", "https://user:secret@example.com/mcp"],
)
def test_validate_server_url_rejects_invalid_or_credentialed_urls(server_url: str) -> None:
    with pytest.raises(ValueError):
        validate_server_url(server_url)


def test_cli_mcp_connection_defaults_and_overrides(tmp_path: Path) -> None:
    defaults = parse_args(["mcp-connection-demo"])
    assert defaults.server_url == DEFAULT_MCP_SERVER_URL
    assert defaults.timeout_seconds == 30.0

    parsed = parse_args(
        [
            "mcp-connection-demo",
            "--server-url",
            "https://example.com/mcp",
            "--timeout-seconds",
            "15",
            "--output-dir",
            str(tmp_path / "artifacts"),
            "--results-file",
            str(tmp_path / "result.md"),
        ]
    )
    assert parsed.server_url == "https://example.com/mcp"
    assert parsed.timeout_seconds == 15.0
    assert parsed.output_dir == tmp_path / "artifacts"
    assert parsed.results_file == tmp_path / "result.md"


@pytest.mark.skipif(
    os.getenv("AI_ADVENT_RUN_MCP_INTEGRATION") != "1",
    reason="remote MCP integration test is opt-in",
)
def test_deepwiki_remote_mcp_discovery() -> None:
    result = asyncio.run(discover_mcp_tools())

    assert result.tools
    assert result.server_url == DEFAULT_MCP_SERVER_URL
    assert not result.missing_expected_tools
