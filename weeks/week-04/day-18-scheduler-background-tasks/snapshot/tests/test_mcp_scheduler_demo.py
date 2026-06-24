from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any, cast

from ai_advent_agent.mcp_scheduler_client import (
    RUN_LOG_TOOL_NAME,
    SCHEDULER_TOOL_NAME,
    SUMMARY_TOOL_NAME,
    build_agent_periodic_summary_markdown,
    run_scheduler_demo_via_mcp,
)
from ai_advent_agent.mcp_scheduler_service import (
    get_scheduler_run_log,
    get_tracker_summary,
    schedule_tracker_summary,
)
from ai_advent_agent.mcp_scheduler_store import initialize_store
from ai_advent_agent.scenarios import parse_args, scenario_mcp_scheduler_demo


def test_scheduler_store_creates_sqlite_schema(tmp_path: Path) -> None:
    storage_path = tmp_path / "tracker-summary.sqlite3"

    initialize_store(storage_path)

    with sqlite3.connect(storage_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert {"jobs", "runs", "issue_snapshots"}.issubset(tables)


def test_single_run_persists_snapshots(tmp_path: Path) -> None:
    storage_path = tmp_path / "tracker-summary.sqlite3"

    result = asyncio.run(
        schedule_tracker_summary(
            issue_keys=["AI-16", "AI-17"],
            interval_seconds=0,
            max_runs=1,
            storage_path=storage_path,
        )
    )

    assert result["status"] == "completed"
    assert result["runs_completed"] == 1
    with sqlite3.connect(storage_path) as connection:
        runs_count = connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        snapshots_count = connection.execute("SELECT COUNT(*) FROM issue_snapshots").fetchone()[0]
    assert runs_count == 1
    assert snapshots_count == 2


def test_aggregated_summary_counts_latest_issues(tmp_path: Path) -> None:
    storage_path = tmp_path / "tracker-summary.sqlite3"

    asyncio.run(
        schedule_tracker_summary(
            issue_keys=["AI-16", "AI-17", "AI-18"],
            interval_seconds=0,
            max_runs=2,
            storage_path=storage_path,
        )
    )
    summary = get_tracker_summary(storage_path=storage_path, window_minutes=60)

    assert summary["runs_total"] == 2
    assert summary["snapshots_total"] == 6
    assert summary["issue_count"] == 3
    assert summary["status_counts"] == {"done": 3}
    assert summary["priority_counts"] == {"high": 1, "medium": 2}
    assert "2 scheduled runs collected 6 issue snapshots" in summary["summary_text"]


def test_scheduler_run_log_returns_ordered_timeline(tmp_path: Path) -> None:
    storage_path = tmp_path / "tracker-summary.sqlite3"

    job = asyncio.run(
        schedule_tracker_summary(
            issue_keys=["AI-16", "AI-17", "AI-18"],
            interval_seconds=0,
            max_runs=3,
            storage_path=storage_path,
        )
    )
    run_log = get_scheduler_run_log(storage_path=storage_path, job_id=job["job_id"])

    assert run_log["job_id"] == job["job_id"]
    assert run_log["interval_seconds"] == 0
    assert run_log["max_runs"] == 3
    assert run_log["runs_total"] == 3
    assert run_log["snapshots_total"] == 9
    assert [run["run_number"] for run in run_log["runs"]] == [1, 2, 3]
    assert {run["status"] for run in run_log["runs"]} == {"completed"}
    assert all(run["issue_count"] == 3 for run in run_log["runs"])
    assert all(run["issue_keys"] == ["AI-16", "AI-17", "AI-18"] for run in run_log["runs"])


def test_empty_summary_is_structured(tmp_path: Path) -> None:
    summary = get_tracker_summary(
        storage_path=tmp_path / "missing.sqlite3",
        window_minutes=60,
    )

    assert summary["empty"] is True
    assert summary["runs_total"] == 0
    assert summary["latest_issues"] == []
    assert summary["reason"] == "storage file does not exist"


def test_cli_mcp_scheduler_defaults_and_overrides(tmp_path: Path) -> None:
    defaults = parse_args(["mcp-scheduler-demo"])
    assert defaults.issue_keys == ["AI-16", "AI-17", "AI-18"]
    assert defaults.interval_seconds == 1.0
    assert defaults.max_runs == 3
    assert defaults.window_minutes == 60
    assert defaults.timeout_seconds == 30.0

    parsed = parse_args(
        [
            "mcp-scheduler-demo",
            "--issue-keys",
            "ai-18",
            "AI-17",
            "--interval-seconds",
            "0",
            "--max-runs",
            "2",
            "--window-minutes",
            "10",
            "--timeout-seconds",
            "8",
            "--output-dir",
            str(tmp_path / "artifacts"),
            "--results-file",
            str(tmp_path / "result.md"),
        ]
    )
    assert parsed.issue_keys == ["ai-18", "AI-17"]
    assert parsed.interval_seconds == 0
    assert parsed.max_runs == 2
    assert parsed.window_minutes == 10
    assert parsed.timeout_seconds == 8
    assert parsed.output_dir == tmp_path / "artifacts"
    assert parsed.results_file == tmp_path / "result.md"


def test_mcp_scheduler_server_exposes_tools_and_schemas(tmp_path: Path) -> None:
    result = asyncio.run(
        run_scheduler_demo_via_mcp(
            issue_keys=["AI-16"],
            interval_seconds=0,
            max_runs=1,
            storage_path=tmp_path / "tracker-summary.sqlite3",
            timeout_seconds=10,
        )
    )

    tools = {tool.name: tool for tool in result.tools}
    assert {SCHEDULER_TOOL_NAME, RUN_LOG_TOOL_NAME, SUMMARY_TOOL_NAME}.issubset(tools)
    scheduler_schema = tools[SCHEDULER_TOOL_NAME].input_schema
    assert scheduler_schema["type"] == "object"
    assert scheduler_schema["required"] == ["issue_keys", "storage_path"]
    scheduler_properties = cast(dict[str, dict[str, Any]], scheduler_schema["properties"])
    assert scheduler_properties["issue_keys"]["type"] == "array"
    assert scheduler_properties["interval_seconds"]["default"] == 1.0
    assert scheduler_properties["max_runs"]["default"] == 3

    summary_schema = tools[SUMMARY_TOOL_NAME].input_schema
    summary_properties = cast(dict[str, dict[str, Any]], summary_schema["properties"])
    assert summary_schema["required"] == ["storage_path"]
    assert summary_properties["window_minutes"]["default"] == 60

    run_log_schema = tools[RUN_LOG_TOOL_NAME].input_schema
    run_log_properties = cast(dict[str, dict[str, Any]], run_log_schema["properties"])
    assert run_log_schema["required"] == ["storage_path"]
    assert run_log_properties["job_id"]["default"] is None


def test_mcp_client_calls_scheduler_tools_through_stdio(tmp_path: Path) -> None:
    result = asyncio.run(
        run_scheduler_demo_via_mcp(
            issue_keys=["ai-16", "AI-17", "AI-18"],
            interval_seconds=0,
            max_runs=2,
            storage_path=tmp_path / "tracker-summary.sqlite3",
            timeout_seconds=10,
        )
    )

    assert result.job_result["status"] == "completed"
    assert result.job_result["runs_completed"] == 2
    assert result.run_log["runs_total"] == 2
    assert result.run_log["snapshots_total"] == 6
    assert result.summary["runs_total"] == 2
    assert result.summary["snapshots_total"] == 6
    assert result.raw_job_result["isError"] is False
    assert result.raw_run_log_result["isError"] is False
    assert result.raw_summary_result["isError"] is False


def test_agent_markdown_uses_aggregated_summary(tmp_path: Path) -> None:
    result = asyncio.run(
        run_scheduler_demo_via_mcp(
            issue_keys=["AI-16", "AI-17"],
            interval_seconds=0,
            max_runs=1,
            storage_path=tmp_path / "tracker-summary.sqlite3",
            timeout_seconds=10,
        )
    )

    markdown = build_agent_periodic_summary_markdown(result)

    assert "Agent Periodic Tracker Summary" in markdown
    assert "Runs completed: `1`" in markdown
    assert "## Scheduled runs" in markdown
    assert "Status counts:" in markdown


def test_mcp_scheduler_demo_scenario_creates_artifacts_and_results(tmp_path: Path) -> None:
    output_dir = tmp_path / "artifacts"
    results_file = tmp_path / "results" / "day-18-scheduler-background-tasks.md"

    scenario_mcp_scheduler_demo(
        issue_keys=["AI-16", "AI-17", "AI-18"],
        interval_seconds=0,
        max_runs=2,
        window_minutes=60,
        timeout_seconds=10,
        output_dir=output_dir,
        results_file=results_file,
    )

    assert (output_dir / "tracker-summary.sqlite3").exists()
    tools_payload = json.loads((output_dir / "tools-list.json").read_text(encoding="utf-8"))
    job_payload = json.loads((output_dir / "scheduler-job-result.json").read_text(encoding="utf-8"))
    run_log_payload = json.loads(
        (output_dir / "scheduler-run-log.json").read_text(encoding="utf-8")
    )
    summary_payload = json.loads(
        (output_dir / "aggregated-summary.json").read_text(encoding="utf-8")
    )
    agent_markdown = (output_dir / "agent-periodic-summary.md").read_text(encoding="utf-8")
    results_markdown = results_file.read_text(encoding="utf-8")

    assert [tool["name"] for tool in tools_payload["tools"]] == [
        RUN_LOG_TOOL_NAME,
        SUMMARY_TOOL_NAME,
        SCHEDULER_TOOL_NAME,
    ]
    assert job_payload["normalized_result"]["runs_completed"] == 2
    assert run_log_payload["runs_total"] == 2
    assert run_log_payload["snapshots_total"] == 6
    assert [run["status"] for run in run_log_payload["runs"]] == ["completed", "completed"]
    assert summary_payload["normalized_result"]["snapshots_total"] == 6
    assert "Agent Periodic Tracker Summary" in agent_markdown
    assert "Scheduler run timeline" in results_markdown
    assert "Day 18 — Планировщик" in results_markdown
