# Day 18 — Планировщик и фоновые задачи через MCP tools

## 🎥 Видео-отчёт

> [▶️ Смотреть видео-отчёт](https://drive.google.com/open?id=1UOJ3nmCv4EId9F2351txPnpuTewAqGzq)

## Исходное условие

🔥 День 18. Планировщик и фоновые задачи

Сделайте MCP-инструмент с отложенным или периодическим выполнением.

Пример:

👉 reminder
👉 периодический сбор данных
👉 регулярный summary

Инструмент должен:

👉 сохранять данные (JSON / SQLite)
👉 выполняться по расписанию
👉 возвращать агрегированный результат

Результат:

Агент, который работает 24/7 и периодически выдаёт сводку

Формат:

Видео + Код

## Цель задания

Проверить, как MCP tool может быть не только разовым read-only вызовом, но и интерфейсом управления
scheduled/background workflow: агент запускает периодический сбор данных через MCP, server сохраняет
snapshots в SQLite, а второй MCP tool возвращает агрегированную summary.

## Реализация

Статус: `✅ done`.

Day 18 продолжает Day 17. Day 17 публиковал один read-only tool `get_tracker_issue` поверх mock
Tracker API. Day 18 добавляет отдельный локальный stdio MCP server `AI Advent Tracker Scheduler`,
который публикует три scheduler-aware tools:

- `schedule_tracker_summary` — запускает bounded scheduled collection для mock Tracker issues,
  сохраняет каждый run в SQLite и возвращает structured job result;
- `get_scheduler_run_log` — читает SQLite и возвращает ordered timeline scheduled runs без нового
  collection и без изменения состояния;
- `get_tracker_summary` — читает SQLite, агрегирует snapshots по окну времени и возвращает
  structured summary для агентского отчёта.

Архитектурный flow:

```text
Agent -> MCP client -> stdio MCP server -> scheduler/service layer -> mock Tracker API -> SQLite
```

Сценарий демонстрации bounded: `interval_seconds=5.0`, `max_runs=3`. Это показывает 24/7-паттерн,
но не оставляет тесты и видео в бесконечном процессе. Внутренний service layer поддерживает
`max_runs=None` как режим "работать до отмены", но CLI и artifacts используют только bounded demo.

SQLite schema создаётся автоматически и содержит:

- `jobs` — зарегистрированные scheduled jobs;
- `runs` — отдельные итерации collection;
- `issue_snapshots` — снимки карточек задач на каждом run.

CLI scenario перед bounded demo пересоздаёт свой файл `tracker-summary.sqlite3`, чтобы повторный
запуск команды давал воспроизводимые 3 runs и 9 snapshots. Сами MCP tools и service layer остаются
append-only и могут накапливать историю в существующей SQLite базе.

Server не пишет обычные сообщения в stdout. stdout занят MCP protocol messages; диагностические
сообщения SDK идут в stderr.

## Новые команды

| Команда | Назначение |
|---|---|
| `ai-advent-scenarios mcp-scheduler-demo` | Запустить локальный stdio MCP server, вызвать scheduler tools и сохранить SQLite/JSON/Markdown artifacts |
| `--issue-keys KEY ...` | Список mock Tracker issue keys; default `AI-16 AI-17 AI-18` |
| `--interval-seconds N` | Интервал между scheduled runs; для video/demo `5`, для тестов можно `0` |
| `--max-runs N` | Ограничение числа runs; default `3` |
| `--window-minutes N` | Окно агрегации для summary; default `60` |
| `--timeout-seconds N` | Общий timeout startup, scheduled collection и summary; default `30` |
| `--output-dir PATH` | Каталог artifacts |
| `--results-file PATH` | Markdown result report |

Новых slash-команд интерактивного агента нет.

## Структура файлов

```text
weeks/week-04/day-18-scheduler-background-tasks/
├── README.md
├── artifacts/
│   ├── agent-periodic-summary.md
│   ├── aggregated-summary.json
│   ├── scheduler-job-result.json
│   ├── scheduler-run-log.json
│   ├── tools-list.json
│   └── tracker-summary.sqlite3
├── results/
│   └── day-18-scheduler-background-tasks.md
└── snapshot/
    ├── .env.example
    ├── README.md
    ├── pyproject.toml
    ├── uv.lock
    ├── src/ai_advent_agent/
    │   ├── __init__.py
    │   ├── mcp_mock_api.py
    │   ├── mcp_scheduler_client.py
    │   ├── mcp_scheduler_server.py
    │   ├── mcp_scheduler_service.py
    │   ├── mcp_scheduler_store.py
    │   ├── mcp_tool_client.py
    │   └── scenarios.py
    └── tests/test_mcp_scheduler_demo.py
```

Актуальный код находится в `packages/ai_advent_agent/src/ai_advent_agent/`:

- `mcp_scheduler_store.py`;
- `mcp_scheduler_service.py`;
- `mcp_scheduler_server.py`;
- `mcp_scheduler_client.py`;
- routing в `scenarios.py`;
- tests в `packages/ai_advent_agent/tests/test_mcp_scheduler_demo.py`.

## Как запустить

### Актуальный пакет

#### Offline-сценарий

Команда не требует интернета, API key, внешнего Tracker API, LLM API, VPS или cron/systemd.

```bash
uv run --project packages/ai_advent_agent ai-advent-scenarios mcp-scheduler-demo \
  --issue-keys AI-16 AI-17 AI-18 \
  --interval-seconds 5 \
  --max-runs 3 \
  --output-dir weeks/week-04/day-18-scheduler-background-tasks/artifacts \
  --results-file weeks/week-04/day-18-scheduler-background-tasks/results/day-18-scheduler-background-tasks.md
```

Тесты Day 18:

```bash
uv run --project packages/ai_advent_agent pytest \
  packages/ai_advent_agent/tests/test_mcp_scheduler_demo.py -q
```

#### Online/interactive агент

Online/interactive запуск не предусмотрен. Day 18 намеренно не использует LLM API, реальные внешние
API, API keys, сеть или бесконечный daemon в default scenario.

### Snapshot Day 18

#### Offline-сценарий

```bash
cd weeks/week-04/day-18-scheduler-background-tasks/snapshot
uv sync
uv run python -m pytest -q
uv run ai-advent-scenarios mcp-scheduler-demo \
  --issue-keys AI-16 AI-17 AI-18 \
  --interval-seconds 5 \
  --max-runs 3 \
  --output-dir ../artifacts \
  --results-file ../results/day-18-scheduler-background-tasks.md
```

API key и интернет не требуются. Runtime-файлы сохраняются вне `snapshot/`.

#### Online/interactive агент

Online/interactive запуск snapshot-а не предусмотрен.

## Сценарий демонстрации для видео

1. Показать исходное условие Day 18 и уточнение преподавателя: фокус на MCP tool, VPS не нужен.
2. Показать отличие от Day 17: теперь agent не вызывает mock API напрямую, а управляет scheduled
   workflow через MCP tools.
3. Открыть `mcp_scheduler_server.py`: показать `FastMCP`, tools `schedule_tracker_summary`,
   `get_scheduler_run_log` и `get_tracker_summary`, structured output и `mcp.run(transport="stdio")`.
4. Открыть `mcp_scheduler_service.py`: показать bounded loop, `max_runs`, `interval_seconds`,
   `asyncio.sleep` и сбор mock issues.
5. Открыть `mcp_scheduler_store.py`: показать SQLite schema `jobs`, `runs`, `issue_snapshots` и
   aggregation по latest issues.
6. Запустить `pytest packages/ai_advent_agent/tests/test_mcp_scheduler_demo.py -q`.
7. Выполнить основной scenario `mcp-scheduler-demo` с `interval_seconds=5`, `max_runs=3`.
8. Открыть `artifacts/tools-list.json`: показать, что tools получены через `list_tools`.
9. Открыть `artifacts/scheduler-job-result.json`: показать job id, status и runs completed.
10. Открыть `artifacts/scheduler-run-log.json`: показать три scheduled runs с timestamps и issue keys.
11. Открыть `artifacts/aggregated-summary.json`: показать counts и latest issues.
12. Открыть `artifacts/agent-periodic-summary.md`: показать, как агент использовал timeline и summary.
13. Открыть `results/day-18-scheduler-background-tasks.md` как итоговый отчёт с timeline-таблицей.
14. Перейти в `snapshot/`, выполнить `uv sync`, `uv run python -m pytest -q` и snapshot scenario.

## Результаты

Фактический запуск 2026-06-24 создал локальный stdio MCP server `AI Advent Tracker Scheduler`,
получил tools `schedule_tracker_summary`, `get_scheduler_run_log` и `get_tracker_summary`,
выполнил 3 scheduled runs по задачам `AI-16`, `AI-17`, `AI-18` с `interval_seconds=5.0`, сохранил
9 snapshots в SQLite, вернул timeline scheduled runs и aggregated summary.

Проверенные файлы:

- [tools-list.json](artifacts/tools-list.json);
- [scheduler-job-result.json](artifacts/scheduler-job-result.json);
- [scheduler-run-log.json](artifacts/scheduler-run-log.json);
- [aggregated-summary.json](artifacts/aggregated-summary.json);
- [agent-periodic-summary.md](artifacts/agent-periodic-summary.md);
- [day-18-scheduler-background-tasks.md](results/day-18-scheduler-background-tasks.md).

## Выводы

Scheduled/background workflow удобно выражать через MCP tools как control plane: агент запускает
работу и запрашивает summary через protocol boundary, а хранение, расписание и агрегация остаются
на стороне server/service layer. Для учебного и тестового сценария bounded schedule безопаснее
настоящего 24/7 daemon: он воспроизводим, не зависает и создаёт проверяемые artifacts.
