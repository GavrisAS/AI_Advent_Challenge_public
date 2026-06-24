"""Stdio MCP client helpers for the Day 18 scheduler demo."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import timedelta
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any, cast

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult, TextContent, Tool

from ai_advent_agent.mcp_scheduler_service import TrackerScheduleJobResult
from ai_advent_agent.mcp_scheduler_store import (
    SchedulerRunLogPayload,
    TrackerSummaryPayload,
    utc_timestamp,
)
from ai_advent_agent.mcp_tool_client import NormalizedMcpTool, json_compatible, markdown_cell

SCHEDULER_TOOL_NAME = "schedule_tracker_summary"
RUN_LOG_TOOL_NAME = "get_scheduler_run_log"
SUMMARY_TOOL_NAME = "get_tracker_summary"
LOCAL_MCP_TRANSPORT = "stdio"
DEFAULT_MCP_SCHEDULER_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class McpSchedulerDemoResult:
    timestamp_utc: str
    sdk_version: str
    protocol_version: str
    server_name: str
    server_version: str
    issue_keys: tuple[str, ...]
    interval_seconds: float
    max_runs: int | None
    storage_path: Path
    tools: tuple[NormalizedMcpTool, ...]
    job_result: TrackerScheduleJobResult
    run_log: SchedulerRunLogPayload
    summary: TrackerSummaryPayload
    raw_job_result: dict[str, object]
    raw_run_log_result: dict[str, object]
    raw_summary_result: dict[str, object]

    def tools_list_dict(self) -> dict[str, object]:
        return {
            "transport": LOCAL_MCP_TRANSPORT,
            "server_command": ["python", "-m", "ai_advent_agent.mcp_scheduler_server"],
            "tool_count": len(self.tools),
            "tools": [tool.to_dict() for tool in self.tools],
        }


class McpSchedulerDemoError(RuntimeError):
    """Raised when local scheduler MCP workflow cannot be completed."""


async def run_scheduler_demo_via_mcp(
    *,
    issue_keys: list[str],
    interval_seconds: float,
    max_runs: int | None,
    storage_path: Path,
    window_minutes: int = 60,
    timeout_seconds: float = DEFAULT_MCP_SCHEDULER_TIMEOUT_SECONDS,
) -> McpSchedulerDemoResult:
    """Start the scheduler MCP server and call both Day 18 tools over stdio."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")

    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "ai_advent_agent.mcp_scheduler_server"],
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
                            key=lambda item: item.name,
                        )
                    )
                    tool_names = {tool.name for tool in tools}
                    missing = sorted(
                        {SCHEDULER_TOOL_NAME, RUN_LOG_TOOL_NAME, SUMMARY_TOOL_NAME} - tool_names
                    )
                    if missing:
                        raise McpSchedulerDemoError(
                            "Local scheduler MCP server did not expose tools: " + ", ".join(missing)
                        )
                    job_call_result = await session.call_tool(
                        SCHEDULER_TOOL_NAME,
                        arguments={
                            "issue_keys": issue_keys,
                            "interval_seconds": interval_seconds,
                            "max_runs": max_runs,
                            "storage_path": str(storage_path),
                        },
                    )
                    if job_call_result.isError:
                        raise McpSchedulerDemoError(
                            f"Scheduler tool returned an error: {job_call_result!r}"
                        )
                    job_result = extract_payload(job_call_result, "scheduler job result")
                    run_log_call_result = await session.call_tool(
                        RUN_LOG_TOOL_NAME,
                        arguments={
                            "storage_path": str(storage_path),
                            "job_id": job_result["job_id"],
                        },
                    )
                    summary_call_result = await session.call_tool(
                        SUMMARY_TOOL_NAME,
                        arguments={
                            "storage_path": str(storage_path),
                            "window_minutes": window_minutes,
                        },
                    )
    except TimeoutError as error:
        raise McpSchedulerDemoError(
            f"Local MCP scheduler workflow timed out after {timeout_seconds:g} seconds"
        ) from error

    if run_log_call_result.isError:
        raise McpSchedulerDemoError(f"Run log tool returned an error: {run_log_call_result!r}")
    if summary_call_result.isError:
        raise McpSchedulerDemoError(f"Summary tool returned an error: {summary_call_result!r}")

    run_log = extract_payload(run_log_call_result, "scheduler run log")
    summary = extract_payload(summary_call_result, "aggregated summary")
    return McpSchedulerDemoResult(
        timestamp_utc=utc_timestamp(),
        sdk_version=package_version("mcp"),
        protocol_version=str(initialization.protocolVersion),
        server_name=initialization.serverInfo.name,
        server_version=initialization.serverInfo.version,
        issue_keys=tuple(cast(list[str], job_result["issue_keys"])),
        interval_seconds=interval_seconds,
        max_runs=max_runs,
        storage_path=storage_path,
        tools=tools,
        job_result=cast(TrackerScheduleJobResult, job_result),
        run_log=cast(SchedulerRunLogPayload, run_log),
        summary=cast(TrackerSummaryPayload, summary),
        raw_job_result=json_compatible(job_call_result.model_dump(by_alias=True)),
        raw_run_log_result=json_compatible(run_log_call_result.model_dump(by_alias=True)),
        raw_summary_result=json_compatible(summary_call_result.model_dump(by_alias=True)),
    )


