"""CLI entrypoint for the four isolated Day 20 stdio MCP servers."""

from __future__ import annotations

import argparse
from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from ai_advent_agent.mcp_orchestration_knowledge import build_knowledge_server
from ai_advent_agent.mcp_orchestration_report import build_report_server
from ai_advent_agent.mcp_orchestration_storage import build_storage_server
from ai_advent_agent.mcp_orchestration_tracker import build_tracker_server

SERVER_BUILDERS: dict[str, Callable[[], FastMCP]] = {
    "tracker": build_tracker_server,
    "knowledge": build_knowledge_server,
    "report": build_report_server,
    "storage": build_storage_server,
}


def build_server(server_id: str) -> FastMCP:
    """Return the requested server or fail before opening stdio."""

    try:
        builder = SERVER_BUILDERS[server_id]
    except KeyError as error:
        raise ValueError(f"Unknown orchestration server: {server_id}") from error
    return builder()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run one Day 20 orchestration MCP server.")
    parser.add_argument("server", choices=sorted(SERVER_BUILDERS))
    args = parser.parse_args(argv)
    build_server(args.server).run(transport="stdio")


if __name__ == "__main__":
    main()
