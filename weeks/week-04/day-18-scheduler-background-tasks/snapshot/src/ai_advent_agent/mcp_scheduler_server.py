"""Local stdio MCP server exposing Day 18 scheduler-aware tools."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ai_advent_agent.mcp_scheduler_service import (
    TrackerScheduleJobResult,
)
from ai_advent_agent.mcp_scheduler_service import (
    get_scheduler_run_log as get_scheduler_run_log_service,
)
from ai_advent_agent.mcp_scheduler_service import (
    get_tracker_summary as get_tracker_summary_service,
)
from ai_advent_agent.mcp_scheduler_service import (
    schedule_tracker_summary as schedule_tracker_summary_service,
)
from ai_advent_agent.mcp_scheduler_store import SchedulerRunLogPayload, TrackerSummaryPayload

mcp = FastMCP("AI Advent Tracker Scheduler")


@mcp.tool(structured_output=True)
async def schedule_tracker_summary(
    issue_keys: Annotated[
        list[str],
        Field(description="Mock Tracker issue keys to collect, for example AI-16 AI-17 AI-18."),
    ],
    storage_path: Annotated[
        str,
        Field(description="SQLite file path used for scheduler persistence."),
    ],
    interval_seconds: Annotated[
        float,
        Field(description="Delay between collection runs in seconds; use 5 for video/demo."),
    ] = 1.0,
    max_runs: Annotated[
        int | None,
        Field(description="Number of bounded runs. Null means run until cancelled."),
    ] = 3,
) -> TrackerScheduleJobResult:
    """Run scheduled mock Tracker collection and persist snapshots in SQLite."""

    return await schedule_tracker_summary_service(
        issue_keys=issue_keys,
        interval_seconds=interval_seconds,
        max_runs=max_runs,
        storage_path=Path(storage_path),
    )


@mcp.tool(structured_output=True)
def get_tracker_summary(
    storage_path: Annotated[
        str,
        Field(description="SQLite file path produced by schedule_tracker_summary."),
    ],
    window_minutes: Annotated[
        int,
        Field(description="Aggregation window in minutes."),
    ] = 60,
) -> TrackerSummaryPayload:
    """Return aggregated summary from persisted Tracker snapshots."""

    return get_tracker_summary_service(
        storage_path=Path(storage_path), window_minutes=window_minutes
    )


@mcp.tool(structured_output=True)
def get_scheduler_run_log(
    storage_path: Annotated[
        str,
        Field(description="SQLite file path produced by schedule_tracker_summary."),
    ],
    job_id: Annotated[
        str | None,
        Field(
            description="Optional scheduler job id. When omitted, the latest stored job is used."
        ),
    ] = None,
) -> SchedulerRunLogPayload:
    """Return ordered scheduled run timeline from SQLite without collecting new snapshots."""

    return get_scheduler_run_log_service(storage_path=Path(storage_path), job_id=job_id)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
