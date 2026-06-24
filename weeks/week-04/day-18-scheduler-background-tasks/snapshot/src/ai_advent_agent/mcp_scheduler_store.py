"""SQLite persistence and aggregation for Day 18 scheduled MCP summaries."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TypedDict

from ai_advent_agent.mcp_mock_api import TrackerIssuePayload


class SchedulerJobRecord(TypedDict):
    job_id: str
    issue_keys: list[str]
    interval_seconds: float
    max_runs: int | None
    status: str
    storage_path: str
    started_at: str
    completed_at: str | None


class SchedulerRunRecord(TypedDict):
    job_id: str
    run_number: int
    started_at: str
    completed_at: str
    issue_count: int
    status: str


class SchedulerRunLogEntry(TypedDict):
    run_number: int
    started_at: str
    completed_at: str
    issue_count: int
    issue_keys: list[str]
    status: str


class SchedulerRunLogPayload(TypedDict):
    job_id: str | None
    storage_path: str
    interval_seconds: float | None
    max_runs: int | None
    status: str | None
    started_at: str | None
    completed_at: str | None
    issue_keys: list[str]
    runs_total: int
    snapshots_total: int
    runs: list[SchedulerRunLogEntry]
    generated_at: str
    empty: bool
    reason: str | None


class LatestIssueSummary(TypedDict):
    issue_key: str
    title: str
    status: str
    priority: str
    assignee: str
    collected_at: str


class TrackerSummaryPayload(TypedDict):
    storage_path: str
    window_minutes: int
    runs_total: int
    snapshots_total: int
    issue_count: int
    status_counts: dict[str, int]
    priority_counts: dict[str, int]
    assignee_counts: dict[str, int]
    latest_issues: list[LatestIssueSummary]
    summary_text: str
    window_started_at: str
    generated_at: str
    empty: bool
    reason: str | None


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    issue_keys_json TEXT NOT NULL,
    interval_seconds REAL NOT NULL,
    max_runs INTEGER,
    status TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    run_number INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    issue_count INTEGER NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

CREATE TABLE IF NOT EXISTS issue_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    run_number INTEGER NOT NULL,
    issue_key TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    assignee TEXT NOT NULL,
    priority TEXT NOT NULL,
    summary TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

CREATE INDEX IF NOT EXISTS idx_issue_snapshots_collected_at
    ON issue_snapshots(collected_at);
CREATE INDEX IF NOT EXISTS idx_issue_snapshots_issue_key
    ON issue_snapshots(issue_key, collected_at);
CREATE INDEX IF NOT EXISTS idx_runs_job_id
    ON runs(job_id);
"""


def initialize_store(storage_path: Path) -> None:
    """Create parent directory and SQLite schema if needed."""

    storage_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(storage_path) as connection:
        connection.executescript(SCHEMA_SQL)