def normalize_tool(tool: Tool) -> NormalizedMcpTool:
    schema = cast(dict[str, object], json.loads(json.dumps(tool.inputSchema)))
    return NormalizedMcpTool(
        name=tool.name,
        description=tool.description,
        input_schema=schema,
    )


def extract_payload(call_result: CallToolResult, label: str) -> dict[str, Any]:
    if call_result.structuredContent is not None:
        return cast(dict[str, Any], json_compatible(call_result.structuredContent))
    for block in call_result.content:
        if isinstance(block, TextContent):
            try:
                payload = json.loads(block.text)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return cast(dict[str, Any], json_compatible(payload))
    raise McpSchedulerDemoError(f"MCP call result did not contain {label}")


def server_environment() -> dict[str, str]:
    env = dict(os.environ)
    src_dir = str(Path(__file__).resolve().parents[1])
    current_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        src_dir if not current_pythonpath else os.pathsep.join([src_dir, current_pythonpath])
    )
    return env


def write_scheduler_demo_outputs(
    result: McpSchedulerDemoResult, output_dir: Path, results_file: Path
) -> tuple[Path, Path, Path, Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results_file.parent.mkdir(parents=True, exist_ok=True)

    tools_path = output_dir / "tools-list.json"
    job_path = output_dir / "scheduler-job-result.json"
    run_log_path = output_dir / "scheduler-run-log.json"
    summary_path = output_dir / "aggregated-summary.json"
    agent_markdown_path = output_dir / "agent-periodic-summary.md"

    write_json(tools_path, result.tools_list_dict())
    write_json(job_path, build_job_artifact(result))
    write_json(run_log_path, build_run_log_artifact(result))
    write_json(summary_path, build_summary_artifact(result))
    agent_markdown_path.write_text(build_agent_periodic_summary_markdown(result), encoding="utf-8")
    results_file.write_text(build_results_markdown(result, output_dir), encoding="utf-8")
    return tools_path, job_path, run_log_path, summary_path, agent_markdown_path, results_file


def build_job_artifact(result: McpSchedulerDemoResult) -> dict[str, object]:
    return {
        "transport": LOCAL_MCP_TRANSPORT,
        "tool_name": SCHEDULER_TOOL_NAME,
        "arguments": {
            "issue_keys": list(result.issue_keys),
            "interval_seconds": result.interval_seconds,
            "max_runs": result.max_runs,
            "storage_path": str(result.storage_path),
        },
        "is_error": False,
        "normalized_result": result.job_result,
        "raw_call_result": result.raw_job_result,
    }


def build_summary_artifact(result: McpSchedulerDemoResult) -> dict[str, object]:
    return {
        "transport": LOCAL_MCP_TRANSPORT,
        "tool_name": SUMMARY_TOOL_NAME,
        "arguments": {
            "storage_path": str(result.storage_path),
            "window_minutes": result.summary["window_minutes"],
        },
        "is_error": False,
        "normalized_result": result.summary,
        "raw_call_result": result.raw_summary_result,
    }


def build_run_log_artifact(result: McpSchedulerDemoResult) -> dict[str, object]:
    return {
        **result.run_log,
        "transport": LOCAL_MCP_TRANSPORT,
        "tool_name": RUN_LOG_TOOL_NAME,
        "arguments": {
            "storage_path": str(result.storage_path),
            "job_id": result.job_result["job_id"],
        },
        "is_error": False,
        "raw_call_result": result.raw_run_log_result,
    }


def build_agent_periodic_summary_markdown(result: McpSchedulerDemoResult) -> str:
    latest_rows = "\n".join(
        (
            "- `{issue_key}` — {title}; status `{status}`, "
            "priority `{priority}`, assignee `{assignee}`"
        ).format(**issue)
        for issue in result.summary["latest_issues"]
    )
    latest_block = latest_rows or "- Нет snapshot-ов в выбранном окне."
    run_rows = "\n".join(
        (
            "- Run {run_number} completed at `{completed_at}` and collected "
            "{issue_count} issue snapshots for {issues}."
        ).format(
            run_number=run["run_number"],
            completed_at=run["completed_at"],
            issue_count=run["issue_count"],
            issues=", ".join(f"`{issue_key}`" for issue_key in run["issue_keys"]),
        )
        for run in result.run_log["runs"]
    )
    run_block = run_rows or "- Scheduler run log is empty."
    tools_line = (
        f"Agent used MCP tools `{SCHEDULER_TOOL_NAME}`, `{RUN_LOG_TOOL_NAME}` "
        f"and `{SUMMARY_TOOL_NAME}` through stdio."
    )
    return f"""# Agent Periodic Tracker Summary

{tools_line}

## Collection

- Job: `{result.job_result["job_id"]}`
- Status: `{result.job_result["status"]}`
- Runs completed: `{result.job_result["runs_completed"]}`
- Interval seconds: `{result.interval_seconds}`
- Storage: `{result.storage_path}`

## Scheduled runs

{run_block}

The agent received the run log and aggregated summary through MCP tools, then used the persisted
SQLite data to produce this report.

## Aggregated summary

{result.summary["summary_text"]}

- Status counts: `{result.summary["status_counts"]}`
- Priority counts: `{result.summary["priority_counts"]}`
- Assignee counts: `{result.summary["assignee_counts"]}`

## Latest issues

{latest_block}
"""


def build_results_markdown(result: McpSchedulerDemoResult, output_dir: Path) -> str:
    tool_rows = "\n".join(
        f"| `{tool.name}` | {markdown_cell(tool.description or '—')} |" for tool in result.tools
    )
    issue_rows = "\n".join(
        "| `{issue_key}` | {title} | `{status}` | `{priority}` | `{assignee}` |".format(**issue)
        for issue in result.summary["latest_issues"]
    )
    timeline_rows = "\n".join(
        (
            "| {run_number} | `{started_at}` | `{completed_at}` | {issue_count} | "
            "{issues} | {status} |"
        ).format(
            run_number=run["run_number"],
            started_at=run["started_at"],
            completed_at=run["completed_at"],
            issue_count=run["issue_count"],
            issues=", ".join(f"`{issue_key}`" for issue_key in run["issue_keys"]),
            status=run["status"],
        )
        for run in result.run_log["runs"]
    )
    return f"""# Day 18 — Планировщик и фоновые MCP tools

Сценарий выполнен локально через stdio MCP server, без внешней сети, API key, LLM API,
cron/systemd/Celery/APScheduler и реального Tracker API.

## MCP workflow

- Server: `{result.server_name} {result.server_version}`
- Transport: `{LOCAL_MCP_TRANSPORT}`
- Protocol version: `{result.protocol_version}`
- MCP Python SDK: `{result.sdk_version}`
- Tools: `{SCHEDULER_TOOL_NAME}`, `{RUN_LOG_TOOL_NAME}`, `{SUMMARY_TOOL_NAME}`
- Demo schedule: `interval_seconds={result.interval_seconds}`, `max_runs={result.max_runs}`
- Storage: `{result.storage_path}`
- Timestamp UTC: `{result.timestamp_utc}`
- Mode: bounded demo mode, without VPS or external services

| Tool | Description |
|---|---|
{tool_rows}

## Job result

- Job id: `{result.job_result["job_id"]}`
- Status: `{result.job_result["status"]}`
- Runs completed: `{result.job_result["runs_completed"]}`
- Issue keys: `{", ".join(result.issue_keys)}`
- Started at: `{result.job_result["started_at"]}`
- Completed at: `{result.job_result["completed_at"]}`

## Scheduler run timeline

Scheduler was run in bounded demo mode with `interval_seconds={result.interval_seconds}` and
`max_runs={result.max_runs}`. The workflow produced `{result.run_log["runs_total"]}` scheduled
executions and persisted `{result.run_log["snapshots_total"]}` issue snapshots in SQLite. The
agent received this timeline through `{RUN_LOG_TOOL_NAME}` before requesting the aggregated summary.

| Run | Started at | Completed at | Issue count | Issues | Status |
|---:|---|---|---:|---|---|
{timeline_rows}

## Aggregated result

{result.summary["summary_text"]}

- Runs total: `{result.summary["runs_total"]}`
- Snapshots total: `{result.summary["snapshots_total"]}`
- Issue count: `{result.summary["issue_count"]}`
- Status counts: `{result.summary["status_counts"]}`
- Priority counts: `{result.summary["priority_counts"]}`
- Assignee counts: `{result.summary["assignee_counts"]}`

| Issue | Title | Status | Priority | Assignee |
|---|---|---|---|---|
{issue_rows}

## Артефакты

JSON, SQLite и Markdown outputs сформированы в `{output_dir}`:

- `tracker-summary.sqlite3`
- `tools-list.json`
- `scheduler-job-result.json`
- `scheduler-run-log.json`
- `aggregated-summary.json`
- `agent-periodic-summary.md`
"""


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
