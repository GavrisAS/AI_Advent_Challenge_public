# Day 20 — Orchestration MCP

Статус: `✅ done`.

## Цель

Проверить модель-агностичную оркестрацию нескольких MCP servers: discovery, normalized registry,
neutral JSON planning, validation, routing в правильную stdio session и длинный flow до safe save.

## Архитектурные свойства

- Planner mode: `llm-json`
- Model: `deepseek-v4-flash`
- `model_specific_tool_calling=false`
- `hardcoded_pipeline=false`
- Tool calls: `11`
- Servers used: `tracker`, `knowledge`, `report`, `storage`
- Required ordered chain found: `true`
- Completed: `true`
- LLM API calls: `12`

Несколько servers используются как отдельные boundaries ответственности: Tracker выдаёт mock
issues, Knowledge — локальный учебный контекст, Report — deterministic processing, Storage —
единственная точка записи финальных flow artifacts.

## Registered servers

| Server | Transport | Tools | Status |
|---|---|---:|---|
| `tracker` | `stdio` | 2 | `initialized` |
| `knowledge` | `stdio` | 2 | `initialized` |
| `report` | `stdio` | 2 | `initialized` |
| `storage` | `stdio` | 2 | `initialized` |

## Tools by server

| Server | Tool | Behavior |
|---|---|---|
| `knowledge` | `get_best_practice_note` | read/process |
| `knowledge` | `get_mcp_day_context` | read/process |
| `report` | `build_next_steps` | read/process |
| `report` | `build_orchestration_report` | read/process |
| `storage` | `save_json_file` | write |
| `storage` | `save_markdown_file` | write |
| `tracker` | `get_tracker_issue` | read/process |
| `tracker` | `search_tracker_issues` | read/process |

## Routing timeline

Каждый action проверен против registry, затем разрешён через `sessions[action.server]`. Таблица
показывает фактический порядок; success допускает дополнительные/retry calls, но требует ordered
subsequence `tracker -> knowledge -> report -> next_steps -> save_markdown -> save_json`.

| Step | Chosen by | Server | Tool | Result summary |
|---:|---|---|---|---|
| 1 | `llm` | `tracker` | `search_tracker_issues` | `{"issue_count": 4, "issue_keys": ["AI-16", "AI-17", "AI-18", "AI-19"]}` |
| 2 | `llm` | `tracker` | `search_tracker_issues` | `{"issue_count": 1, "issue_keys": ["AI-20"]}` |
| 3 | `llm` | `knowledge` | `get_mcp_day_context` | `{"id": "day-18", "title": "Scheduler-aware MCP tools"}` |
| 4 | `llm` | `knowledge` | `get_mcp_day_context` | `{"id": "day-19", "title": "Composition tools внутри одного MCP server"}` |
| 5 | `llm` | `knowledge` | `get_mcp_day_context` | `{"id": "day-20", "title": "Orchestration нескольких MCP servers"}` |
| 6 | `llm` | `knowledge` | `get_best_practice_note` | `{"id": "multi-server-orchestration", "title": "Multi-server orchestration"}` |
| 7 | `llm` | `knowledge` | `get_best_practice_note` | `{"id": "model-agnostic-planning", "title": "Model-agnostic planning"}` |
| 8 | `llm` | `report` | `build_orchestration_report` | `{"title": "Week 04 MCP orchestration report", "issue_count": 5, "next_steps_count": 0, "markdown_bytes": 2796}` |
| 9 | `llm` | `report` | `build_next_steps` | `{"title": "Week 04 MCP orchestration report", "issue_count": 5, "next_steps_count": 4, "markdown_bytes": 0}` |
| 10 | `llm` | `storage` | `save_markdown_file` | `{"saved": true, "path": "final-orchestration-report.md", "bytes_written": 2796, "sha256": "dbeba2c67738b61b5a60ba0f8a5aaf9d77e27d72103c8e3bec71a050b7ceabbc"}` |
| 11 | `llm` | `storage` | `save_json_file` | `{"saved": true, "path": "saved-flow-state.json", "bytes_written": 7185, "sha256": "bb64e88d9ff4eaf13e1e4b865256666a6d31048c6476066ea6aeb1d245ee5680"}` |

## Saved artifacts

- `server-registry.json`
- `tools-registry.json`
- `orchestration-trace.json`
- `routing-decisions.json`
- `flow-state.json`
- `final-orchestration-report.md`
- `final-agent-answer.md`
- `saved-flow-state.json`

`final-orchestration-report.md` и `saved-flow-state.json` сохранены соответствующими Storage MCP
tools. Registry, trace, routing decisions, compact flow state и final answer являются служебными
evidence-файлами host/orchestrator.

## Проверка выбора и порядка

- server/tool validation запрещает неизвестный server, tool и несовпадающую принадлежность;
- routing decision фиксирует requested server/tool и resolved session для каждого вызова;
- success требует все четыре server, минимум восемь calls и причинный ordered subsequence;
- exact sequence equality не используется, поэтому допустимы LLM retry/extra calls;
- scripted planner предназначен только для offline tests и не заменяет этот online result.