def create_job(
    *,
    storage_path: Path,
    job_id: str,
    issue_keys: list[str],
    interval_seconds: float,
    max_runs: int | None,
    started_at: str,
) -> SchedulerJobRecord:
    initialize_store(storage_path)
    record: SchedulerJobRecord = {
        "job_id": job_id,
        "issue_keys": issue_keys,
        "interval_seconds": interval_seconds,
        "max_runs": max_runs,
        "status": "running",
        "storage_path": str(storage_path),
        "started_at": started_at,
        "completed_at": None,
    }
    with sqlite3.connect(storage_path) as connection:
        connection.execute(
            """
            INSERT INTO jobs (
                job_id, issue_keys_json, interval_seconds, max_runs, status,
                storage_path, started_at, completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                json.dumps(issue_keys, ensure_ascii=False),
                interval_seconds,
                max_runs,
                record["status"],
                str(storage_path),
                started_at,
                None,
            ),
        )
    return record


def record_run(
    *,
    storage_path: Path,
    job_id: str,
    run_number: int,
    issues: list[TrackerIssuePayload],
    started_at: str,
    completed_at: str,
) -> SchedulerRunRecord:
    initialize_store(storage_path)
    record: SchedulerRunRecord = {
        "job_id": job_id,
        "run_number": run_number,
        "started_at": started_at,
        "completed_at": completed_at,
        "issue_count": len(issues),
        "status": "completed",
    }
    with sqlite3.connect(storage_path) as connection:
        connection.execute(
            """
            INSERT INTO runs (
                job_id, run_number, started_at, completed_at, issue_count, status
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                run_number,
                started_at,
                completed_at,
                len(issues),
                record["status"],
            ),
        )
        connection.executemany(
            """
            INSERT INTO issue_snapshots (
                job_id, run_number, issue_key, title, status, assignee,
                priority, summary, collected_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    job_id,
                    run_number,
                    issue["issue_key"],
                    issue["title"],
                    issue["status"],
                    issue["assignee"],
                    issue["priority"],
                    issue["summary"],
                    completed_at,
                )
                for issue in issues
            ],
        )
    return record


def complete_job(*, storage_path: Path, job_id: str, status: str, completed_at: str) -> None:
    initialize_store(storage_path)
    with sqlite3.connect(storage_path) as connection:
        connection.execute(
            "UPDATE jobs SET status = ?, completed_at = ? WHERE job_id = ?",
            (status, completed_at, job_id),
        )


def read_scheduler_run_log(
    *, storage_path: Path, job_id: str | None = None
) -> SchedulerRunLogPayload:
    """Return ordered run timeline for a stored scheduler job without mutating state."""

    generated_at = utc_timestamp()
    if not storage_path.exists():
        return empty_run_log(
            storage_path=storage_path,
            generated_at=generated_at,
            reason="storage file does not exist",
        )

    initialize_store(storage_path)
    with sqlite3.connect(storage_path) as connection:
        connection.row_factory = sqlite3.Row
        if job_id is None:
            job_row = connection.execute(
                """
                SELECT job_id, issue_keys_json, interval_seconds, max_runs, status,
                       started_at, completed_at
                FROM jobs
                ORDER BY started_at DESC, rowid DESC
                LIMIT 1
                """
            ).fetchone()
        else:
            job_row = connection.execute(
                """
                SELECT job_id, issue_keys_json, interval_seconds, max_runs, status,
                       started_at, completed_at
                FROM jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()

        if job_row is None:
            return empty_run_log(
                storage_path=storage_path,
                generated_at=generated_at,
                reason="job not found" if job_id else "storage has no scheduler jobs",
            )

        stored_job_id = str(job_row["job_id"])
        run_rows = connection.execute(
            """
            SELECT run_number, started_at, completed_at, issue_count, status
            FROM runs
            WHERE job_id = ?
            ORDER BY run_number ASC, started_at ASC
            """,
            (stored_job_id,),
        ).fetchall()
        snapshot_rows = connection.execute(
            """
            SELECT run_number, issue_key
            FROM issue_snapshots
            WHERE job_id = ?
            ORDER BY run_number ASC, snapshot_id ASC
            """,
            (stored_job_id,),
        ).fetchall()

    issue_keys_by_run: dict[int, list[str]] = {}
    snapshots_total = 0
    for row in snapshot_rows:
        snapshots_total += 1
        run_number = int(row["run_number"])
        issue_key = str(row["issue_key"])
        issue_keys = issue_keys_by_run.setdefault(run_number, [])
        if issue_key not in issue_keys:
            issue_keys.append(issue_key)

    runs: list[SchedulerRunLogEntry] = [
        {
            "run_number": int(row["run_number"]),
            "started_at": str(row["started_at"]),
            "completed_at": str(row["completed_at"]),
            "issue_count": int(row["issue_count"]),
            "issue_keys": issue_keys_by_run.get(int(row["run_number"]), []),
            "status": str(row["status"]),
        }
        for row in run_rows
    ]
    issue_keys_json = str(job_row["issue_keys_json"])
    issue_keys_payload = json.loads(issue_keys_json)
    issue_keys = [str(issue_key) for issue_key in issue_keys_payload]
    return {
        "job_id": stored_job_id,
        "storage_path": str(storage_path),
        "interval_seconds": float(job_row["interval_seconds"]),
        "max_runs": None if job_row["max_runs"] is None else int(job_row["max_runs"]),
        "status": str(job_row["status"]),
        "started_at": str(job_row["started_at"]),
        "completed_at": None if job_row["completed_at"] is None else str(job_row["completed_at"]),
        "issue_keys": issue_keys,
        "runs_total": len(runs),
        "snapshots_total": snapshots_total,
        "runs": runs,
        "generated_at": generated_at,
        "empty": False,
        "reason": None,
    }


def empty_run_log(*, storage_path: Path, generated_at: str, reason: str) -> SchedulerRunLogPayload:
    return {
        "job_id": None,
        "storage_path": str(storage_path),
        "interval_seconds": None,
        "max_runs": None,
        "status": None,
        "started_at": None,
        "completed_at": None,
        "issue_keys": [],
        "runs_total": 0,
        "snapshots_total": 0,
        "runs": [],
        "generated_at": generated_at,
        "empty": True,
        "reason": reason,
    }


def aggregate_tracker_summary(
    *, storage_path: Path, window_minutes: int = 60
) -> TrackerSummaryPayload:
    """Aggregate collected issue snapshots for the requested window."""

    if window_minutes <= 0:
        raise ValueError("window_minutes must be greater than zero")

    generated_at = utc_timestamp()
    window_started_at = (
        (datetime.now(UTC) - timedelta(minutes=window_minutes))
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )

    if not storage_path.exists():
        return empty_summary(
            storage_path=storage_path,
            window_minutes=window_minutes,
            window_started_at=window_started_at,
            generated_at=generated_at,
            reason="storage file does not exist",
        )

    initialize_store(storage_path)
    with sqlite3.connect(storage_path) as connection:
        connection.row_factory = sqlite3.Row
        runs_total = int(
            connection.execute(
                "SELECT COUNT(*) FROM runs WHERE completed_at >= ?",
                (window_started_at,),
            ).fetchone()[0]
        )
        snapshot_rows = connection.execute(
            """
            SELECT issue_key, title, status, assignee, priority, collected_at
            FROM issue_snapshots
            WHERE collected_at >= ?
            ORDER BY collected_at ASC, snapshot_id ASC
            """,
            (window_started_at,),
        ).fetchall()

    if not snapshot_rows:
        return empty_summary(
            storage_path=storage_path,
            window_minutes=window_minutes,
            window_started_at=window_started_at,
            generated_at=generated_at,
            reason="no snapshots in requested window",
        )

    latest_by_issue: dict[str, LatestIssueSummary] = {}
    for row in snapshot_rows:
        latest_by_issue[row["issue_key"]] = {
            "issue_key": row["issue_key"],
            "title": row["title"],
            "status": row["status"],
            "priority": row["priority"],
            "assignee": row["assignee"],
            "collected_at": row["collected_at"],
        }

    latest_issues = sorted(latest_by_issue.values(), key=lambda item: item["issue_key"])
    status_counts = Counter(issue["status"] for issue in latest_issues)
    priority_counts = Counter(issue["priority"] for issue in latest_issues)
    assignee_counts = Counter(issue["assignee"] for issue in latest_issues)
    snapshots_total = len(snapshot_rows)
    issue_count = len(latest_issues)
    summary_text = (
        f"{runs_total} scheduled runs collected {snapshots_total} issue snapshots for "
        f"{issue_count} unique issues in the last {window_minutes} minutes."
    )
    return {
        "storage_path": str(storage_path),
        "window_minutes": window_minutes,
        "runs_total": runs_total,
        "snapshots_total": snapshots_total,
        "issue_count": issue_count,
        "status_counts": dict(sorted(status_counts.items())),
        "priority_counts": dict(sorted(priority_counts.items())),
        "assignee_counts": dict(sorted(assignee_counts.items())),
        "latest_issues": latest_issues,
        "summary_text": summary_text,
        "window_started_at": window_started_at,
        "generated_at": generated_at,
        "empty": False,
        "reason": None,
    }


def empty_summary(
    *,
    storage_path: Path,
    window_minutes: int,
    window_started_at: str,
    generated_at: str,
    reason: str,
) -> TrackerSummaryPayload:
    return {
        "storage_path": str(storage_path),
        "window_minutes": window_minutes,
        "runs_total": 0,
        "snapshots_total": 0,
        "issue_count": 0,
        "status_counts": {},
        "priority_counts": {},
        "assignee_counts": {},
        "latest_issues": [],
        "summary_text": f"No tracker snapshots found: {reason}.",
        "window_started_at": window_started_at,
        "generated_at": generated_at,
        "empty": True,
        "reason": reason,
    }


def utc_timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
