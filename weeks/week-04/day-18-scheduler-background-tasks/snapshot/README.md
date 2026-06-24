# Snapshot Day 18 — Scheduler and Background MCP Tasks

Самодостаточная версия Day 18. Snapshot запускает локальный stdio MCP server, публикует
scheduler-aware tools `schedule_tracker_summary`, `get_scheduler_run_log` и `get_tracker_summary`,
сохраняет snapshots в SQLite и формирует run timeline + aggregated summary.

API key, LLM API, интернет, VPS, cron/systemd, Celery, Redis и APScheduler не требуются.

## Проверки

```bash
uv sync
uv run python -m pytest -q
uv run ruff check .
uv run ty check
```

## Offline-сценарий

Из каталога `snapshot/`:

```bash
uv run ai-advent-scenarios mcp-scheduler-demo \
  --issue-keys AI-16 AI-17 AI-18 \
  --interval-seconds 5 \
  --max-runs 3 \
  --output-dir ../artifacts \
  --results-file ../results/day-18-scheduler-background-tasks.md
```

Runtime-файлы сохраняются вне `snapshot/`.
