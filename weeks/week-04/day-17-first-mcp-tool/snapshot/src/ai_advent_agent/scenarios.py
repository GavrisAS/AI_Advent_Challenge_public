"""CLI scenario for the self-contained Day 17 snapshot."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from ai_advent_agent.mcp_tool_client import (
    DEFAULT_MCP_TOOL_TIMEOUT_SECONDS,
    LOCAL_MCP_TRANSPORT,
    McpToolDemoError,
    call_tracker_issue_tool,
    write_tool_demo_outputs,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Advent Day 17 MCP tool scenario.")
    subparsers = parser.add_subparsers(dest="scenario", required=True)
    mcp_tool = subparsers.add_parser(
        "mcp-tool-demo",
        help="Run a local stdio MCP server and call its mock Tracker tool.",
    )
    mcp_tool.add_argument("--issue-key", default="AI-17")
    mcp_tool.add_argument("--include-comments", action="store_true")
    mcp_tool.add_argument("--timeout-seconds", type=float, default=DEFAULT_MCP_TOOL_TIMEOUT_SECONDS)
    mcp_tool.add_argument("--output-dir", type=Path, default=Path("../artifacts"))
    mcp_tool.add_argument(
        "--results-file",
        type=Path,
        default=Path("../results/day-17-first-mcp-tool.md"),
    )
    return parser.parse_args(argv)


def scenario_mcp_tool_demo(
    *,
    issue_key: str,
    include_comments: bool,
    timeout_seconds: float,
    output_dir: Path,
    results_file: Path,
) -> None:
    print("# Day 17 MCP tool demo")
    print(f"Transport: {LOCAL_MCP_TRANSPORT}")
    print("Server: python -m ai_advent_agent.mcp_tool_server")
    print("Tool: get_tracker_issue")
    print(f"Issue key: {issue_key}")
    print(f"Include comments: {include_comments}")
    try:
        result = asyncio.run(
            call_tracker_issue_tool(
                issue_key=issue_key,
                include_comments=include_comments,
                timeout_seconds=timeout_seconds,
            )
        )
    except McpToolDemoError as error:
        print(f"MCP tool demo failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    tools_path, call_result_path, agent_markdown_path, report_path = write_tool_demo_outputs(
        result,
        output_dir,
        results_file,
    )
    print("Initialization: successful")
    print(f"Protocol version: {result.protocol_version}")
    print(f"Tool count: {len(result.tools)}")
    print("Tools:")
    for tool in result.tools:
        print(f"- {tool.name}")
    print(f"Normalized issue: {result.tool_result['issue_key']}")
    print(f"Issue status: {result.tool_result['status']}")
    print(f"Tools list: {tools_path}")
    print(f"Tool call result: {call_result_path}")
    print(f"Agent used result: {agent_markdown_path}")
    print(f"Results: {report_path}")
    print("Tool calls: 1")
    print("LLM API calls: 0")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    scenario_mcp_tool_demo(
        issue_key=args.issue_key,
        include_comments=args.include_comments,
        timeout_seconds=args.timeout_seconds,
        output_dir=args.output_dir,
        results_file=args.results_file,
    )


if __name__ == "__main__":
    main()

