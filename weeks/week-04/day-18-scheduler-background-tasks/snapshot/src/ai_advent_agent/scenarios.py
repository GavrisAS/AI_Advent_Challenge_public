"""Offline Day 18 MCP scheduler scenario for the standalone snapshot."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from ai_advent_agent.mcp_scheduler_client import (
    DEFAULT_MCP_SCHEDULER_TIMEOUT_SECONDS,
    RUN_LOG_TOOL_NAME,
    SCHEDULER_TOOL_NAME,
    SUMMARY_TOOL_NAME,
    McpSchedulerDemoError,
    run_scheduler_demo_via_mcp,
    write_scheduler_demo_outputs,
)
from ai_advent_agent.mcp_tool_client import LOCAL_MCP_TRANSPORT


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Advent Day 18 snapshot scenarios.")
    subparsers = parser.add_subparsers(dest="scenario", required=True)

    mcp_scheduler = subparsers.add_parser(
        "mcp-scheduler-demo",
        help="Day 18: run scheduler-aware MCP tools and aggregate persisted Tracker snapshots.",
    )
    mcp_scheduler.add_argument(
        "--issue-keys",
        nargs="+",
        default=["AI-16", "AI-17", "AI-18"],
        help="Mock Tracker issue keys to collect.",
    )
    mcp_scheduler.add_argument(
        "--interval-seconds",
        type=float,
        default=1.0,
        help="Delay between scheduled collection runs.",
    )
    mcp_scheduler.add_argument(
        "--max-runs",
        type=int,
        default=3,
        help="Bounded number of scheduled collection runs.",
    )
    mcp_scheduler.add_argument(
        "--window-minutes",
        type=int,
        default=60,
        help="Aggregation window for get_tracker_summary.",
    )
    mcp_scheduler.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_MCP_SCHEDULER_TIMEOUT_SECONDS,
        help="Overall local server startup, scheduled collection and summary timeout.",
    )
    mcp_scheduler.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Куда сохранить SQLite/JSON/Markdown artifacts Day 18.",
    )
    mcp_scheduler.add_argument(
        "--results-file",
        type=Path,
        default=None,
        help="Куда сохранить Markdown-отчёт Day 18.",
    )

    return parser.parse_args(argv)


def scenario_mcp_scheduler_demo(
    *,
    issue_keys: list[str],
    interval_seconds: float,
    max_runs: int,
    window_minutes: int,
    timeout_seconds: float,
    output_dir: Path,
    results_file: Path,
) -> None:
    """Run the Day 18 local scheduler-aware MCP tools scenario."""

    storage_path = output_dir / "tracker-summary.sqlite3"
    if storage_path.exists():
        storage_path.unlink()
    print("# Day 18 MCP scheduler demo")
    print(f"Transport: {LOCAL_MCP_TRANSPORT}")
    print("Server: python -m ai_advent_agent.mcp_scheduler_server")
    print(f"Tools: {SCHEDULER_TOOL_NAME}, {RUN_LOG_TOOL_NAME}, {SUMMARY_TOOL_NAME}")
    print(f"Issue keys: {', '.join(issue_keys)}")
    print(f"Interval seconds: {interval_seconds:g}")
    print(f"Max runs: {max_runs}")
    print(f"Storage: {storage_path}")
    try:
        result = asyncio.run(
            run_scheduler_demo_via_mcp(
                issue_keys=issue_keys,
                interval_seconds=interval_seconds,
                max_runs=max_runs,
                storage_path=storage_path,
                window_minutes=window_minutes,
                timeout_seconds=timeout_seconds,
            )
        )
    except McpSchedulerDemoError as error:
        print(f"MCP scheduler demo failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    tools_path, job_path, run_log_path, summary_path, agent_markdown_path, report_path = (
        write_scheduler_demo_outputs(result, output_dir, results_file)
    )
    print("Initialization: successful")
    print(f"Protocol version: {result.protocol_version}")
    print(f"Tool count: {len(result.tools)}")
    print("Tools:")
    for tool in result.tools:
        print(f"- {tool.name}")
    print(f"Job status: {result.job_result['status']}")
    print(f"Runs completed: {result.job_result['runs_completed']}")
    print(f"Run log entries: {result.run_log['runs_total']}")
    print(f"Snapshots total: {result.summary['snapshots_total']}")
    print(f"Tools list: {tools_path}")
    print(f"Scheduler job result: {job_path}")
    print(f"Scheduler run log: {run_log_path}")
    print(f"Aggregated summary: {summary_path}")
    print(f"Agent periodic summary: {agent_markdown_path}")
    print(f"Results: {report_path}")
    print("Tool calls: 3")
    print("LLM API calls: 0")


def default_day18_artifacts_dir() -> Path:
    cwd = Path.cwd()
    if cwd.name == "snapshot":
        return Path("../artifacts")
    return Path("artifacts")


def default_day18_results_file() -> Path:
    cwd = Path.cwd()
    if cwd.name == "snapshot":
        return Path("../results/day-18-scheduler-background-tasks.md")
    return Path("results/day-18-scheduler-background-tasks.md")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.scenario == "mcp-scheduler-demo":
        scenario_mcp_scheduler_demo(
            issue_keys=args.issue_keys,
            interval_seconds=args.interval_seconds,
            max_runs=args.max_runs,
            window_minutes=args.window_minutes,
            timeout_seconds=args.timeout_seconds,
            output_dir=args.output_dir or default_day18_artifacts_dir(),
            results_file=args.results_file or default_day18_results_file(),
        )
    else:
        raise SystemExit(f"Unknown scenario: {args.scenario}")


if __name__ == "__main__":
    main()
