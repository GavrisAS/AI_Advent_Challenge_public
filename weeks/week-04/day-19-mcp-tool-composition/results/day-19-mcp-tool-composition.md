# Day 19 — Композиция MCP-инструментов

Статус: `✅ done`.

## Задание и уточнение

Day 19 проверяет автоматический пайплайн из нескольких MCP tools. Важное уточнение преподавателя:
`summarize` в исходном задании означает отчёт / итог / обработку данных, а не LLM-суммаризацию
внутри tool. Поэтому `build_tracker_report` строит deterministic Markdown report без LLM.

## Архитектура

```text
LLM planner -> generic MCP client loop -> stdio MCP server -> deterministic tools
```

- Planner: `llm`
- Model: `deepseek-v4-flash`
- Transport: `stdio`
- Server: `AI Advent MCP Tool Composition 1.28.0`
- Protocol version: `2025-11-25`
- MCP Python SDK: `1.28.0`
- Hardcoded pipeline: `false`
- LLM API calls: `4`
- Pipeline completed: `true`
- Required chain found: `true`
- Save completed: `true`
- Issue count: `3`
- Goal: Найди завершённые MCP-задачи Week 04, собери итоговый отчёт и сохрани его в файл.

## MCP tools

| Tool | Schema summary |
|---|---|
| `build_tracker_report` | Build a deterministic Markdown report from Tracker issues without using an LLM. |
| `save_report_to_file` | Save a Markdown report inside the configured local artifacts directory. |
| `search_tracker_issues` | Return filtered mock Tracker issues for MCP tool composition demos. |

## Tool-call trace

Последовательность вызовов пришла от planner/model и была исполнена generic loop через
`session.call_tool(...)`:

| Step | Requested by | Tool | Outcome |
|---:|---|---|---|
| 1 | `llm` | `search_tracker_issues` | `{"issue_count": 3, "issues": ["AI-16", "AI-17", "AI-18"]}` |
| 2 | `llm` | `build_tracker_report` | `{"issue_count": 3, "status_counts": {"done": 3}, "priority_counts": {"high": 1, "medium": 2}, "markdown_length": 746}` |
| 3 | `llm` | `save_report_to_file` | `{"saved": true, "path": "weeks/week-04/day-19-mcp-tool-composition/artifacts/tracker-composition-report.md", "bytes_written": 947, "sha256": "a444cbf790abff719d1fc5ca54a58f04fdc931fa31bff00f48e4d9db1367070f"}` |

Pipeline sequence: `search_tracker_issues` -> `build_tracker_report` -> `save_report_to_file`

## Передача данных между tools

- Output `search_tracker_issues.issues` стал input `build_tracker_report.issues`.
- Output `build_tracker_report.markdown` стал input `save_report_to_file.markdown`.
- `save_report_to_file` создал файл отчёта внутри configured artifacts/output dir.

## Итоговый report file

- Path: `weeks/week-04/day-19-mcp-tool-composition/artifacts/tracker-composition-report.md`
- SHA-256: `a444cbf790abff719d1fc5ca54a58f04fdc931fa31bff00f48e4d9db1367070f`
- Artifacts directory: `weeks/week-04/day-19-mcp-tool-composition/artifacts`

## Команды запуска

Основной LLM-driven запуск требует `DEEPSEEK_API_KEY`:

```bash
uv run --project packages/ai_advent_agent ai-advent-scenarios mcp-tool-composition-demo \
  --planner llm \
  --goal "Найди завершённые MCP-задачи Week 04, собери итоговый отчёт и сохрани его в файл." \
  --output-dir weeks/week-04/day-19-mcp-tool-composition/artifacts \
  --results-file weeks/week-04/day-19-mcp-tool-composition/results/day-19-mcp-tool-composition.md
```

Offline scripted fallback используется только для deterministic tests без API key:

```bash
uv run --project packages/ai_advent_agent ai-advent-scenarios mcp-tool-composition-demo \
  --planner scripted \
  --output-dir .tmp/day19-scripted-fallback \
  --results-file .tmp/day19-scripted-fallback/day-19-mcp-tool-composition.md
```

## Testing notes

Default tests не ходят в сеть и не требуют `DEEPSEEK_API_KEY`. `scripted` planner остаётся
test/offline fallback: он имитирует tool-call responses, но проходит через тот же generic
execution loop и stdio MCP `call_tool`.

## Security notes

- Реальный Tracker/Jira/GitHub API не используется; данные mock.
- Secrets, raw API headers и API key не сохраняются в artifacts.
- `save_report_to_file` запрещает абсолютные пути, `..` и path separators.
- Output ограничен configured artifacts/output directory.
