"""Scheduler orchestration for Day 18 MCP background task tools."""

from __future__ import annotations

import asyncio
import math
import uuid
from pathlib import Path
from typing import TypedDict

from ai_advent_agent.mcp_mock_api import get_issue, normalize_issue_key
from ai_advent_agent.mcp_scheduler_store import (
    SchedulerRunLogPayload,
    TrackerSummaryPayload,
    aggregate_tracker_summary,
    complete_job,
    create_job,
    read_scheduler_run_log,
    record_run,
    utc_timestamp,
)


class TrackerScheduleJobResult(TypedDict):
    job_id: str
    status: str
    interval_seconds: float
    max_runs: int | None
    runs_completed: int
    issue_keys: list[str]
    storage_path: str
    started_at: str
    completed_at: str | None


def normalize_issue_keys(issue_keys: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for issue_key in issue_keys:
        normalized_key = normalize_issue_key(issue_key)
        if normalized_key not in seen:
            normalized.append(normalized_key)
            seen.add(normalized_key)
    if not normalized:
        raise ValueError("issue_keys must contain at least one issue key")
    return normalized


def validate_schedule_inputs(*, interval_seconds: float, max_runs: int | None) -> None:
    if not math.isfinite(interval_seconds) or interval_seconds < 0:
        raise ValueError("interval_seconds must be a finite number greater than or equal to zero")
    if max_runs is not None and max_runs <= 0:
        raise ValueError("max_runs must be a positive integer or null")


async def schedule_tracker_summary(
    *,
    issue_keys: list[str],
    storage_path: Path,
    interval_seconds: float = 1.0,
    max_runs: int | None = 3,
) -> TrackerScheduleJobResult:
    """Run periodic mock Tracker collection and persist every snapshot."""

    normalized_keys = normalize_issue_keys(issue_keys)
    validate_schedule_inputs(interval_seconds=interval_seconds, max_runs=max_runs)
    job_id = f"tracker-summary-{uuid.uuid4().hex[:12]}"
    started_at = utc_timestamp()
    create_job(
        storage_path=storage_path,
        job_id=job_id,
        issue_keys=normalized_keys,
        interval_seconds=interval_seconds,
        max_runs=max_runs,
        started_at=started_at,
    )

    runs_completed = 0
    status = "running"
    completed_at: str | None = None
    try:
        run_number = 1
        while max_runs is None or run_number <= max_runs:
            run_started_at = utc_timestamp()
            issues = [get_issue(issue_key, include_comments=False) for issue_key in normalized_keys]
            run_completed_at = utc_timestamp()
            record_run(
                storage_path=storage_path,
                job_id=job_id,
                run_number=run_number,
                issues=issues,
                started_at=run_started_at,
                completed_at=run_completed_at,
            )
            runs_completed = run_number
            if max_runs is not None and run_number >= max_runs:
                status = "completed"
                completed_at = utc_timestamp()
                break
            run_number += 1
            if interval_seconds:
                await asyncio.sleep(interval_seconds)
            else:
                await asyncio.sleep(0)
    except asyncio.CancelledError:
        status = "cancelled"
        completed_at = utc_timestamp()
        complete_job(
            storage_path=storage_path, job_id=job_id, status=status, completed_at=completed_at
        )
        raise
    except Exception:
        status = "failed"
        completed_at = utc_timestamp()
        complete_job(
            storage_path=storage_path, job_id=job_id, status=status, completed_at=completed_at
        )
        raise

    final_completed_at = completed_at or utc_timestamp()
    complete_job(
        storage_path=storage_path,
        job_id=job_id,
        status=status,
        completed_at=final_completed_at,
    )
    return {
        "job_id": job_id,
        "status": status,
        "interval_seconds": interval_seconds,
        "max_runs": max_runs,
        "runs_completed": runs_completed,
        "issue_keys": normalized_keys,
        "storage_path": str(storage_path),
        "started_at": started_at,
        "completed_at": final_completed_at,
    }


def get_tracker_summary(*, storage_path: Path, window_minutes: int = 60) -> TrackerSummaryPayload:
    return aggregate_tracker_summary(storage_path=storage_path, window_minutes=window_minutes)


def get_scheduler_run_log(
    *, storage_path: Path, job_id: str | None = None
) -> SchedulerRunLogPayload:
    return read_scheduler_run_log(storage_path=storage_path, job_id=job_id)
