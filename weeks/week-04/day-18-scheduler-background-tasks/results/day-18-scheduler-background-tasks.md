# Day 18 — Планировщик и фоновые MCP tools

Сценарий выполнен локально через stdio MCP server, без внешней сети, API key, LLM API,
cron/systemd/Celery/APScheduler и реального Tracker API.

## MCP workflow

- Server: `AI Advent Tracker Scheduler 1.28.0`
- Transport: `stdio`
- Protocol version: `2025-11-25`
- MCP Python SDK: `1.28.0`
- Tools: `schedule_tracker_summary`, `get_scheduler_run_log`, `get_tracker_summary`
- Demo schedule: `interval_seconds=5.0`, `max_runs=3`
- Storage: `../artifacts/tracker-summary.sqlite3`
- Timestamp UTC: `2026-06-24T18:12:01Z`
- Mode: bounded demo mode, without VPS or external services

| Tool | Description |
|---|---|
| `get_scheduler_run_log` | Return ordered scheduled run timeline from SQLite without collecting new snapshots. |
| `get_tracker_summary` | Return aggregated summary from persisted Tracker snapshots. |
| `schedule_tracker_summary` | Run scheduled mock Tracker collection and persist snapshots in SQLite. |

## Job result

- Job id: `tracker-summary-1888def442ce`
- Status: `completed`
- Runs completed: `3`
- Issue keys: `AI-16, AI-17, AI-18`
- Started at: `2026-06-24T18:11:51Z`
- Completed at: `2026-06-24T18:12:01Z`

## Scheduler run timeline

Scheduler was run in bounded demo mode with `interval_seconds=5.0` and
`max_runs=3`. The workflow produced `3` scheduled
executions and persisted `9` issue snapshots in SQLite. The
agent received this timeline through `get_scheduler_run_log` before requesting the aggregated summary.

| Run | Started at | Completed at | Issue count | Issues | Status |
|---:|---|---|---:|---|---|
| 1 | `2026-06-24T18:11:51Z` | `2026-06-24T18:11:51Z` | 3 | `AI-16`, `AI-17`, `AI-18` | completed |
| 2 | `2026-06-24T18:11:56Z` | `2026-06-24T18:11:56Z` | 3 | `AI-16`, `AI-17`, `AI-18` | completed |
| 3 | `2026-06-24T18:12:01Z` | `2026-06-24T18:12:01Z` | 3 | `AI-16`, `AI-17`, `AI-18` | completed |

## Aggregated result

3 scheduled runs collected 9 issue snapshots for 3 unique issues in the last 60 minutes.

- Runs total: `3`
- Snapshots total: `9`
- Issue count: `3`
- Status counts: `{'done': 3}`
- Priority counts: `{'high': 1, 'medium': 2}`
- Assignee counts: `{'student': 3}`

| Issue | Title | Status | Priority | Assignee |
|---|---|---|---|---|
| `AI-16` | Подключить MCP discovery | `done` | `medium` | `student` |
| `AI-17` | Подключить первый MCP tool | `done` | `high` | `student` |
| `AI-18` | Расширить MCP orchestration | `done` | `medium` | `student` |

## Артефакты

JSON, SQLite и Markdown outputs сформированы в `../artifacts`:

- `tracker-summary.sqlite3`
- `tools-list.json`
- `scheduler-job-result.json`
- `scheduler-run-log.json`
- `aggregated-summary.json`
- `agent-periodic-summary.md`
