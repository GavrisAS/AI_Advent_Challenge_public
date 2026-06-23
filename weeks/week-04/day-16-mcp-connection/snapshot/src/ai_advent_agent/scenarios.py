"""CLI scenario for the self-contained Day 16 snapshot."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from ai_advent_agent.mcp_connection import (
    DEFAULT_MCP_SERVER_URL,
    DEFAULT_MCP_TIMEOUT_SECONDS,
    MCP_TRANSPORT,
    McpConnectionError,
    discover_mcp_tools,
    write_error_artifact,
    write_success_outputs,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Advent Day 16 MCP scenario.")
    subparsers = parser.add_subparsers(dest="scenario", required=True)
    connection = subparsers.add_parser(
        "mcp-connection-demo",
        help="Connect to a remote MCP server and discover tools without calling them.",
    )
    connection.add_argument("--server-url", default=DEFAULT_MCP_SERVER_URL)
    connection.add_argument("--timeout-seconds", type=float, default=DEFAULT_MCP_TIMEOUT_SECONDS)
    connection.add_argument("--output-dir", type=Path, default=Path("../artifacts/snapshot-run"))
    connection.add_argument(
        "--results-file",
        type=Path,
        default=Path("../results/day-16-mcp-connection-snapshot.md"),
    )
    return parser.parse_args(argv)


def scenario_mcp_connection_demo(
    *, server_url: str, timeout_seconds: float, output_dir: Path, results_file: Path
) -> None:
    print("# Day 16 MCP connection demo")
    print(f"Server URL: {server_url}")
    print(f"Transport: {MCP_TRANSPORT}")
    try:
        result = asyncio.run(
            discover_mcp_tools(server_url=server_url, timeout_seconds=timeout_seconds)
        )
    except McpConnectionError as error:
        error_path = write_error_artifact(error, server_url, output_dir)
        print(f"MCP connection failed [{error.kind}]: {error}", file=sys.stderr)
        print(f"Error artifact: {error_path}", file=sys.stderr)
        raise SystemExit(1) from error

    result_path, tools_path, report_path = write_success_outputs(result, output_dir, results_file)
    print("Initialization: successful")
    print(f"Protocol version: {result.protocol_version}")
    print(f"Tool count: {len(result.tools)}")
    print("Tools:")
    for tool in result.tools:
        print(f"- {tool.name}")
    if not result.expected_tools_present:
        print(
            "Warning: missing expected tools: " + ", ".join(result.missing_expected_tools),
            file=sys.stderr,
        )
    if result.extra_tools:
        print("Additional tools: " + ", ".join(result.extra_tools))
    print(f"Connection result: {result_path}")
    print(f"Tools list: {tools_path}")
    print(f"Results: {report_path}")
    print("Tool calls: 0")
    print("LLM API calls: 0")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    scenario_mcp_connection_demo(
        server_url=args.server_url,
        timeout_seconds=args.timeout_seconds,
        output_dir=args.output_dir,
        results_file=args.results_file,
    )


if __name__ == "__main__":
    main()
