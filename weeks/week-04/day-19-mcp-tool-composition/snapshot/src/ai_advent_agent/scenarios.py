"""Minimal Day 19 scenario CLI for the snapshot package."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from ai_advent_agent.config import DEFAULT_API_URL, DEFAULT_MODEL
from ai_advent_agent.mcp_composition_client import (
    COMPOSITION_REPORT_TOOL_NAME,
    COMPOSITION_SAVE_TOOL_NAME,
    COMPOSITION_SEARCH_TOOL_NAME,
    DEFAULT_MCP_COMPOSITION_GOAL,
    DEFAULT_MCP_COMPOSITION_TIMEOUT_SECONDS,
    McpToolCompositionError,
    ScriptedToolPlanner,
    ToolCallingClientError,
    build_llm_planner_from_env,
    run_composition_demo_via_mcp,
    write_composition_demo_outputs,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Day 19 MCP tool composition snapshot.")
    subparsers = parser.add_subparsers(dest="scenario", required=True)
    composition = subparsers.add_parser(
        "mcp-tool-composition-demo",
        help="Run an LLM/scripted planner over composed local MCP tools.",
    )
    composition.add_argument("--planner", choices=["llm", "scripted"], default="scripted")
    composition.add_argument("--goal", default=DEFAULT_MCP_COMPOSITION_GOAL)
    composition.add_argument("--output-dir", type=Path, default=Path("../artifacts"))
    composition.add_argument(
        "--results-file",
        type=Path,
        default=Path("../results/day-19-mcp-tool-composition.md"),
    )
    composition.add_argument(
        "--server-timeout-seconds",
        type=float,
        default=DEFAULT_MCP_COMPOSITION_TIMEOUT_SECONDS,
    )
    composition.add_argument("--max-planner-steps", type=int, default=8)
    composition.add_argument("--model", default=os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL))
    composition.add_argument("--api-url", default=os.getenv("DEEPSEEK_API_URL", DEFAULT_API_URL))
    composition.add_argument("--temperature", type=float, default=0.0)
    composition.add_argument("--max-tokens", type=int, default=1200)
    return parser.parse_args(argv)


def scenario_mcp_tool_composition_demo(
    *,
    planner_mode: str,
    goal: str,
    output_dir: Path,
    results_file: Path,
    server_timeout_seconds: float,
    max_planner_steps: int,
    model: str,
    api_url: str,
    temperature: float,
    max_tokens: int,
) -> None:
    print("# Day 19 MCP tool composition demo")
    print("Transport: stdio")
    print("Server: python -m ai_advent_agent.mcp_composition_server")
    print(
        "Tools: "
        f"{COMPOSITION_SEARCH_TOOL_NAME}, {COMPOSITION_REPORT_TOOL_NAME}, "
        f"{COMPOSITION_SAVE_TOOL_NAME}"
    )
    print(f"Planner: {planner_mode}")
    if planner_mode == "scripted":
        planner = ScriptedToolPlanner()
    elif planner_mode == "llm":
        try:
            planner = build_llm_planner_from_env(
                model=model,
                api_url=api_url,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout_seconds=server_timeout_seconds,
            )
        except (McpToolCompositionError, ValueError) as error:
            print(f"MCP tool composition demo failed: {error}", file=sys.stderr)
            raise SystemExit(1) from error
    else:
        raise SystemExit(f"Unknown planner mode: {planner_mode}")

    try:
        result = asyncio.run(
            run_composition_demo_via_mcp(
                planner=planner,
                goal=goal,
                output_dir=output_dir,
                timeout_seconds=server_timeout_seconds,
                max_planner_steps=max_planner_steps,
            )
        )
    except (McpToolCompositionError, ToolCallingClientError) as error:
        print(f"MCP tool composition demo failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    tools_path, trace_path, pipeline_path, final_answer_path, report_path = (
        write_composition_demo_outputs(result, output_dir, results_file)
    )
    print("Initialization: successful")
    print("Tool sequence: " + " -> ".join(result.pipeline_result["tool_sequence"]))
    print(f"Report path: {result.pipeline_result['report_path']}")
    print(f"Tools list: {tools_path}")
    print(f"Tool-call trace: {trace_path}")
    print(f"Pipeline result: {pipeline_path}")
    print(f"Final answer: {final_answer_path}")
    print(f"Results: {report_path}")
    print(f"Tool calls: {result.pipeline_result['tool_count']}")
    print(f"LLM API calls: {result.usage.get('llm_api_calls', 0)}")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.scenario == "mcp-tool-composition-demo":
        scenario_mcp_tool_composition_demo(
            planner_mode=args.planner,
            goal=args.goal,
            output_dir=args.output_dir,
            results_file=args.results_file,
            server_timeout_seconds=args.server_timeout_seconds,
            max_planner_steps=args.max_planner_steps,
            model=args.model,
            api_url=args.api_url,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
    else:
        raise SystemExit(f"Unknown scenario: {args.scenario}")


if __name__ == "__main__":
    main()
