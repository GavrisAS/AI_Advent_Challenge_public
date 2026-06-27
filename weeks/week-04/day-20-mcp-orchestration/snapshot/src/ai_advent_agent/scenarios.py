"""Standalone Day 20 scenario CLI for the snapshot."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from ai_advent_agent.config import DEFAULT_API_URL, DEFAULT_MODEL
from ai_advent_agent.mcp_orchestration_client import (
    DEFAULT_MCP_ORCHESTRATION_GOAL,
    DEFAULT_MCP_ORCHESTRATION_MAX_STEPS,
    DEFAULT_MCP_ORCHESTRATION_TIMEOUT_SECONDS,
    McpOrchestrationError,
    run_orchestration_via_mcp,
    write_orchestration_outputs,
)
from ai_advent_agent.mcp_orchestration_planner import (
    PlannerError,
    ScriptedJsonPlanner,
    build_llm_json_planner_from_env,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Day 20 MCP orchestration snapshot.")
    subparsers = parser.add_subparsers(dest="scenario", required=True)
    demo = subparsers.add_parser("mcp-orchestration-demo")
    demo.add_argument("--planner", choices=["llm-json", "scripted"], default="scripted")
    demo.add_argument("--goal", default=DEFAULT_MCP_ORCHESTRATION_GOAL)
    demo.add_argument("--output-dir", type=Path, default=Path(".tmp/day20/artifacts"))
    demo.add_argument(
        "--results-file", type=Path, default=Path(".tmp/day20/day-20-mcp-orchestration.md")
    )
    demo.add_argument(
        "--server-timeout-seconds",
        type=float,
        default=DEFAULT_MCP_ORCHESTRATION_TIMEOUT_SECONDS,
        help=(
            "Overall timeout for MCP startup, planner loop and tool calls; not only server startup."
        ),
    )
    demo.add_argument("--max-steps", type=int, default=DEFAULT_MCP_ORCHESTRATION_MAX_STEPS)
    demo.add_argument("--model", default=os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL))
    demo.add_argument("--api-url", default=os.getenv("DEEPSEEK_API_URL", DEFAULT_API_URL))
    demo.add_argument("--temperature", type=float, default=0.0)
    demo.add_argument("--max-tokens", type=int, default=2000)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.planner == "scripted":
        planner = ScriptedJsonPlanner()
    else:
        planner = build_llm_json_planner_from_env(
            model=args.model,
            api_url=args.api_url,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout_seconds=args.server_timeout_seconds,
        )
    try:
        result = asyncio.run(
            run_orchestration_via_mcp(
                planner=planner,
                output_dir=args.output_dir,
                goal=args.goal,
                timeout_seconds=args.server_timeout_seconds,
                max_steps=args.max_steps,
            )
        )
    except (McpOrchestrationError, PlannerError) as error:
        print(f"MCP orchestration demo failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    write_orchestration_outputs(result, args.output_dir, args.results_file)
    print(f"Planner: {result.planner}")
    print(f"Tool calls: {len(result.steps)}")
    print(f"Servers used: {', '.join(result.flow_state['servers_used'])}")
    print(f"Completed: {str(result.completed).lower()}")
    if not result.completed:
        raise SystemExit("Flow did not satisfy completion criteria")


if __name__ == "__main__":
    main()
